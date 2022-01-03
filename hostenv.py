import os

def dst_home(user, env):
    if user == 'root':
        return '/root'
    if 'home' in env:
        return os.path.join(env.home, user)
    return os.path.join('/home/', user)

#
# Back-to-back topology description
#
b2b = [('192.168.%d.2/24' % (11+i) , '192.168.%d.3/24' % (11+i),
       '192.168.%d.4/24' % (11+i), '192.168.%d.5/24' % (11+i)) for i in
        range(4)]
b2b_cl = [('10.10.1.1/24', '10.10.1.2/24')]
addr_map = {
        'n01': {'ens1f0': '192.168.11.151/24', 'ens1f1': '192.168.11.152/24'},
        'n02': {'enp6s0f0': '192.168.11.153/24', 'enp6s0f1': '192.168.11.154/24',
            'enp4s0f4np0':'192.168.11.163/24', 'enp4s0f6np0': '192.168.11.162'},
        'n04': {'enp1s0f0': '192.168.11.161/24'},
        'n05': {'enp1s0f0': '192.168.11.162/24'},
        }
n01 = {'ens1f0': '192.168.11.151/24', 'ens1f1': '192.168.11.152/24'}
star = [('192.168.20.%d/24'%i) for i in range(2, 10)]
def_ports = [50000, 60000]

def linux_defaults(env):
    #
    # default values for Linux hosts
    #
    env.nogit = True
    if 'workdir' not in env:
        env.workdir = os.path.join(dst_home(env.user, env), 'deployed')
    env.linux_src = os.path.join(env.workdir, 'net-next')
    env.netmap_src = os.path.join(env.workdir, 'netmap')
    env.nm_modules = ['e1000', 'ixgbe', 'i40e']
    env.nm_no_ext_drivers = env.nm_modules
    env.nm_premod = ['mdio']
    env.linux_config = 'def'
    env.ovs_src = os.path.join(env.workdir, 'ovs')


    # May fail, set warn_only
    env.nic_all_profiles = {
        'common': [
            'ip link set {} up',
            'ip link set {} promisc on',
            'ethtool -A {} autoneg off tx off rx off',
        ],
        'offload': [
            'ethtool -K {} tx on rx on tso on lro on',
            'ethtool -K {} gso on gro on',
        ],
        'onload': [
            'ethtool -K {} tx off rx off tso off',
            'ethtool -K {} lro off',
            'ethtool -K {} gso off gro off',
        ],
        'csum': [
            'ethtool -K {} tx-checksum-ip-generic on',
            'ethtool -K {} tx-checksum-ipv4 on', # i40e
        ],
        'singleq': [
            'ethtool -L {} combined 1',
        ],
        'mq': [
            'ethtool -L {} combined {}',
        ],
        'noim': [
            'ethtool -C {} adaptive-rx off adaptive-tx off', # i40e
            'ethtool -C {} rx-usecs 0 tx-usecs 0',
        ],
        'busywait': [
            'ethtool -C {} rx-usecs 1022',
            'ethtool -C {} adaptive-rx off adaptive-tx off rx-usecs 1022'
        ],
    }

def freebsd_defaults(env):
    env.nogit = True
    env.workdir = os.path.join(dst_home(env.user, env), 'deployed')
    env.fbsd_src = '/usr/src'
    #env.fbsd_config = 'GENERIC-NODEBUG'
    #env.fbsd_install = getattr(operations, 'sudo')
    env.netmap_src = os.path.join(env.workdir, 'netmap')
    env.nic_all_profiles = {
        'common':[
            'ifconfig {} up',
        ],
        'onload':[
            'ifconfig {} -lro -tso -txcsum -rxcsum',
        ],
        'offload':[
            'ifconfig {} lro tso txcsum rxcsum',
        ],
        'noim': [
            'sysctl dev.{}.queue0.interrupt_rate=1',
            'sysctl dev.{}.rx_itr=1',
        ],
    }
    env.nooldkern = False

def hostenv(env):

    name = env.original_host

    env.priv_if_num = env.ncpus * 2
    env.priv_ring_size = 33024 # accommodate 2048 slots
    env.priv_ring_num = env.ncpus * 2 * 2
    # 10k extra buffers per core
    env.priv_buf_num = env.priv_ring_num * 2048 + env.ncpus * 10000

    if name == 'vm0':
        env.nogit=True
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.ifs = ['em1', 'em2']
        env.ifs_addr = {'em1':'172.16.176.65/24', 'em2':'172.16.177.65/24'}
        env.fbsd_nm_modules = ['e1000']
        env.fbsd_src = '/usr/src'
        #env.fbsd_config = 'GENERIC-NODEBUG'
        #env.fbsd_config = 'FABRIC'
        env.fbsd_install = getattr(operations, 'sudo')
        env.netmap_src = os.path.join(env.workdir, 'netmap')
        env.freebsd_ifcmd = {
                'common':[
                        'ifconfig {} up',
                ]
        }

    elif name == 'vm1':
        env.nogit=True
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.ifs = ['eth1', 'eth2']
        env.ifs_addr = {'eth1':'172.16.176.66/24', 'eth2':'172.16.177.66/24'}
        env.nm_modules = ['e1000', 'ixgbe']
        env.nm_premod = ['mdio']
        env.linux_src = os.path.join(env.workdir, 'net-next')
        env.linux_config = 'def'
        env.fbsd_src = os.path.join(env.workdir, 'freebsd')
        env.netmap_src = os.path.join(env.workdir, 'netmap')
        env.ovs_src = os.path.join(env.workdir, 'ovs')
        env.nic_profiles = {
            'common':[
                'ip link set {} up',
                'ethtool -C {} rx-usecs 1',
                'ethtool -A {} autoneg off tx off rx off',
            ],
            'offload':[
                'ethtool -K {} tx on rx on tso on',
                'ethtool -K {} gso on gro on'
            ],
            'onload':[
                'ethtool -K {} tx off rx off tso off',
                'ethtool -K {} gso off gro off'
            ]
        }

    elif name == 'va0':
        env.ifs = ['em0']
        #env.ifs_addr = {'em0':b2b[0][0], 'em1':b2b[1][0], 'em2':'192.168.18.2'}
        #env.ifs_mac = {'em0':'08:00:27:ad:47:06', 'em1':'08:00:27:6c:66:20'}
        #env.ifs_def_dst_addr = {'em0':b2b[0][1], 'em1':b2b[1][1]}
        #env.ifs_def_dst_mac = {'em0':'08:00:27:24:fb:ba',
        #        'em1':'08:00:27:dc:da:59'}
        #env.fbsd_nm_modules = ['e1000', 'ixgbe', 'i40e']
        #env.def_sport = def_ports[0]
        #env.def_dport = def_ports[1]
        freebsd_defaults(env)
        env.fbsd_config = 'GENERIC'
        env.nic_profiles = ['common', 'onload']

    elif name == 'vp':
        linux_defaults()
        env.ifs = ['eth1']
        env.ifs_addr = {'eth1':'192.168.15.15/24'}
        env.ifs_mac = {'eth1':'08:00:27:75:03:24'}
        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nm_modules = ['e1000']
        env.nic_profiles = ['common', 'onload', 'csum']
        #env.nic_profiles = ['common', 'onload']
        env.no_clflush = True;

    elif name == 'va5':
        linux_defaults(env)
        env.linux_config = 'cur'
        env.linux_src = os.path.join(dst_home(env.user, env), 'net-next')

    elif name == 'va1':
        linux_defaults(env)
        env.linux_config = 'cur'
        env.ifs = ['eth1']
        env.ifs_addr = {'eth1':'192.168.18.4/24'}
        #env.ifs_mac = {'eth1':'08:00:27:24:fb:ba', 'eth2':'08:00:27:dc:da:59'}
        #env.ifs_def_dst_addr = {'eth1':b2b[0][0], 'eth2':b2b[1][0]}
        #env.ifs_def_dst_mac = {'eth1':'00:00:27:18:dd:ff',
        #                        'eth2':'00:00:27:ef:1c:e2'}
        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nm_modules = ['e1000', 'i40e']
        env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum']
        #env.nic_profiles = ['common', 'onload']
        env.no_clflush = True;

    elif name == 'va2' or name == 'va3':
        linux_defaults(env)
        env.linux_config = 'cur'
        if name == 'va2':
            env.ifs = ['eth1']
        elif name == 'va3':
            env.ifs = ['enp0s8']
        #env.nm_modules = ['virtio_net.c']
        env.nm_modules = ['e1000']
        env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum']
        env.no_clflush = True;

    elif name == 'o02':
        linux_defaults(env)
        env.linux_config = 'cur'
        env.nm_modules = ['ixgbe']
        env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum', 'noim', 'mq']

#    elif name == 'n04':# or name == 'n05':# or name == 'n04':
#        if name == 'n05' or name == 'n04':
#            env.ifs = ['ixl0']
#        else:
#            env.ifs = ['ix0']
#        if name == 'n05' or name == 'n07':
#            env.ifs_addr = {env.ifs[0]:b2b[0][3]}
#        else:
#            env.ifs_addr = {env.ifs[0]:b2b[0][2]}
#        freebsd_defaults(env)
#        env.fbsd_config = 'GENERIC'
#        env.nic_profiles = ['common', 'onload']
#
    elif name == 'n01' or name == 'n02' or name == 'n04' or name == 'n05' or name == 'n06' or name == 'n07':
        linux_defaults(env)
        env.nrings = env.ncpus
        env.linux_config = 'cur'
        if name == 'n01':
            env.ifs = ['ens1f0', 'ens1f1']
        elif name == 'n02':
            env.ifs = ['enp6s0f0', 'enp6s0f1']
        elif name in ['n04', 'n05', 'n06', 'n07']:
            env.ifs = ['enp1s0f0']

        if name in addr_map:
            env.ifs_addr = addr_map[name]

        #env.nm_modules = ['ixgbe', 'i40e']
        if name == 'n06' or name == 'n07':
            env.nm_modules = ['ixgbe']
        else:
            env.nm_modules = ['i40e']
        env.nm_no_ext_drivers = env.nm_modules
        if name == 'n01' or name == 'n04' or name == 'n06':
            env.nic_profiles = ['common', 'singleq', 'onload', 'csum', 'noim']
        else:
            env.nic_profiles = ['common', 'offload', 'csum', 'noim']


    elif name == 'localhost':
        env.nogit=True
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.nm_modules = ['e1000', 'ixgbe']
        env.nm_premod = ['mdio']
        env.linux_src = os.path.join(dst_home(env.user), 'net-next')
        env.linux_config = 'def'
        env.fbsd_src = os.path.join(env.workdir, 'freebsd')
        env.netmap_src = os.path.join(env.workdir, 'netmap')
        env.ovs_src = os.path.join(env.workdir, 'ovs')
        env.linux_ifcmd = {
            'common':[
                'ip link set {} up',
                'ethtool -C {} rx-usecs 1',
                'ethtool -A {} autoneg off tx off rx off',
            ],
            'offload':[
                'ethtool -K {} tx on rx on tso on',
                'ethtool -K {} gso on gro on'
            ],
            'onload':[
                'ethtool -K {} tx off rx off tso off',
                'ethtool -K {} gso off gro off'
                ]
            }
        env.dgraph = '/Users/michio/dgraphdata'

    elif name == 'cl0' or name == 'cl1' or name == 'cl2' or name == 'cl3':
        env.home = '/users'
        linux_defaults(env)
        #env.linux_src = '/dev/shm/net-next'
        env.nm_modules = ['i40e']
        if name == 'cl2':
            env.nm_modules = ['ixgbe']
        env.nm_no_ext_drivers = env.nm_modules
        env.linux_config = 'cur'
        env.nopmem = True
        #env.linux_src = ''
        env.ifs = ['ens1f0']
        if name == 'cl2' or name == 'cl3':
            env.ifs = ['enp6s0f0']
        env.ifs_addr = {env.ifs[0]:b2b_cl[0][0]}
        if name == 'cl1':
            env.ifs_addr = {env.ifs[0]:b2b_cl[0][1]}
        #env.nm_modules = ['i40e']
        #if name == 'cl2':
        #    env.nm_modules = ['ixgbe']
        #env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum', 'mq', 'noim']
        #if name != 'cl0' and name != 'cl2':
        #    env.nic_profiles = ['common', 'offload', 'csum', 'mq', 'noim']
        #if name == 'cl0' or name =='cl2':

    else:
        linux_defaults(env)
        print('No special configuration for {}'.format(name))

    return env
