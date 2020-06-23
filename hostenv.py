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
b2b = [('192.168.%d.2/24' % (11+i) , '192.168.%d.3/24' % (11+i)) for i in
        range(4)]
b2b_cl = [('10.10.1.1/24', '10.10.1.2/24')]
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
    env.priv_if_num = 16
    env.priv_ring_num = 32
    env.priv_buf_num = 32784
    env.priv_ring_size = 18432 # what's this?

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
        'noim': [
            'ethtool -C {} rx-usecs 0 tx-usecs 0',
            'ethtool -C {} adaptive-rx off adaptive-tx '
            'off rx-usecs 0 tx-usecs 0'
        ],
        'busywait': [
            'ethtool -C {} rx-usecs 1022',
            'ethtool -C {} adaptive-rx off adaptive-tx off rx-usecs 1022'
        ],
        'singleq': [
            'ethtool -L {} combined 1',
        ],
        'mq': [
            'ethtool -L {} combined {}',
        ],
    }

def freebsd_defaults():
    env.nogit = True
    env.workdir = os.path.join(dst_home(env.user), 'deployed')
    env.fbsd_src = '/usr/src'
    env.fbsd_config = 'GENERIC-NODEBUG'
    env.fbsd_install = getattr(operations, 'sudo')
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
    # Merge with linux_defaults() better...
    env.priv_if_num = 16
    env.priv_ring_num = 32
    env.priv_buf_num = 32784
    env.priv_ring_size = 18432 # what's this?

    env.nooldkern = False

def hostenv(env):

    name = env.original_host

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

    elif name == 'nina':
        linux_defaults()
        env.ifs = ['eth2', 'eth3']
        env.nm_modules= ['ixgbe']
        env.ifs_mac = {
                env.ifs[0]:'90:e2:ba:09:a7:78',
                env.ifs[1]:'90:e2:ba:09:a7:79'
        }
        env.ifs_def_dst_mac = {
                env.ifs[1]:'90:e2:ba:09:a7:79',
                env.ifs[0]:'90:e2:ba:09:a7:78'
        }
        env.nic_profiles = ['common', 'onload', 'noim']

    elif name == 'nino':
        linux_defaults()
        env.ifs = ['eth2', 'eth3']
        env.nm_modules= ['ixgbe']
        env.ifs_mac = {
                env.ifs[0]:'b4:96:91:15:33:36',
                env.ifs[1]:'90:e2:ba:93:a4:b5'
        }
        env.ifs_def_dst_mac = {
                env.ifs[0]:'90:e2:ba:93:a4:b5',
                env.ifs[1]:'b4:96:91:15:33:36'
        }
        env.nic_profiles = ['common', 'onload', 'noim']

    elif name == 'c230':
        env.password = 'root'
        linux_defaults()

        env.ifs = ['enp4s0f0', 'enp4s0f1']
        env.nm_modules = ['ixgbe']
        env.ifs_mac = {
                env.ifs[0]:'00:1b:21:ce:f5:1c',
                env.ifs[1]:'00:1b:21:ce:f5:1d'
        }
        env.ifs_def_dst_mac = {
                env.ifs[0]:'a0:36:9f:52:2a:b4',
                env.ifs[1]:'a0:36:9f:52:2a:b6'
        }
        env.ifs_addr = {
            env.ifs[0]:b2b[0][0],
            env.ifs[1]:b2b[1][0],
        }
        env.ifs_def_dst_addr = {
                env.ifs[0]:b2b[0][0],
        }
        env.def_sport = def_ports[0]
        env.def_dport = def_ports[1]
        env.nic_profiles = ['common', 'offload', 'noim']

    elif name == 'c237':
        if env.ostype == 'FreeBSD':
            env.ifs = ['ix0', 'ix1', 'ixl2', 'ixl3']
            freebsd_defaults()
            env.fbsd_config = 'GENERIC-NODEBUG'
            env.fbsd_nooldkern = True
        else:
            env.password = 'root'
            linux_defaults()
            env.ifs = ['enp23s0f0', 'enp23s0f1', 'enp179s0f0', 'enp179s0f1']
            env.nm_modules = ['ixgbe','i40e']
            env.nm_no_ext_drivers = ['ixgbe','i40e']

        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:52:2a:b4',
                env.ifs[1]:'a0:36:9f:52:2a:b6'
        }
        env.ifs_def_dst_mac = {
                env.ifs[0]:'a0:36:9f:23:ac:54',
                env.ifs[1]:'a0:36:9f:23:ac:56'
        }
        env.ifs_addr = {
            env.ifs[0]:b2b[0][1],
            env.ifs[1]:b2b[2][1],
            env.ifs[2]:b2b[1][1],
            env.ifs[3]:b2b[3][1],
        }
        env.ifs_def_dst_addr = {
                env.ifs[0]:b2b[0][0],
        }

#        env.ifs = ['enp11s0f0']
#        env.ifs_mac = {env.ifs[0]:'3c:fd:fe:a9:4d:cc'}
#        env.ifs_def_dst_mac = {env.ifs[0]:'3c:fd:fe:a9:4e:24'}
#        env.ifs_addr = {env.ifs[0]:b2b[0][1]}
#        env.ifs_def_dst_addr = {env.ifs[0]:b2b[0][0]}

        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nic_profiles = ['common', 'onload', 'csum', 'singleq', 'noim']
        #env.nic_profiles = ['common', 'offload', 'csum', 'singleq', 'noim']
        env.priv_ring_num = 160
        #env.priv_ring_num = 32
        #env.priv_buf_num = 1024000  # need 2GB
        #env.priv_buf_num = 640000
        env.priv_buf_num = 200000
        #env.priv_ring_size = 33024  # accommodate 2048 slots
        #env.priv_buf_num = 3515625  # 7.2GB
        env.dgraph = '/mnt/nvme/dgraph'
        #env.dgraphpath = '/root/go/bin'

    elif name == 'c307':
        env.password = 'root'
        linux_defaults()
        env.nm_modules = ['ixgbe', 'i40e']
        env.nm_no_ext_drivers = ['ixgbe','i40e']
        env.ifs = ['enp4s0f0', 'enp4s0f1', 'enp3s0f0', 'enp3s0f1']
        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:23:ac:54',
                env.ifs[1]:'a0:36:9f:23:ac:56',
                env.ifs[2]:'3c:fd:fe:a9:4e:24',
                env.ifs[3]:'3c:fd:fe:a9:4e:25',
        }
        env.ifs_def_dst_mac = {
                env.ifs[0]:'a0:36:9f:70:70:98',
                env.ifs[1]:'a0:36:9f:70:70:9a',
                env.ifs[2]:'3c:fd:fe:a9:4d:cc',
                env.ifs[3]:'3c:fd:fe:a9:4d:cd',
        }
#        env.ifs = ['enp3s0f0']
#        env.ifs_mac = {env.ifs[0]:'3c:fd:fe:a9:4e:24'}
#        env.ifs_def_dst_mac = {env.ifs[0]:'3c:fd:fe:a9:4d:cc'}
        env.ifs_addr = {
                env.ifs[0]:b2b[0][0],
                env.ifs[1]:b2b[2][0],
                env.ifs[2]:b2b[1][0],
                env.ifs[3]:b2b[3][0],
        }
        env.ifs_def_dst_addr = {\
                env.ifs[0]:b2b[0][1],
                env.ifs[1]:star[0],
        }
        env.def_sport = def_ports[0]
        env.def_dport = def_ports[1]
        env.nic_profiles = ['common', 'offload', 'noim']
        #env.nic_profiles = ['common', 'onload', 'csum', 'noim']
        #env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        env.priv_ring_num = 320
        env.priv_buf_num = 400000
        env.dgraph = '/mnt/nvme/dgraph'

    elif name == 'c309':
        env.password = 'root'
        linux_defaults()
        env.nm_modules = ['ixgbe']
        env.ifs = ['enp4s0f0', 'enp4s0f1']
        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:31:fa:a0',
                env.ifs[1]:'a0:36:9f:31:fa:a2',
        }
        env.ifs_addr = {
                env.ifs[0]:b2b[0][0],
                env.ifs[1]:star[3],
        }
        env.ifs_def_dst_addr = {
                env.ifs[1]:star[0],
        }
        #env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        #env.nic_profiles = ['common', 'onload', 'busywait', 'singleq']
        env.nic_profiles = ['common', 'offload', 'noim']
        env.priv_ring_num = 320
        env.priv_buf_num = 200000

    elif name == 'c416':
        env.password = 'root'
        linux_defaults()
        env.nm_modules = ['ixgbe']
        env.ifs = ['enp1s0f0', 'enp1s0f1']
        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:70:9d:a4',
                env.ifs[1]:'a0:36:9f:70:9d:a6',
        }
        env.ifs_addr = {
                env.ifs[0]:b2b[0][0],
                env.ifs[1]:b2b[1][0],
        }
        env.ifs_def_dst_addr = {
                env.ifs[0]:b2b[0][1],
                env.ifs[1]:b2b[0][0],
        }
        env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        #env.nic_profiles = ['common', 'onload', 'busywait', 'singleq']
        #env.nic_profiles = ['common', 'offload', 'noim']
        env.priv_ring_num = 320
        env.priv_buf_num = 200000

    elif name == 'c415':
        env.password = 'root'
        linux_defaults()
        env.nm_modules = ['ixgbe']
        env.ifs = ['enp1s0f0', 'enp1s0f1']
        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:23:a4:30',
                env.ifs[1]:'a0:36:9f:23:a4:32',
        }
        #env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        #env.nic_profiles = ['common', 'onload', 'busywait', 'singleq']
        env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        env.priv_ring_num = 320
        env.priv_buf_num = 200000

    elif name == 'c414':
        env.password = 'root'
        env.workdir = os.path.join(dst_home(env.user), 'deployed2')
        linux_defaults()
        env.nm_modules = ['ixgbe']
        env.ifs = ['enp1s0f0', 'enp1s0f1']
        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:23:ac:2c',
                env.ifs[1]:'a0:36:9f:23:ac:2e'
        }
        env.ifs_addr = {
                env.ifs[0]:b2b[1][1],
                env.ifs[1]:b2b[0][1],
        }
        #env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        #env.nic_profiles = ['common', 'onload', 'busywait', 'singleq']
        env.nic_profiles = ['common', 'onload', 'noim', 'singleq']
        #env.nic_profiles = ['common', 'offload', 'noim', 'singleq']
        env.priv_ring_num = 320
        env.priv_buf_num = 200000

    elif name == 'c402':
        env.password = 'root'
        linux_defaults()
        env.nm_modules = ['ixgbe']

        #env.ifs = ['enp8s0f0', 'enp8s0f1', 'enp11s0f0', 'enp11s0f1']
        env.ifs = ['enp8s0f0', 'enp8s0f1']
        env.ifs_mac = {
                env.ifs[0]:'a0:36:9f:70:70:98',
                env.ifs[1]:'a0:36:9f:70:70:9a',
                #env.ifs[2]:'3c:fd:fe:a9:4d:cc',
                #env.ifs[3]:'3c:fd:fe:a9:4d:cd',
        }
        env.ifs_def_dst_mac = {
                env.ifs[0]:'a0:36:9f:23:ac:54',
                env.ifs[1]:'a0:36:9f:23:ac:56',
                #env.ifs[2]:'3c:fd:fe:a9:4e:24',
                #env.ifs[3]:'3c:fd:fe:a9:4e:25',
        }
        env.ifs_addr = {
            env.ifs[0]:b2b[0][1],
            env.ifs[1]:star[0],
            #env.ifs[2]:b2b[1][1],
            #env.ifs[3]:b2b[2][1],
        }
        env.ifs_def_dst_addr = {
                env.ifs[0]:b2b[0][0],
        }

#        env.ifs = ['enp11s0f0']
#        env.ifs_mac = {env.ifs[0]:'3c:fd:fe:a9:4d:cc'}
#        env.ifs_def_dst_mac = {env.ifs[0]:'3c:fd:fe:a9:4e:24'}
#        env.ifs_addr = {env.ifs[0]:b2b[0][1]}
#        env.ifs_def_dst_addr = {env.ifs[0]:b2b[0][0]}

        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nic_profiles = ['common', 'onload', 'csum', 'singleq', 'busywait']
        #env.nic_profiles = ['common', 'onload', 'singleq', 'busywait']
        #env.nic_profiles = ['common', 'onload', 'singleq', 'noim']
        #env.nic_profiles = ['common', 'offload', 'csum', 'singleq', 'noim']
        env.priv_ring_num = 160
        #env.priv_ring_num = 32
        #env.priv_buf_num = 1024000  # need 2GB
        env.priv_buf_num = 640000
        env.priv_ring_size = 33024  # accommodate 2048 slots
        #env.priv_buf_num = 3515625  # 7.2GB

    elif name == 'c404':
        linux_defaults()
        env.ifs = ['eth2']
        env.ifs_mac = {'eth2':'a0:36:9f:71:67:3c',
                'eth3':'a0:36:9f:71:67:3e', 'eth1':'0c:c4:7a:31:ed:ab'}
        env.ifs_def_dst_mac = {'eth2':'a0:36:9f:71:67:04',
                'eth3':'a0:36:9f:71:67:06'}
        env.ifs_addr = {'eth2':b2b[0][0], 'eth3':b2b[1][0]}
        env.ifs_def_dst_addr = {'eth2':b2b[0][1], 'eth3':b2b[1][1]}
        env.def_sport = def_ports[0]
        env.def_dport = def_ports[1]
        env.nic_profiles = ['common', 'onload', 'csum', 'busywait', 'singleq']
        env.priv_ring_num = 256
        env.priv_buf_num = 400000

    elif name == 'c411':
        linux_defaults()
        env.ifs = ['enp1s0f0']
        env.ifs_mac = {'enp1s0f0':'a0:36:9f:71:67:04',
                'enp1s0f1':'a0:36:9f:71:67:06', 'eno2':'0c:c4:7a:77:94:c3'}
        env.ifs_def_dst_mac = {'enp1s0f0':'a0:36:9f:70:70:98',
                'enp1s0f1':'a0:36:9f:70:70:9a '}
        env.ifs_addr = {'enp1s0f0':b2b[0][0], 'enp1s0f1':b2b[1][0]}
        env.ifs_def_dst_addr = {'enp1s0f0':b2b[0][1], 'enp1s0f1':b2b[1][1]}
        env.def_sport = def_ports[0]
        env.def_dport = def_ports[1]
        env.nic_profiles = ['common', 'off', 'csum', 'noim']
        env.priv_ring_num = 128
        env.priv_buf_num = 200000

    elif name == 'c412':
        env.ifs = ['enp1s0f0', 'enp1s0f1', 'eno2']
        env.ifs_mac = {'enp1s0f0':'a0:36:9f:70:9e:44',
                'enp1s0f1':'a0:36:9f:70:9e:46', 'eno2':'0c:c4:7a:77:94:cf'}
        env.ifs_def_dst_mac = {'enp1s0f0':'a0:36:9f:71:67:04',
                'enp1s0f1':'a0:36:9f:71:67:06'}
        env.ifs_addr = {'enp1s0f0':b2b[0][1], 'enp1s0f1':b2b[1][1]}
        env.ifs_def_dst_addr = {'enp1s0f0':b2b[0][0], 'enp1s0f1':b2b[1][0]}

    elif name == 'capoccino.netgroup.uniroma2.it':
        linux_defaults()
        env.ifs = ['eth2', 'eth3']
        env.nic_profiles = ['common', 'onload', 'singleq']

    elif name == 'bach':
        linux_defaults()
        env.linux_src = ''
        env.nm_modules = ['ixgbe']

        env.ifs = ['enp1s0f0', 'enp1s0f1']
        env.ifs_mac = {
                env.ifs[0]:'00:1b:21:80:ea:18',
                env.ifs[1]:'00:1b:21:80:ea:19'
        }
        env.ifs_def_dst_mac = {
        }
        env.ifs_addr = {
            env.ifs[0]:'192.168.1.2',
#            env.ifs[1]:b2b[1][1]
        }
#        env.ifs_def_dst_addr = {
#                env.ifs[0]:b2b[0][0],
#                env.ifs[1]:b2b[1][0]
#        }
        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nic_profiles = ['common', 'onload', 'csum', 'singleq', 'busywait']
    elif name == 'm1':
        env.nogit=True
        env.ifs = ['enp6s0f0']
        env.ifs_addr = {'enp6s0f0':'10.0.0.2/24', 'enp6s0f1':'10.0.1.2/24'}
        env.ifs_mac = {'enp6s0f0':'90:e2:ba:2b:3a:00',
                'enp6s0f1':'90:e2:ba:2b:3a:01'}
        env.ifs_def_dst_addr = {'enp6s0f0':'10.0.0.3', 'enp6s0f1':'10.0.1.3'}
        env.ifs_def_dst_mac = {'enp6s0f0':'90:e2:ba:39:39:50',
                'enp6s0f1':'90:e2:ba:39:39:51'}
        env.nm_modules = ['ixgbe']
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.linux_src = os.path.join(env.workdir, 'net-next')
        env.linux_config = 'def'
        env.fbsd_src = os.path.join(env.workdir, 'freebsd')
        env.netmap_src = os.path.join(env.workdir, 'netmap')
        env.linux_ifcmd = {
            'common':[
                'ip link set {} up',
                # swapped these config with m2
                #'ethtool -C {} rx-usecs 1000',
                #'ethtool -L {} combined 1'
                'ethtool -C {} rx-usecs 0'
            ],
            'offload': [
                'ethtool -A {} autoneg off tx off rx off',
                'ethtool -K {} tx on rx on tso on lro on',
                'ethtool -K {} gso on gro on'
            ],
            'onload': [
                'ethtool -A {} autoneg off tx off rx off',
                'ethtool -K {} tx off rx off tso off lro off',
                'ethtool -K {} gso on gro off'
            ],
            'noim': [
                'ethtool -C {} rx-usecs 0'
            ]
        }

    elif name == 'm2':
        env.nogit=True
        env.ifs = ['enp6s0f0']
        env.ifs_addr = {'enp6s0f0':'10.0.0.3/24', 'enp6s0f1':'10.0.1.3/24'}
        env.ifs_mac = {'enp6s0f0':'90:e2:ba:39:39:50',
                'enp6s0f1':'90:e2:ba:39:39:51'}
        env.ifs_def_dst_addr = {'enp6s0f0':'10.0.0.2', 'enp6s0f1':'10.0.1.2'}
        env.ifs_def_dst_mac = {'enp6s0f0':'90:e2:ba:2b:3a:00',
                'enp6s0f1':'90:e2:ba:2b:3a:01'}
        env.nm_modules = ['ixgbe']
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.linux_src = os.path.join(env.workdir, 'net-next')
        env.linux_config = 'def'
        env.fbsd_src = os.path.join(env.workdir, 'freebsd')
        env.netmap_src = os.path.join(env.workdir, 'netmap')
        env.linux_ifcmd = {
            'common':[
                'ip link set {} up',
                'ethtool -C {} rx-usecs 1000',
                'ethtool -L {} combined 1'
            ],
            'offload': [
                'ethtool -A {} autoneg off tx off rx off',
                'ethtool -K {} tx on rx on tso on lro on',
                'ethtool -K {} gso on gro on'
            ],
            'onload': [
                'ethtool -A {} autoneg off tx off rx off',
                'ethtool -K {} tx off rx off tso off lro off',
                'ethtool -K {} gso off gro off'
            ],
            'noim': [
                'ethtool -C {} rx-usecs 0'
            ]
        }

    elif name == 'laurel':
        env.nogit=False
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.fbsd_src = os.path.join(env.workdir, 'freebsd')
        env.fbsd_config = 'MUCLAB'
        env.fbsd_target = '/usr/local/muclab/image/{}/freebsd.michio' % env.user
        env.fbsd_install = getattr(operations, 'run')
        env.fbsd_args_in_makefile = True

    elif name == 'netmap':
        env.ifs = ['ix0', 'ix1']
        env.ifs_addr = {'ix0':'10.10.0.1/24', 'ix1':'10.10.2.1'}
        env.ifs_mac = {'ix0':'00:1b:21:d9:17:00', 'ix1':'00:1b:21:d9:17:01'}
        freebsd_defaults()
        env.fbsd_config = 'GENERIC'
        env.nic_profiles = ['common', 'onload']
        env.fbsd_src = os.path.join(env.workdir, 'freebsd')

    elif name == 'netmap3':
        env.nogit=True
        env.workdir = os.path.join(dst_home(env.user), 'deployed')
        env.ifs = ['em1', 'em2']
        env.ifs_addr = {'em1':'10.0.3.2/24', 'em2':'10.0.5.2/24'}
        env.fbsd_nm_modules = ['e1000']
        env.fbsd_src = '/usr/src'
        env.fbsd_config = 'GENERIC-NODEBUG'
        #env.fbsd_config = 'FABRIC'
        env.fbsd_install = getattr(operations, 'sudo')
        env.netmap_src = os.path.join(env.workdir, 'netmap')
        env.freebsd_ifcmd = {
                'common':[
                        'ifconfig {} up',
                ]
        }

    elif name == 'va0':
        env.ifs = ['em0', 'em1', 'em2']
        env.ifs_addr = {'em0':b2b[0][0], 'em1':b2b[1][0], 'em2':'192.168.18.2'}
        env.ifs_mac = {'em0':'08:00:27:ad:47:06', 'em1':'08:00:27:6c:66:20'}
        env.ifs_def_dst_addr = {'em0':b2b[0][1], 'em1':b2b[1][1]}
        env.ifs_def_dst_mac = {'em0':'08:00:27:24:fb:ba',
                'em1':'08:00:27:dc:da:59'}
        env.fbsd_nm_modules = ['e1000', 'ixgbe', 'i40e']
        env.def_sport = def_ports[0]
        env.def_dport = def_ports[1]
        freebsd_defaults()
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

    elif name == 'va1' or name == 'va2':
        linux_defaults(env)
        env.linux_config = 'cur'
        env.ifs = ['eth1', 'eth2', 'eth3']
        env.ifs_addr = {'eth1':b2b[0][1], 'eth2':b2b[1][1],
                'eth3':'192.168.18.4/24'}
        #env.ifs_mac = {'eth1':'08:00:27:24:fb:ba', 'eth2':'08:00:27:dc:da:59'}
        #env.ifs_def_dst_addr = {'eth1':b2b[0][0], 'eth2':b2b[1][0]}
        #env.ifs_def_dst_mac = {'eth1':'00:00:27:18:dd:ff',
        #                        'eth2':'00:00:27:ef:1c:e2'}
        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nm_modules = ['i40e', 'e1000']
        #env.nm_no_ext_drivers = env.nm_modules
        env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum']
        #env.nic_profiles = ['common', 'onload']
        env.no_clflush = True;
        #env.priv_ring_num = 16
        #env.priv_buf_num = 32000
        #env.priv_ring_size = 33024  # accommodate 2048 slots
        env.priv_if_num = 2
        env.priv_ring_num = 2
        env.priv_buf_num = 16
        env.priv_ring_size = 33024  # accommodate 2048 slots

    #elif name == 'va2':
    #    env.ifs = ['em0', 'em1']
    #    env.ifs_addr = {'em0':b2b[0][0], 'em1':b2b[1][0]}
    #    env.ifs_mac = {'em0':'08:00:27:c9:35:47', 'em1':'08:00:27:1d:76:eb'}
    #    env.ifs_def_dst_addr = {'em0':b2b[0][1], 'em1':b2b[1][1]}
    #    env.ifs_def_dst_mac = {'em0':'08:00:27:24:fb:ba',
    #            'em1':'08:00:27:dc:da:59'}
    #    env.fbsd_nm_modules = ['e1000', 'igb', 'ixgbe', 'i40e']
    #    env.def_sport = def_ports[0]
    #    env.def_dport = def_ports[1]
    #    freebsd_defaults()
    #    env.fbsd_config = 'FAB'
    #    env.nic_profiles = ['common', 'onload']

    elif name == 'va3':
        linux_defaults()
        env.ifs = ['eth1']
        #env.ifs_addr = {'eth1':'192.168.18.2'}
        env.ifs_addr = {'eth1':'192.168.11.4/24'}
        env.ifs_mac = {'eth1':'08:00:27:0f:15:fd'}
        #env.ifs_def_dst_addr = {'eth1':b2b[0][0], 'eth2':b2b[1][0]}
        #env.ifs_def_dst_mac = {'eth1':'00:00:27:18:dd:ff',
        #                        'eth2':'00:00:27:ef:1c:e2'}
        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nm_modules = ['e1000', 'i40e', 'ixgbe']
        env.nm_no_ext_drivers = ['i40e', 'ixgbe']
        env.nic_profiles = ['common', 'onload', 'csum']
        #env.nic_profiles = ['common', 'onload']
        env.no_clflush = True;

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

    elif name == 'node0':
        env.home = '/users'
        linux_defaults()
        env.linux_src = os.path.join(dst_home(env.user), 'workspace/linux-4.14')
        env.ifs = ['enp6s0f0']
        env.ifs_addr = {env.ifs[0]:'10.10.1.2/24'}
        env.nm_modules = ['ixgbe']
        env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum', 'singleq', 'noim']
        env.priv_ring_num = 160
        env.priv_buf_num = 640000
        env.priv_ring_size = 33024  # accommodate 2048 slots

    elif name == 'cl0' or name == 'cl1' or name == 'cl2':
        env.home = '/users'
        linux_defaults(env)
        env.linux_config = 'cur'
        env.nopmem = True
        #env.linux_src = ''
        env.ifs = ['ens1f0']
        if name == 'cl2' or name == 'cl3':
            env.ifs = ['enp6s0f0', 'enp6s0f1']
        env.ifs_addr = {env.ifs[0]:b2b_cl[0][0]}
        if name == 'cl1':
            env.ifs_addr = {env.ifs[0]:b2b_cl[0][1]}
        #env.nm_modules = ['i40e']
        #if name == 'cl2':
        #    env.nm_modules = ['ixgbe']
        #env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum', 'singleq', 'noim']
        if name != 'cl0':
            env.nic_profiles = ['common', 'offload', 'csum', 'mq', 'noim']
        if name == 'cl0' or name =='cl2':
            env.priv_if_num = 32
            env.priv_ring_num = 320
            env.priv_buf_num = 400000
            env.priv_ring_size = 33024  # accommodate 2048 slots

    else:
        linux_defaults(env)
        print('No special configuration for {}'.format(name))

    return env
