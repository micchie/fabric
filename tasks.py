# Copyright (C) 2014 Michio Honda.  All rights reserved.
#
# Michio Honda  <micchie@sfc.wide.ad.jp>
#
# Redistribution and use in source and binary forms, with or without
#Falsemodification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the project nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE PROJECT AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE PROJECT OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.

from invoke import task
from fabric import Connection
from patchwork import files
from hostenv import hostenv
import re
import os
import time
from patchwork.transfers import rsync

def is_freebsd(c):
    return c.ostype == 'FreeBSD'

def is_linux(c):
    return c.ostype == 'Linux'

def ensure_connected(c, host):
    if not 'user' in c:
        c = Connection(host)
        _hostenv(c)
    return c

def rsync_upload(c, src, dst, nogit=False, delete=False):
    src = src.rstrip('/') + '/'
    exclude = '.git' if nogit else ''
    ssh_agent = os.environ.get('SSH_AUTH_SOCK', None)
    if ssh_agent:
        c.config['run']['env']['SSH_AUTH_SOCK'] = ssh_agent
    rsync(c, src, dst, delete=delete, exclude=exclude, rsync_opts='-q',
            ssh_opts=get_ssh_opts(c))

def norm(s):
    s = re.sub("^\s+", "", s)
    s = re.sub("\s+", " ", s)
    return s, s.split(' ')[:-1]

def ostype_and_ncores(c):
    ostype = c.run('uname -s', hide='both').stdout.strip()
    if ostype == 'Linux':
        r = c.run('cat /proc/cpuinfo | egrep ^processor | wc', hide='both').stdout
        ncpus = int( norm(r)[1][0] )
    elif ostype == 'FreeBSD':
        r = c.run("sysctl hw.ncpu | cut -d' ' -f2").stdout
        ncpus = int(r)
    else:
        print('Unsupported OS %s' % ostype)
        return None, None
    return ostype, ncpus

def _hostenv(c, output=False):
    c.ostype, c.ncpus = ostype_and_ncores(c)
    hostenv(c)
    c.output = c.original_host + '.log' if output else None
    return c

# Survive broken proxycommand handler of rsync
def get_ssh_opts(c):
    if 'proxycommand' in c.ssh_config:
        return '-o "ProxyCommand {}"'.format(c.ssh_config['proxycommand'])
    return ''

@task
def rsynctest(c, host, src, dst):
    c = Connection(host)
    c = hostenv(c)
    ssh_agent = os.environ.get('SSH_AUTH_SOCK', None)
    if ssh_agent:
        c.config['run']['env']['SSH_AUTH_SOCK'] = ssh_agent
    rsync(c, src, dst, ssh_opts=get_ssh_opts(c))

@task
def test(c, host):
    c = Connection(host)
    print('c', c)
    c.run('ls')

@task
def test2(c, host):
    c = Connection(host)
    _hostenv(c)
    c.sudo('bash -c "cd deployed && ls"')

def _exists(c, s):
    if is_freebsd(c):
        r = c.run('test -e %s'%s, warn_only=True)
        return True if r.exited == 0 else False
    return files.exists(c, s)

@task
def noht(c, host=None):
    c = ensure_connected(c, host)
    c.sudo('bash -c "echo off > /sys/devices/system/cpu/smt/control"',warn=True,
            echo=True)
    time.sleep(1)

@task
def setup_irq(c, host=None):
    c = ensure_connected(c, host)

    nomq = False
    for i in c.ifs:
        s = 'cat /proc/interrupts | grep "{}-TxRx" | tr -s " " | sed "s/^ //"'
        r = c.run(s.format(i), hide='stdout', echo=True, warn=True)
        print('r.stdout', r.stdout)
        if not r.stdout:
            nomq = True
            r = c.run(s.replace('-TxRx', '').format(i), echo=True, warn=True)
        if r.failed:
            continue
        lines = r.stdout.split('\n')[:-1]
        for l in lines:
            irq = l.split(':')[0]
            cor = 0 if nomq else int(l.split('-')[-1])
            p = '/proc/irq/{}/smp_affinity'.format(irq)
            c.sudo('bash -c "echo {:x} >> {}"'.format(1 << cor, p), echo=True)

def do_ifcmd(c, cmd, ifname):
    n = (ifname, c.ncpus) # second argument is only for mq profile
    if is_freebsd(c) and re.search('sysctl', cmd):
        ift = re.split('[0-9]', ifname)[0]
        ifi = ifname[len(ift):len(ifname)]
        n = ('{}.{}'.format(ift, ifi), '{}'.format(c.ncpus))
    c.sudo(cmd.format(*n), warn=True, echo=True)

@task
def setup_ifs(c, host=None, ifs=None, profiles=[]):

    c = ensure_connected(c, host)
    if not ifs:
        ifs = c.ifs
    if not profiles:
        profiles = c.nic_profiles
    print('Ensuring no HT enabled')
    noht(c, host)
    # ncpus may has changed
    c.ostype, c.ncpus = ostype_and_ncores(c)

    # configure interfaces
    for i in ifs:
        for p in profiles:
            cmdlist = []
            if p in c.nic_all_profiles:
                cmdlist = c.nic_all_profiles[p]
            for cmd in cmdlist:
                do_ifcmd(c, cmd, i)
    # set irq properly if possible
    setup_irq(c, host)

    # configure IP addresses
    for i in ifs:
        if 'ifs_addr' in c and i in c.ifs_addr:
            if is_linux(c):
                # warn on the address already exists
                c.sudo('ip addr add {} dev {}'.format(c.ifs_addr[i], i),
                        warn=True, echo=True)
            elif is_freebsd(c):
                c.sudo('ifconfig %s inet %s' % (i, c.ifs_addr[i]), warn=True,
                        echo=True)

def _enable_netmap_debug(c):
    f = os.path.join(c.netmap_src, 'sys/dev/netmap/netmap_kern.h')
    s = '#define CONFIG_NETMAP_DEBUG 1'
    if not files.contains(c, f, s):
        c.run("sed -i '1s/^/{}\\n/' {}".format(s, f))

@task
def unload_netmap(c):
    r = c.run('lsmod', hide='both').stdout
    lines = r.split('\n')

    # TODO: delete all vale instances and their lookup modules

    netmap_modules = []
    for l in lines:
        items = l.split()
        if items and items[0] == 'netmap':
            if len(items) == 4: # has modules relying on netmap
                netmap_modules += items[3].split(',')
            break
    else:
        print('netmap is not loaded')
        return
    print('unload_netmap: netmap_modules ', netmap_modules)

    for m in netmap_modules:
        c.sudo('rmmod ' + m, warn=True)
        r = c.sudo('modprobe -r ' + m, warn=True)
        if r.exited != 0:
            r = c.sudo('rmmod ' + m)
    c.sudo('rmmod netmap', warn=True)

@task
def load_netmap(c, host=None, debug=False):
    c = ensure_connected(c, host)
    if is_freebsd(c):
        for v, k in ((c.priv_if_num, 'if_num'), (c.priv_ring_num,
                'ring_num'), (c.priv_buf_num, 'buf_num'),
                (c.priv_ring_size, 'ring_size')):
            c.sudo('sysctl -w dev.netmap.priv_%s=%d'%(k, v))
        setup_ifs(c.ifs, profiles=c.nic_profiles)
        return
    unload_netmap(c)

    c.sudo('insmod ' + '{}/netmap.ko'.format(c.netmap_src), echo=True)
    c.sudo('lsmod')
    if 'nm_premod' in c:
        for m in c.nm_premod:
            c.sudo('modprobe ' + m)
    time.sleep(1)
    for m in c.nm_modules:
        if re.search('\.c', m):
            m = m.strip('\.c')
        if c.run('lsmod | grep ^' + m, warn=True, hide='both').exited == 0:
            c.sudo('rmmod ' + m, warn=True) # XXX e1000e against e1000
            #sudo('modprobe -r ' + m, warn_only=True) # XXX e1000e against e1000
            c.sudo('lsmod')
        for k in '%s/%s.ko'%(m,m), '%s.ko'%m:
            k = os.path.join(c.netmap_src, k)
            if _exists(c, k):
                r = c.sudo('insmod ' + k, warn=True, echo=True)
                if r.exited != 0:
                    r = c.sudo('modprobe ' + k)
                break
        else:
            raise Exception('Couldn\'t find %s.ko!'%m)
#        for v, k in ((32, 'if_num'), (64, 'ring_num'), (32784, 'buf_num'), (36864, 'ring_size')):
    for v, k in ((c.priv_if_num, 'if_num'), (c.priv_ring_num, 'ring_num'),
            (c.priv_buf_num, 'buf_num'), (c.priv_ring_size, 'ring_size')):
        c.sudo('bash -c "echo %d >> /sys/module/netmap/parameters/priv_%s"'%(v,
            k), echo=True)
    if debug:
        c.sudo('bash -c "echo 65536 >> /sys/module/netmap/parameters/debug"',
            echo=True)
    #sudo('echo %d > /sys/module/netmap/parameters/debug'%65536)
    setup_ifs(c, c.ifs, profiles=c.nic_profiles)
    print('done load_netmap')

def _make_netmap_linux(c, path, config, apps=False ,drivupload=False):
    # let's get kernel source path
    if not c.linux_src:
        v = c.run('uname -r', hide=True).stdout.split('-')[0]
        c.linux_src = '/usr/src/linux-source-' + v + '/linux-source-' + v
        print('guess Linux source is at ', c.linux_src)
    with c.cd(path):
        if not not config:
            if drivupload:
                put('i*.tar.gz', 'LINUX/ext-drivers/')
            cmd = './configure --disable-ptnetmap --disable-generic' + \
                  ' --enable-extmem --enable-vale --enable-stack'
            if apps:
                cmd += ' --apps={}'.format(apps)
            else:
                cmd += ' --no-apps'
            if 'nm_driver_suffix' in c:
                cmd += ' --driver-suffix=-netmap'
            if c.linux_src:
                cmd += ' --kernel-dir={}'.format(c.linux_src)
            if config == 'nodriv':
                cmd += ' --no-drivers'
            else:
                cmd += ' --drivers=' + ','.join(c.nm_modules)
            if 'nm_no_ext_drivers' in c:
                cmd += ' --no-ext-drivers=' + ','.join(c.nm_no_ext_drivers)
            #c.run(cmd) # XXX
            #c.run('make distclean', hide='both')
            print(cmd)
            c.run(cmd)
        #run('make -j%d KSRC=%s' % (env.ncpus+1, env.linux_src))
        cmd = 'make'
        c.run(cmd)

@task
def make_netmap_apps(c, host=None, src=None):
    c = ensure_connected(c, host)
    makecmd = 'gmake' if is_freebsd(c) else 'make'
    appdir = os.path.join(c.netmap_src, 'apps')
    cmd = '{} apps'.format(makecmd)
    cleancmd = '{} clean-apps'.format(makecmd)
    if src:
        rsync_upload(c, os.path.join(src, os.path.basename(appdir)), appdir,
                nogit=c.nogit)
    with c.cd(c.netmap_src):
        print(cmd)
        c.run(cleancmd)
        c.run(cmd)
    phttpd = os.path.join(appdir, 'phttpd')
    print('phttpd', phttpd, _exists(c, phttpd))
    if _exists(c, phttpd):
        with c.cd(phttpd):
            c.run('make clean; make')

@task
def make_netmap(c, host, src=None, config=False, fbsddriv=False,
        drivupload=False, debug=False, noload=False, apps=''):
    c = ensure_connected(c, host)

    if src:
        if is_linux(c) and not config:
            update_files = []
            for p in ['sys/dev/netmap', 'sys/net']:
                r = c.local('ls {}'.format(os.path.join(src, p)), hide='out')
                for l in r.stdout.splitlines():
                    update_files.append(os.path.join(p, l))
            for f in ['bsd_glue.h', 'netmap_linux.c']:
                update_files.append(os.path.join('LINUX', f))
            for f in update_files:
                print(os.path.join(src, f), os.path.join(c.netmap_src, f))
                c.put(os.path.join(src, f), os.path.join(c.netmap_src, f))
        else:
            rsync_upload(c, src, c.netmap_src, nogit=c.nogit, delete=config)
    if debug:
        _enable_netmap_debug(c)
    #tweak_netmap(env.netmap_src)
    libnetmappath = os.path.join(c.netmap_src, 'libnetmap')
    if is_linux(c):
        _make_netmap_linux(c, c.netmap_src, config, apps, drivupload)
        if _exists(c, libnetmappath):
            with c.cd(libnetmappath):
                #run('gcc -c nmreq.c -I../sys -DLIB')
                #run('ar rcs libnetmap.a nmreq.o')
                c.run('make')
        make_netmap_apps(c, src=src)
        if not noload:
            load_netmap(c, debug=debug)

    elif is_freebsd(c):
        with cd(env.netmap_src):
            if not fbsddriv:
                print('copying files')
                #run('cp sys/dev/netmap/netmap* sys/dev/netmap/stackmap.c sys/dev/netmap/ptnetmap.c ' + os.path.join(env.fbsd_src,
                run('cp sys/dev/netmap/netmap* ' + os.path.join(env.fbsd_src,
                'sys/dev/netmap/'))
                s = 'sys/dev/netmap/netmap_stack.c'
                if _exists(os.path.join(env.netmap_src, s)):
                    run('cp %s '%s + os.path.join(env.fbsd_src,
                            'sys/dev/netmap/'))
            else:
                run('cp sys/dev/netmap/* ' + os.path.join(env.fbsd_src,
                'sys/dev/netmap/'))
            run('cp sys/net/netmap* ' + os.path.join(env.fbsd_src, 'sys/net/'))
        make_freebsd(None, upload=False, config=config, world=False)
        with cd(env.netmap_src):
            if _exists(libnetmappath):
                with cd(libnetmappath):
                    run('clang -c nmreq.c -I../sys -DLIB')
                    run('ar rcs libnetmap.a nmreq.o')
        make_netmap_apps()
    print('done make_netmap')

@task
def make_linux(c, host, src=None, config=False,
        debug=False, trace=False, opt=False, pmem=False, nospace=False):
    c = Connection(host)
    _hostenv(c)
    if src:
        rsync_upload(c, src, c.linux_src, nogit=c.nogit, delete=(not not config))
    if config:
        with c.cd(c.linux_src):
            c.run("make mrproper")
        config_linux(c, debug, trace, opt, (not ('nopmem' in c)))
    with c.cd(c.linux_src):
        c.run("make -j%d bzImage" % (c.ncpus+1))
        c.run("make -j%d modules" % (c.ncpus+1))
        if nospace:
            print('freeing up some space')
            l = c.run('find . | grep "\.o$"').stdout.split('\n')
            batches = [l[i:i+20] for i in range(0, len(l), 20)]
            for b in batches:
                c.run('rm {}'.format(' '.join(b)), echo=True)
    print('installing the new kernel to {}'.format(c.linux_src))
    c.sudo('bash -c "cd {} && make modules_install"'.format(c.linux_src))
    c.sudo('bash -c "cd {} && make install"'.format(c.linux_src))

def update_kconfig(c, d, conffile):
    for k, v in d.items():
        kk = 'CONFIG_' + k
        # match against uncommented and commented lines
        for confline in kk + '=', '# ' + kk + ' ':
            if open(conffile).read().find(confline) != -1:
                if v == 'n':
                    if confline[0] != '#':
                        c.local('sed -i -e "s/{}/{}/" {}'.format(
                            confline + '.*$', '# ' + kk + ' is not set',
                            conffile))
                    # otherwise already commented out
                else:
                    if '"' in v:
                        v = v.replace('"', '\\"')
                    c.local('sed -i -e "s/{}/{}/" {}'.format( confline +
                        '.*$', kk + '=' + v, conffile))
                break
        else:
            if v != 'n':
                open(conffile, 'a').write(kk + '=' + v + '\n')

#
# config must be def, cur or old
#
def config_linux(c, debug, trace, opt, pmem):

    base = c.linux_config
    with c.cd(c.linux_src):
        if base == 'cur':
            c.run('cp /boot/config-`uname -r` .config')
            c.run('yes "" | make olddefconfig')
        elif base == 'def':
            c.run("make defconfig")

    #ver = kernelversion()
    if opt:
        if debug:
            print('debug cannot coexist with opt')
            debug = False
        if trace:
            print('trace cannot coexist with opt')
            trace = False

    d = {}

    # Let's add LOCALVERSION for pxeboot which doesn't boot with short name
    d.update({'LOCALVERSION':'"-fab"'})

    # y for systemtap, otherwise n
    if trace:
        trace_config = ['RELAY', 'DEBUG_FS', 'DEBUG_INFO', 'KPROBES',
                        'KPROBE_EVENTS',
                        'DEBUG_INFO_DWARF4', 'ENABLE_MUST_CHECK',
                        'FRAME_POINTER', 'DEBUG_KERNEL', 'KALLSYMS_ALL',
                        'BPF_SYSCALL', 'BPF_EVENTS', 'BPF_JIT_ALWAYS_ON']
        d.update({k:'y' for k in trace_config})
        d.update({'DEBUG_INFO_REDUCED':'n'})

    # General kernel debug (disable if unnecessary)
    if debug:
        dbg_config = ['UNINLINE_SPIN_UNLOCK', 'PREEMPT_COUNT', 'DEBUG_SPINLOCK',
                      'DEBUG_MUTEXES', 'DEBUG_LOCK_ALLOC', 'DEBUG_LOCKDEP',
                      'LOCKDEP', 'DEBUG_ATOMIC_SLEEP', 'TRACE_IRQFLAGS',
                      'PROVE_RCU']
        d.update({k:'y' for k in dbg_config})

    ## virtio - based on http://www.linux-kvm.org/page/Virtio
    virtio_config = {'VIRTIO_MENU', 'VIRTIO_PCI', 'VIRTIO_PCI_LEGACY',
                     'VIRTIO_BALLOON', 'VIRTIO_BLK', 'VIRT_DRIVERS',
                     'VIRTIO_CMDLINE_DEVICES'}
    d.update({k:'y' for k in virtio_config})

    virtio_config = ['VIRTIO', 'VIRTIO_NET', 'VIRTIO_INPUT', 'VIRTIO_MMIO',
                     'VBOXGUEST', 'VIRTIO_CONSOLE', 'VIRTIO_BLK']
    d.update({k:'m' for k in virtio_config})

    # netmap drivers
    nic_config = {'DCB':'n', 'E1000':'m', 'E1000E':'y', 'IGB':'m', 'IGB_HWMON':'y',
                  'IGB_DCA':'y', 'IGBVF':'m', 'IXGBE':'m', 'IXGBE_HWMON':'y',
                  'R8169':'m', 'IXGBE_DCA':'y', 'IXGBE_DCB':'n', 'IXGBEVF':'m',
                  'I40E':'m', 'I40EVF':'m', 'I40E_DCB':'n', 'VETH':'m', 'INFINIBAND':'n'}
    d.update(nic_config)

    # mellanox
    mlx_config = {'NET_VENDOR_MELLANOX':'y', 'MLX4_EN':'m', 'MLX4_CORE':'m',
                  'MLX4_DEBUG':'y', 'MLX4_CORE_GEN2':'y', 'MLX5_CORE':'m',
                  'MLX5_CORE_EN':'y', 'MLX5_EN_ARFS':'y', 'MLX5_EN_RXNFC':'y',
                  'MLX5_MPFS':'y', 'MLX4_ESWITCH':'y', 'MLX5_CORE_IPOIB':'y',
                  'MLX5_SW_STEERING':'y'}
    d.update(mlx_config)

    # netmap after 4.17
    ax25_config = {'HAMRADIO':'y', 'AX25':'y'}
    d.update(ax25_config)

    tun_config = {'NET_IPIP':'m', 'NET_L3_MASTER_DEV':'y', 'BPF_JIT':'y',
                  'NET_SWITCHDEV':'y', 'NET_IPGRE':'m', 'NET_IPGRE_DEMUX':'m',
                  'NET_IPGRE_BROADCAST':'y', 'NET_IP_TUNNEL':'y',
                  'VXLAN':'m', 'LIBCRC32C':'y', 'TUN':'m', 'GENEVE':'m'}
    d.update(tun_config)

    noconfigs = ['IP_SCTP', 'IP_DCCP', 'SWAP', 'SOUND', 'AUDIT',
              'NET_VENDOR_3COM', 'E100', 'NET_VENDOR_MICROSEMI',
              'NET_VENDOR_MICROCHIP', 'NET_VENDOR_MYRI', 'NET_VENDOR_NETERION',
              'NET_VENDOR_ADAPTEC', 'NET_VENDOR_AGERE', 'NET_VENDOR_ALTEON',
              'ALTERA_TSE', 'NET_VENDOR_AMD', 'NET_XGENE', 'EDAC', 'SECURITY',
              'NET_VENDOR_ARC', 'NET_VENDOR_ATHEROS', 'NET_VENDOR_CISCO',
              'NET_VENDOR_DEC', 'DNET', 'CX_ECAT', 'NET_VENDOR_DLINK',
              'NET_VENDOR_FUJITSU', 'NET_VENDOR_MICREL', 'NET_VENDOR_NATSEMI',
              'NET_VENDOR_NVIDIA', 'NET_VENDOR_OKI', 'NET_VENDOR_QUALCOMM',
              'NET_VENDOR_RDC', 'NET_VENDOR_SAMSUNG', 'NET_VENDOR_SEEQ',
              'NET_VENDOR_SILAN', 'NET_VENDOR_SIS', 'NET_VENDOR_SMSC',
              'NET_VENDOR_STMICRO', 'NET_VENDOR_SUN', 'NET_VENDOR_TEHUTI',
              'NET_VENDOR_TI', 'NET_VENDOR_VIA', 'NET_VENDOR_WIZNET',
              'NET_VENDOR_XIRCOM', 'FDDI', 'HIPPI', 'NET_SB1000',
              'USB_PRINTER', 'INPUT_TOUCHSCREEN', 'INPUT_TABLET',
              'INPUT_JOYSTICK', 'USB_NET_DRIVERS', 'WIRELESS',
              'NET_VENDOR_EMULEX', 'NET_VENDOR_EXAR', 'NET_VENDOR_BROCADE',
              'NET_VENDOR_HP', 'NET_VENDOR_I825XX', 'NET_VENDOR_MARVELL',
              'HAMRADIO', 'NET_VENDOR_MYRI', 'RFKILL', 'TASK_XACCT', 'PCCARD',
              'PCMCIA', 'PCMCIA_LOAD_CIS', 'CARDBUS', 'IRDA', 'DONGLE', 'BT',
              'WIMAX', 'RFKILL', 'CAIF', 'NFC', 'MEDIA_SUPPORT', 'RC_CORE',
              'USB_VIDEO_CLASS', 'USB_VIDEO_CLASS_INPUT_EVDEV', 'USB_GSPCA',
              'DVB_USB', 'VIDEO_EM28XX', 'USB_AIRSPY', 'USB_HACKRF',
              'USB_MSI2500', 'MEDIA_PCI_SUPPORT', 'VIDEO_MEYE', 'VIDEO_SOLO6X10',
              'VIDEO_TW68', 'VIDEO_ZORAN', 'VIDEO_IVTV',
              'NET_VENDOR_RENESAS', 'NET_VENDOR_QLOGIC', 'MACINTOSH_DRIVERS',
              'NET_VENDOR_ALACRITECH', 'NET_CADENCE',
              'NET_VENDOR_EZCHIP', 'WLAN', 'PPS', 'LEDS_TRIGGERS',
              'EEPC_LAPTOP', 'SYSTEM_TRUSTED_KEYRING', 'SYSTEM_TRUSTED_KEYS',
              'STAGING', 'DRM_XEN', 'SLIP', 'VMXNET3',
              'NET_VENDOR_CHELSIO', 'NET_VENDOR_AQUANTIA',
              'CAN', 'WAN', 'SCSI_QLOGIC_1280', 'SCSI_QLA_FC', 'SCSI_QLA2XXX',
              'SCSI_QLA_ISCSI', 'SCSI_LPFC', 'SCSI_BFA_FC', 'ATM', 'ISDN',
              'IIO', 'USB_GADGET', '6LOWPAN', 'BT', 'BATMAN_ADV', 'TIPC',
              'DECNET', 'PHONET', 'NET_NCSI', 'ATALK', 'AFS_FS', 'CIFS',
              'CEPH_FS', 'CEPH_LIB', 'F2FS_FS', 'REISERFS_FS', 'GFS2_FS',
              'OCFS2_FS', 'BLK_DEV_DRBD', 'FUSION', 'TARGET', 'FIREWIRE',
              'MACINTOSH_DRIVERS', 'NET_FC', 'YENTA', 'RAPIDIO',
              'SENSORS_LIS3LV02D', 'AD525X_DPOT', 'IBM_ASM', 'PHANTOM',
              'TIFM_CORE', 'ICS932S401', 'ENCLOSURE_SERVICES', 'SGI_XP',
              'APDS9802ALS', 'ISL29003', 'ISL29020', 'SENSORS_TSL2550',
              'SENSORS_BH1770', 'SENSORS_APDS990X', 'HMC6352', 'DS1682',
              'VMWARE_BALLOON', 'AGP', 'I2C_NVIDIA_GPU', 'VGA_ARB',
              ]
    d.update({k:'n' for k in noconfigs})

    """
    d.update({'IOMMU_SUPPORT':'n'})
    """

    # Following PMEM/NVMe options seem unnecessary
    # pmem
    #nvm_config = {'EXPERT':'y', 'XFS_FS':'y', 'FS_DAX':'y',
    #        'X86_PMEM_LEGACY_DEVICE':'y', 'X86_PMEM_LEGACY':'y',
    #        'ACPI_NFIT':'m', 'LIBNVDIMM':'y', 'BLK_DEV_PMEM':'m', 'ND_BLK':'m',
    #        'ND_CLAIM':'y', 'ND_BTT':'m', 'BTT':'y', 'ND_PFN':'m',
    #        'NVDIMM_PFN':'y', 'ZONE_DMA':'n', 'MEMORY_HOTPLUG':'y',
    #        'MEMORY_HOTREMOVE':'y', 'SPARSEMEM_VMEMMAP':'y', 'ZONE_DEVICE':'y',
    #        'TRANSPARENT_HUGEPAGE':'y', 'DEV_DAX':'y'}
    #if pmem:
    #    d.update(nvm_config)

    # NVMe
    nvme_config = ['NVME_CORE', 'BLK_DEV_NVME', 'NVME_MULTIPATH']
    d.update({k:'y' for k in nvme_config})
    nvme_config = ['NVME_FABRICS', 'NVME_RDMA', 'NVME_TCP', 'NVME_TARGEt',
                   'NVME_TARGET_LOOP', 'NVME_TARGET_RDMA', 'NVME_TARGET_TCP']
    d.update({k:'m' for k in nvme_config})

    # Small optimization
    #opt_config = {'NETFILTER':'n', 'RETPOLINE':'n'}
    if opt:
        opt_config = {'NETFILTER':'n', 'RETPOLINE':'n'}
        d.update(opt_config)

    conffile = '.config'
    c.get(os.path.join(c.linux_src, conffile))
    update_kconfig(c, d, conffile)
    c.put(conffile, os.path.join(c.linux_src, conffile))

    with c.cd(c.linux_src):
        c.run("make olddefconfig")

def run_bg(c, cmd, sockname='dtach'):
    return c.run('dtach -n `mktemp -u /tmp/%s.XXXX` %s' % (sockname, cmd))

@task
def start_dgraph(c, host, mem='2048', nozero=False, noalpha=False,
        noratel=False):
    _hostenv(env.host_string)
    if 'dgraph' in c:
        data = env.dgraph
    else:
        data = '/tmp/'
    data = data.rstrip('/')
    if not nozero:
        c.run('pkill dgraph', warn=True)
    dgraph = 'dgraph'
    if 'dgraphpath' in c:
        dgraph = os.path.join(c.dgraphpath, dgraph)
    if not nozero:
        run_bg(c, '%s zero -w %s/zw'%(dgraph, data))
    #run_bg('dgraph alpha --lru_mb 2048 --zero localhost:5080 -w %s/w -p /%s/p --my=localhost:7080'
    if not noalpha:
        run_bg(c,
          '%s alpha --lru_mb {} --zero localhost:5080 -w {}/w -p {}/p'.format(
              dgraph, mem, data, data))
    if not noratel:
        if not 'dgraphpath' in c:
            run_bg(c, 'dgraph-ratel')

@task
def config_newfs(c, host, dev, fstype='xfs', newfs=False):
    c = ensure_connected(c, host)

    mnt = '/mnt/ext'
    #opt = '-d su=4k,sw=1'
    opt = ''

    if not _exists(c, dev):
        print('no device %s'%dev)
    if not _exists(c, mnt):
        c.sudo('mkdir ' + mnt)
    else:
        r = c.run('mount | grep %s'%mnt, warn=True)
        #if r.succeeded:
        c.sudo('umount  ' + mnt, warn=True)
    if newfs:
        c.sudo('mkfs.%s %s -f %s'%(fstype, opt, dev), warn=True)
    c.sudo('mount %s %s'%(dev, mnt), warn=True)
    if newfs:
        c.sudo('chmod 777 ' + mnt)

@task
def config_pmem(c, host, fstype='xfs', fname='netmap_mem', fsize=8000000000, agcount=1):
    c = ensure_connected(c, host)

    mnt = '/mnt/pmem'
    dev = '/dev/pmem0'
    #opt = 'su=1024000k,sw=1'
    opt = ''
    if fstype == 'xfs':
        opt = '-d '
        if not agcount:
            opt += 'su=1024m,sw=1'
        else:
            #opt = 'agcount=1,su=1024m,sw=1'
            opt += 'agsize=8192000000'
        opt += ' -m reflink=0'
    fsize = int(fsize)
    bs = 4096

    if not _exists(c, mnt):
        c.sudo('mkdir ' + mnt)
    else:
        r = c.run('mount | grep {}'.format(mnt), warn=True)
        if not r.failed:
            c.sudo('umount  ' + mnt, warn=True)

    if fstype == 'xfs':
        devopt = '-f ' + dev
    else:
        devopt = dev

    r = c.sudo('mkfs.{} {} {}'.format(fstype, opt, devopt), warn=True, echo=True)
    if r.failed:
        # To allocate 256m region and file, we can use memmap 384M!640M
        print('try again...')
        if fstype == 'xfs':
            opt = '-d '
            if not agcount:
                opt += 'su=256m,sw=1'
            else:
                opt += 'agsize=1024000000'
        #opt = 'agsize=256m,su=256m,sw=1'
        fsize /= 8
        c.sudo('mkfs.{} {} {}'.format(fstype, opt, devopt), echo=True)
    c.sudo('mount -o dax {} {}'.format(dev, mnt), echo=True)

#    if fname and fsize and not exists(os.path.join(mnt, fname)):
#        sudo('fallocate -l %d %s' % (fsize, os.path.join(mnt, fname)))
#        sudo('dd if=/dev/zero of=%s bs=%d count=%d' %
#               (os.path.join(mnt, fname), bs, fsize/bs))
    c.sudo('chmod -R 777 ' + mnt, echo=True)

if __name__ == '__main__':
    test('va1')
