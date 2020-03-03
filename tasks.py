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
    # avoid rsync_project that uses env.host rather than host_string
    src = src.rstrip('/') + '/'
    delete_opt = '--delete' if delete else ''
    excl_opt = '--exclude=\'.git\'' if nogit else ''
    c.local("rsync -azl %s %s %s %s:%s" % \
            (delete_opt, excl_opt, src, c.original_host, dst))

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

@task
def test(c, host):
    c = Connection(host)
    c = hostenv(host, c)
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
def setup_irq(c, host=None):
    c = ensure_connected(c, host)

    for i in range(0, len(c.ifs)):

        # obtain irq list
        r = c.run('cat /proc/interrupts | grep {} | grep TxRx'.format(c.ifs[i]),
                warn=True).stdout
        l = r.split()
        last = 1
        for e in l:
            if re.search('{}-TxRx-0'.format(c.ifs[i]), e):
                break
            last += 1
        else:
            continue
        irqs = [l[j:j+last] for j in range(0, len(l), last)]

        # set irqs to intended cores 
        cpuid = 0
        for s in irqs:
            path = '/proc/irq/{}/smp_affinity'.format(s[0].rstrip(':'))
            cmd = 'echo {:x} >> {}'.format(1 << cpuid, path)
            c.sudo(cmd)
            cpuid += 1

def do_ifcmd(c, cmd, ifname):
    n = ifname
    if is_freebsd(c) and re.search('sysctl', cmd):
        ift = re.split('[0-9]', ifname)[0]
        ifi = ifname[len(ift):len(ifname)]
        n = '{}.{}'.format(ift, ifi)
    c.sudo(cmd % n, warn=True)

@task
def setup_ifs(c, host=None, ifs=None, profiles=[]):

    c = ensure_connected(c, host)
    if not ifs:
        ifs = c.ifs
    if not profiles:
        profiles = c.nic_profiles
        
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
                        warn=True)
            elif is_freebsd(c):
                c.sudo('ifconfig %s inet %s' % (i, c.ifs_addr[i]), warn=True)

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

    for m in netmap_modules:
        c.sudo('rmmod ' + m, warn=True)
        r = c.sudo('modprobe -r ' + m, warn=True)
        if r.exited != 0:
            r = c.sudo('rmmod ' + m)
    c.sudo('rmmod netmap', warn=True)

@task
def load_netmap(c, host=None):
    c = ensure_connected(c, host)
    if is_freebsd(c):
        for v, k in ((c.priv_if_num, 'if_num'), (c.priv_ring_num,
                'ring_num'), (c.priv_buf_num, 'buf_num'),
                (c.priv_ring_size, 'ring_size')):
            c.sudo('sysctl -w dev.netmap.priv_%s=%d'%(k, v))
        setup_ifs(c.ifs, profiles=c.nic_profiles)
        return
    unload_netmap(c)

    c.sudo('insmod ' + '{}/netmap.ko'.format(c.netmap_src))
    c.sudo('lsmod', hide='both')
    if 'nm_premod' in c:
        for m in c.nm_premod:
            c.sudo('modprobe ' + m, hide='both')
    time.sleep(1)
    for m in c.nm_modules:
        if c.run('lsmod | grep ^' + m, warn=True).exited == 0:
            c.sudo('rmmod ' + m, warn=True) # XXX e1000e against e1000
            #sudo('modprobe -r ' + m, warn_only=True) # XXX e1000e against e1000
            c.sudo('lsmod')
        for k in '%s/%s.ko'%(m,m), '%s.ko'%m:
            k = os.path.join(c.netmap_src, k)
            if _exists(c, k):
                r = c.sudo('insmod ' + k, warn=True)
                if r.exited != 0:
                    r = c.sudo('modprobe ' + k)
                break
        else:
            raise Exception('Couldn\'t find %s.ko!'%m)
#        for v, k in ((32, 'if_num'), (64, 'ring_num'), (32784, 'buf_num'), (36864, 'ring_size')):
    for v, k in ((c.priv_if_num, 'if_num'), (c.priv_ring_num, 'ring_num'),
            (c.priv_buf_num, 'buf_num'), (c.priv_ring_size, 'ring_size')):
        c.sudo('bash -c "echo %d > /sys/module/netmap/parameters/priv_%s"'%(v, k))
    #sudo('echo %d > /sys/module/netmap/parameters/debug'%65536)
    setup_ifs(c, c.ifs, profiles=c.nic_profiles)

def _make_netmap_linux(c, path, config, drivupload=False):
    with c.cd(path):
        if not not config:
            if drivupload:
                put('i*.tar.gz', 'LINUX/ext-drivers/')
            cmd = './configure --disable-ptnetmap --disable-generic' + \
                  ' --enable-extmem --enable-vale --enable-stack --no-apps'
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
        if c.linux_src:
            cmd += ' KSRC=%s' % c.linux_src
        c.run(cmd)

@task
def make_netmap_apps(c=None, src=None):
    if c is None:
        c = Connection(host)
        _hostenv(c)
    makecmd = 'gmake' if is_freebsd(c) else 'make'
    appdir = os.path.join(c.netmap_src, 'apps')
    cmd = '{} apps'.format(makecmd)
    cleancmd = '{} clean-apps'.format(makecmd)
    if src:
        rsync_upload(c, os.path.join(src, os.path.basename(appdir)), appdir,
                nogit=c.nogit)
    with c.cd(c.netmap_src):
        c.run(cleancmd)
        c.run(cmd)

@task
def make_netmap(c, host, src=None, config=False, fbsddriv=False,
        drivupload=False, debug=False):
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
        _make_netmap_linux(c, c.netmap_src, config, drivupload)
        if _exists(c, libnetmappath):
            with c.cd(libnetmappath):
                #run('gcc -c nmreq.c -I../sys -DLIB')
                #run('ar rcs libnetmap.a nmreq.o')
                c.run('make')
        make_netmap_apps(c)
        load_netmap(c)

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
    print('done')

@task
def make_linux(c, host, src, noupload=False, config=False):
    c = Connection(host)
    _hostenv(c)
    if not noupload:
        rsync_upload(c, src, c.linux_src, nogit=c.nogit, delete=(not not config))
    with c.cd(c.linux_src):
        if config:
            c.run("make mrproper")
            config_linux(c)
        c.run("make -j%d bzImage" % (c.ncpus+1))
        c.run("make -j%d modules" % (c.ncpus+1))
    c.sudo('bash -c "cd {} && make modules_install"'.format(c.linux_src))
    c.sudo('bash -c "cd {} && make install"'.format(c.linux_src))

#
# config must be def, cur or old
#
def config_linux(c, perf=True, sym=True, debug=False, stap=False):

    base = c.linux_config
    if base == 'cur':
        c.run('cp /boot/config-`uname -r` .config')
        c.run('make olddefconfig')
    elif base == 'def':
        c.run("make defconfig")

    #ver = kernelversion()

    d = {}

    # Let's add LOCALVERSION for pxeboot which doesn't boot with short name
    d.update({'LOCALVERSION':'"-fab"'})

    # y for systemtap, otherwise n
    if stap:
        stp_config = ['RELAY', 'DEBUG_FS', 'DEBUG_INFO', 'KPROBES',
            'DEBUG_INFO_DWARF4', 'ENABLE_MUST_CHECK', 'FRAME_POINTER',
            'DEBUG_KERNEL']
        d.update({k:'y' for k in stp_config})

    # perf
    if perf:
        d.update({'KPROBE_EVENTS':'y'})

    # General kernel debug (disable if unnecessary)
    if debug:
        dbg_config = ['UNINLINE_SPIN_UNLOCK', 'PREEMPT_COUNT', 'DEBUG_SPINLOCK',
            'DEBUG_MUTEXES', 'DEBUG_LOCK_ALLOC', 'DEBUG_LOCKDEP', 'LOCKDEP',
            'DEBUG_ATOMIC_SLEEP', 'TRACE_IRQFLAGS', 'PROVE_RCU']
        d.update({k:'y' for k in dbg_config})

    # Kernel symbol
    if sym:
        d.update({'KALLSYMS_ALL':'y'})

    # virtio - based on http://www.linux-kvm.org/page/Virtio
    virtio_config = {'VIRTIO_PCI', 'VIRTIO_BALLOON', 'VIRTIO_BLK',
            'VIRTIO', 'VIRTIO_RING', 'VIRTIO_NET'}
    d.update({k:'y' for k in virtio_config})
    d.update({'VIRTIO_NET':'m'})

    # netmap drivers
    nic_config = {'E1000':'m', 'E1000E':'y', 'IGB':'m', 'IGB_HWMON':'y',
            'IGB_DCA':'y', 'IGBVF':'m', 'IXGBE':'m', 'IXGBE_HWMON':'y',
            'R8169':'m', 'IXGBE_DCA':'y', 'IXGBE_DCB':'y', 'IXGBEVF':'m',
            'I40E':'m', 'I40EVF':'m', 'VETH':'m', 'INFINIBAND':'n'}
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

    noconfigs = ['SWAP', 'SOUND', 'AUDIT', 'NET_VENDOR_3COM',
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
            'VIDEO_TW68', 'VIDEO_ZORAN', 'VIDEO_IVTV', 'DRM', 
            'NET_VENDOR_RENESAS', 'NET_VENDOR_QLOGIC', 'MACINTOSH_DRIVERS',
            'WIRELESS', 'NET_VENDOR_ALACRITECH', 'NET_CADENCE',
            'NET_VENDOR_EZCHIP', 'WLAN', 'PPS']
    d.update({k:'n' for k in noconfigs})

    """
    d.update({'IOMMU_SUPPORT':'n'})
    """

    # pmem
    nvm_config = {'EXPERT':'y', 'XFS_FS':'y', 'FS_DAX':'y',
            'X86_PMEM_LEGACY_DEVICE':'y', 'X86_PMEM_LEGACY':'y',
            'ACPI_NFIT':'m', 'LIBNVDIMM':'y', 'BLK_DEV_PMEM':'m', 'ND_BLK':'m',
            'ND_CLAIM':'y', 'ND_BTT':'m', 'BTT':'y', 'ND_PFN':'m',
            'NVDIMM_PFN':'y', 'ZONE_DMA':'n', 'MEMORY_HOTPLUG':'y',
            'MEMORY_HOTREMOVE':'y', 'SPARSEMEM_VMEMMAP':'y', 'ZONE_DEVICE':'y',
            'TRANSPARENT_HUGEPAGE':'y', 'DEV_DAX':'y'}
    d.update(nvm_config)

    # NVMe
    nvme_config = {'NVME_CORE':'y', 'BLK_DEV_NVME':'y'}
    d.update(nvme_config)


    # Small optimization
    opt_config = {'NETFILTER':'n', 'RETPOLINE':'n'}
    d.update(opt_config)

    conffile = '.config'
    for k, v in d.items():
        kk = 'CONFIG_' + k
        # match against uncommented and commented lines
        for confline in kk + '=', '# ' + kk + ' ':
            if files.contains(c, conffile, confline):
                if v == 'n':
                    if confline[0] != '#':
                        c.run('sed -i -e "s/{}/{}/" {}'.format(
                            confline + '.*$', '# ' + kk + ' is not set',
                            conffile))
                    # otherwise already commented out
                else:
                    if '"' in v:
                        v = v.replace('"', '\\"')
                    c.run('sed -i -e "s/{}/{}/" {}'.format(confline + '.*$', kk
                         + '=' + v, conffile))
                break
        else:
            if v != 'n':
                files.append(c, conffile, kk + '=' + v)
    c.run("make olddefconfig")
    #run("make defconfig")

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

if __name__ == '__main__':
    test('va1')
