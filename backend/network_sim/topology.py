#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.log import setLogLevel

def run():
    net = Mininet(switch=OVSBridge, controller=None)
    h1 = net.addHost('h1', ip='10.0.0.1/24')  # attacker
    h2 = net.addHost('h2', ip='10.0.0.2/24')  # victim (your site)
    s1 = net.addSwitch('s1')
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.start()
    # offloading makes Suricata see bad checksums on virtual links
    for intf in ('s1-eth1', 's1-eth2'):
        s1.cmd(f'ethtool -K {intf} tx off rx off gro off gso off tso off')
    for h in (h1, h2):
        h.cmd(f'ethtool -K {h.defaultIntf()} tx off rx off gro off gso off tso off')
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    run()