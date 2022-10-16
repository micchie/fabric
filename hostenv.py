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
        'n02': {'enp6s0f0': '192.168.11.153/24', 'enp6s0f1': '192.168.11.154/24'},
        'n03': {'ens2f0': '192.168.11.161/24'},
        'n04': {'enp1s0f0': '192.168.11.163/24'},
        'n05': {'enp1s0f0': '192.168.11.162/24'},
        'n29': {'enp8s0f0np0': '192.168.11.13/24'},
        'n31': {'enp8s0f0np0': '192.168.11.11/24'},
        'n08' : {'ens1f0np0': '192.168.11.12/24'},
        'n33' : {'enp8s0f0np0': '192.168.11.33/24'},
        }
addr_map_freebsd = {
        'n01': {'ixl0': '192.168.11.151/24', 'ixl1': '192.168.11.152/24'},
        }
n01 = {'ens5f0': '192.168.11.151/24', 'ens5f1': '192.168.11.152/24'}
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
    env.nm_modules = ['e1000', 'ixgbe', 'i40e', 'ice']
    env.nm_no_ext_drivers = env.nm_modules
    env.nm_premod = ['mdio']
    env.linux_config = 'def'
    env.ovs_src = os.path.join(env.workdir, 'ovs')
    env.nozstd = False


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
    env.fbsd_config = 'GENERIC-NODEBUG'
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

    if name == 'o02':
        linux_defaults(env)
        env.linux_config = 'cur'
        env.nm_modules = ['ixgbe']
        env.nm_no_ext_drivers = env.nm_modules
        env.nic_profiles = ['common', 'onload', 'csum', 'noim', 'mq']

    elif name in ('n01', 'n02', 'n03', 'n04', 'n05', 'n06', 'n07', 'n08', 'n29', 'n31', 'n33'):
        env.nrings = env.ncpus
        if env.ostype == 'FreeBSD':
            freebsd_defaults(env)
            if name == 'n01':
                env.ifs = ['ixl0', 'ixl1']
            if name in addr_map_freebsd:
                env.ifs_addr = addr_map_freebsd[name]
        else:
            linux_defaults(env)
            env.linux_config = 'cur'
            if name == 'n01':
                env.ifs = ['ens1f0']
            elif name == 'n02':
                env.ifs = ['enp6s0f0', 'enp6s0f1']
            elif name in ['n04', 'n05', 'n06', 'n07']:
                env.ifs = ['enp1s0f0']
            else:
                env.ifs = list(addr_map[name].keys())

            if name in addr_map:
                env.ifs_addr = addr_map[name]

        #env.nm_modules = ['ixgbe', 'i40e']
        if name == 'n06' or name == 'n07':
            env.nm_modules = ['ixgbe']
        else:
            env.nm_modules = ['i40e']
        env.nm_no_ext_drivers = env.nm_modules
        #if name == 'n01' or name == 'n04' or name == 'n06':
        if name == 'n04' or name == 'n06':
            env.nic_profiles = ['common', 'singleq', 'onload', 'csum', 'noim']
        else:
            env.nic_profiles = ['common', 'offload', 'csum', 'noim']

    elif name in ('ub22', 'ub22-2'):
        linux_defaults(env)
        env.nozstd = True

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
