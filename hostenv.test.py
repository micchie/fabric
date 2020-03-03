import os

b2b = [('192.168.%d.2/24' % (11+i) , '192.168.%d.3/24' % (11+i)) for i in
        range(4)]
def_ports = [50000, 60000]

def dst_home(user, env):
    if user == 'root':
        return '/root'
    if 'home' in env:
        return os.path.join(env.home, user)
    return os.path.join('/home/', user)

def linux_defaults(env):
    #
    # default values for Linux hosts
    #
    env.nogit = True
    if 'workdir' not in env:
        env.workdir = os.path.join(dst_home(env.user, env), 'deployed')
    env.linux_src = os.path.join(env.workdir, 'net-next')
    env.netmap_src = os.path.join(env.workdir, 'netmap')
    env.nm_modules = ['e1000', 'ixgbe'] # temporary opt out i40e for 4.12
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
            'ip link set %s up',
            'ip link set %s promisc on',
            'ethtool -A %s autoneg off tx off rx off',
        ],
        'offload': [
            'ethtool -K %s tx on rx on tso on lro on',
            'ethtool -K %s gso on gro on',
        ],
        'onload': [
            'ethtool -K %s tx off rx off tso off lro off',
            'ethtool -K %s tx off rx off tso off',

            'ethtool -K %s gso off gro off',
        ],
        'csum': [
            'ethtool -K %s tx-checksum-ip-generic on',
            'ethtool -K %s tx-checksum-ipv4 on', # i40e
        ],
        'noim': [
            'ethtool -C %s rx-usecs 0',
            'ethtool -C %s adaptive-rx off adaptive-tx off rx-usecs 0 tx-usecs 0 rx-usecs-irq 0 tx-usecs-irq 0 rx-frames 0 tx-frames 0',
        ],
        'busywait': [
            'ethtool -C %s rx-usecs 1022',
            'ethtool -C %s adaptive-rx off adaptive-tx off rx-usecs 0 tx-usecs 0 rx-frames-irq 1 tx-frames-irq 1',
            # *-usecs supports up to 8160 for i40e
            'ethtool -C %s adaptive-rx off adaptive-tx off rx-usecs 1022 tx-usecs 1022 rx-usecs-irq 1022 tx-usecs-irq 1022 rx-frames 10000 tx-frames 10000',
        ],
        'singleq': [
            'ethtool -L %s combined 1',
        ],
        'mq2': [
            'ethtool -L %s combined 2',
        ],
        'mq3': [
            'ethtool -L %s combined 3',
        ],
        'mq4': [
            'ethtool -L %s combined 4',
        ],
        'mq5': [
            'ethtool -L %s combined 5',
        ],
        'mq6': [
            'ethtool -L %s combined 6',
        ],
        'mq7': [
            'ethtool -L %s combined 7',
        ],
        'mq8': [
            'ethtool -L %s combined 8',
        ],
        'mq9': [
            'ethtool -L %s combined 9',
        ],
        'mq10': [
            'ethtool -L %s combined 10',
        ],
    }

def hostenv(env, name):
    if name == 'va1' or name == 'va2':
        linux_defaults(env)
        env.ifs = ['eth1', 'eth2', 'eth3']
        env.ifs_addr = {'eth1':b2b[0][1], 'eth2':b2b[1][1],
                'eth3':'192.168.18.4/24'}
        env.def_sport = def_ports[1]
        env.def_dport = def_ports[0]
        env.nm_modules = ['i40e', 'e1000']
        env.nm_no_ext_drivers = ['i40e']
        env.nic_profiles = ['common', 'onload', 'csum']
        #env.nic_profiles = ['common', 'onload']
        env.no_clflush = True;
        env.priv_ring_num = 16
        env.priv_buf_num = 32000
        env.priv_ring_size = 33024  # accommodate 2048 slots
    return env
