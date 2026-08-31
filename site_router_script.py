import sys
import pandas as pd
import textwrap

ip_data = pd.read_csv('ip_data.csv')
vrf_data = pd.read_csv('vrf_data.csv')
tunnel_data = pd.read_csv('tunnel_data.csv')

out_file = sys.argv[1]
sn = input("Hva er site nummret: ")
router_id = ".".join([sn, sn, sn, "0"])
print(router_id)

def ms(ms):
    return textwrap.dedent(ms)

out_data = ms(f"""\
    interface loopback0
        ip address {router_id} 255.255.255.255
    exit
    """)

def create_vrf(vrf_data):
    out = ""
    
    for index, row in vrf_data.iterrows():
        vrf_name = row['vrf']
        vrf_rd = row['rd']
        vrf_loopback = row['loopback']
        vrf_laddr= row['laddr']

        print(f"Creating VRF: {vrf_name} with RD: {vrf_rd}")
        out += ms(f"""\
        interface loopback{vrf_loopback}
            ip vrf forwarding {vrf_name}
            ip address {vrf_laddr} 255.255.255.255
        exit
        ip vrf {vrf_name}
            rd {vrf_rd}
            route-target export {vrf_rd}
            route-target import {vrf_rd}
        exit
        """)
    return out


def create_interface(ip_data):
    out = ""
    intf_s = list(ip_data['interface'])
    
    for index, row in ip_data.iterrows():
        vrf = row['vrf']
        vlan = row['vlan']

        intf = row['interface']
        sub = True if intf_s.count(intf) > 1 else False

        ip_address = row['address min']
        mask = row['mask']

        print(f"Creating Interface for VRF: {vrf} with IP: {ip_address} and Mask: {mask}")
        out += ms(f"""\
        interface g0/{f'{intf}.{vlan}' if sub else intf}
            ip vrf forwarding {vrf}
            ip address {ip_address} {mask}
            no shutdown
        exit
        """)
    return out


out_data += create_vrf(vrf_data)
out_data += create_interface(ip_data)

with open(out_file, 'w') as f:
    f.write(out_data)