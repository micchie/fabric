from invoke import task
from fabric import Connection
from patchwork import files
import os
import time
import re

def norm(s):
    s = re.sub("^\s+", "", s)
    s = re.sub("\s+", " ", s)
    return s, s.split(' ')[:-1]

def _exists(c, s):
    return files.exists(c, s)

@task
def pmem(c):
    c = Connection('localhost')

    fstype = 'xfs'
    fname = 'netmap_mem'
    fsize = 8000000000
    agcount = 1

    mnt = '/mnt/pmem'
    dev = '/dev/pmem0'

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
    devopt = '-f ' + dev
    r = c.sudo('mkfs.{} {} {}'.format(fstype, opt, devopt), warn=True, echo=True)
    if r.failed:
        # To allocate 256m region and file, we can use memmap 384M!640M
        print('try again...')
        opt = '-d '
        if not agcount:
            opt += 'su=256m,sw=1'
        else:
            opt += 'agsize=1024000000'
        fsize /= 8
        c.sudo('mkfs.{} {} {}'.format(fstype, opt, devopt), echo=True)
    c.sudo('mount -o dax {} {}'.format(dev, mnt), echo=True)
    c.sudo('chmod -R 777 ' + mnt, echo=True)

@task
def setup(c):
    c = Connection('localhost')
    c.netmap_src = os.path.join(c.run('pwd', hide='both').stdout.strip(),
            'deployed/netmap')
    # identify the NIC name
    cmd = ('ip addr show to 10.10.1.0/24 | grep ^[0-9]: | cut -d " " -f2'
          ' | sed "s/:$//"')
    ifname = c.run(cmd, echo=True).stdout.strip()
    cmd = 'ethtool -i {} | grep ^drive | cut -d: -f2 | tr -d " "'.format(ifname)
    driver = c.run(cmd, echo=True).stdout.strip()
    cmd = 'ip addr show to 10.10.1.0/24 | grep inet | tr -s " " | cut -d" " -f3'
    addr = c.run(cmd, echo=True).stdout.strip()
    c.ifs = [ifname]
    c.netmap_modules = [driver]
    c.ifs_addr = {c.ifs[0]:addr}

    singleq = True
    lowintr = False # don't enable for i40e driver

    for m in c.netmap_modules + ['netmap']:
        c.sudo('rmmod {}'.format(m), warn=True, echo=True)

    c.sudo('insmod ' + '{}/netmap.ko'.format(c.netmap_src), echo=True)
    for m in c.netmap_modules:
        c.sudo('insmod {}'.format(os.path.join(c.netmap_src, m, m+'.ko')),
            warn=True, echo=True)
    # disable HT
    c.sudo('bash -c "echo off > /sys/devices/system/cpu/smt/control"',
            warn=True, echo=True)
    time.sleep(1)

    # obtain CPU core count
    r = c.run('cat /proc/cpuinfo | egrep ^processor | wc', hide='both').stdout
    ncpus = int( norm(r)[1][0])

    # setup the NIC
    for i in c.ifs:
        if 'ifs_addr' in c and i in c.ifs_addr:
            c.sudo('ip addr add {} dev {}'.format(c.ifs_addr[i], i),
                    echo=True, warn=True)
        cmds = ['ip link set {} up',
                'ip link set {} promisc on',
                'ethtool -A {} autoneg off tx off rx off',
                'ethtool -K {} tx off rx off tso off',
                'ethtool -K {} lro off', # i40e cannot change lro setting
                'ethtool -K {} gso off gro off',
                'ethtool -K {} tx-checksum-ip-generic on', # ixgbe
                'ethtool -K {} tx-checksum-ipv4 on' # i40e
               ]

        cmds.append('ethtool -L {} ' +
                'combined {}'.format(1 if singleq else ncpus))
        intr = 1022 if lowintr else 0
        cmds.append('ethtool -C {} ' +
                'rx-usecs {} tx-usecs {}'.format(intr, intr))
        cmds.append('ethtool -C {} adaptive-rx off adaptive-tx off ' +
               'rx-usecs {} tx-usecs {}'.format(intr, intr))
        for cmd in cmds:
            c.sudo(cmd.format(i), echo=True, warn=True)

    nomq = False
    for i in c.ifs:
        s = 'cat /proc/interrupts | grep "{}-TxRx" | tr -s " " | sed "s/^ //"'
        r = c.run(s.format(i), hide='stdout', echo=True, warn=True)
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

    c.priv_if_num = 32
    c.priv_ring_num = 320
    c.priv_buf_num = 400000
    c.priv_ring_size = 33024  # accommodate 2048 slots
    for v, k in ((c.priv_if_num, 'if_num'), (c.priv_ring_num, 'ring_num'),
            (c.priv_buf_num, 'buf_num'), (c.priv_ring_size, 'ring_size')):
        c.sudo('bash -c "echo {} >> '
               '/sys/module/netmap/parameters/priv_{}"'.format(v, k), echo=True)

