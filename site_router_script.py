import sys
import pandas as pd
import textwrap
import json

ip_data = pd.read_csv('ip_data.csv')
vrf_data = pd.read_csv('vrf_data.csv')
tunnel_data = pd.read_csv('tunnel_data.csv')

my_data = {}
my_data["config"] = {}
my_data["network_info"] = {}

config_file = f"sites_config.json"
try:
    data = {}
    with open(config_file, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
except FileNotFoundError:
    data = {}

while True:
    try:
        sn = int(input("Hva er site nummret: "))
    except ValueError:
        print("Vennligst skriv inn et gyldig tall for site nummeret.")
        continue
    break
router_id = ".".join([str(sn), str(sn), str(sn), "0"])
intf_prefix = input("Hva er interface prefikset for routeren, f.eks. g0/: ")
print(router_id)

ospf_s = []
ospf_s.append(f"router-id {router_id}")
my_data["config"]["router ospf 1"] = ospf_s

my_data["config"]["interface loopback0"] = []
my_data["config"]["interface loopback0"].append(f"ip address {router_id} 255.255.255.255")

intf_s = []
intf_s.append("ip address dhcp")
intf_s.append("ip ospf 1 area 0")
intf_s.append("mpls ip")
intf_s.append("no shutdown")
my_data["config"][f"interface {intf_prefix}/1"] = intf_s

my_data["network_info"]["loopback0"] = {
    "address": router_id,
    "mask": "255.255.255.255"
}


def create_vrf(vrf_data):
    my_data = {}
    my_data["config"] = {}
    my_data["network_info"] = {}
    
    for index, row in vrf_data.iterrows():
        vrf_name = row['vrf']
        vrf_rd = row['rd']
        vrf_loopback = row['loopback']
        vrf_laddr= row['laddr']
        my_data["network_info"][vrf_name] = {
            "rd": vrf_rd,
            "loopback": vrf_loopback,
            "laddr": vrf_laddr
        }

        print(f"lager VRF: {vrf_name} med RD: {vrf_rd}")
        vrf_s = []
        vrf_s.append(f"rd {vrf_rd}")
        vrf_s.append(f"route-target export {vrf_rd}")
        vrf_s.append(f"route-target import {vrf_rd}")
        my_data["config"][f"ip vrf {vrf_name}"] = vrf_s
        intf_s = []
        intf_s.append(f"ip vrf forwarding {vrf_name}")
        intf_s.append(f"ip address {vrf_laddr} 255.255.255.255")
        my_data["config"][f"interface loopback{vrf_loopback}"] = intf_s
        
    return my_data


def create_interface(ip_data, intf_prefix):
    my_data = {}
    my_data["config"] = {}
    my_data["network_info"] = {}
    intf_nums = list(ip_data['interface'])
    
    for index, row in ip_data.iterrows():
        vrf = row['vrf']
        vlan = row['vlan']

        intf = row['interface']
        sub = True if intf_nums.count(intf) > 1 else False

        ip_address = row['address min']
        mask = row['mask']
        my_data["network_info"][f"{intf_prefix}{intf}.{vlan}" if sub else f"{intf_prefix}{intf}"] = {
            "vrf": vrf,
            "vlan": vlan,
            "interface": intf,
            "sub": sub,
            "address": ip_address,
            "mask": mask
        }

        print(f"lager Interface for VRF: {vrf} med IP: {ip_address} og Mask: {mask}")
        intf_s = []
        intf_s.append(f"ip vrf forwarding {vrf}")
        intf_s.append(f"ip address {ip_address} {mask}")
        intf_s.append("no shutdown")
        my_data["config"][f"interface {intf_prefix}{intf}.{vlan}" if sub else f"interface {intf_prefix}{intf}"] = intf_s

    return my_data

def create_mp_bgp_config(vrf_data, ip_data, sites_data):
    my_data = {}
    my_data["config"] = {}
    my_data["network_info"] = {}

    # Example logic for creating MP-BGP config
    bgp_s = []
    vpnv4_s= []
   
    rd = list(vrf_data.iterrows())[0][1]['rd']
    print(f"Using RD: {rd}")
         
    as_num = rd.split(":")[0]
        
    for site, site_data in sites_data.items():
        net_info = site_data["network_info"]
        loop0 = net_info[f"loopback0"]
        
        bgp_s.append(f"neighbor {loop0['address']} remote-as {as_num}")
        bgp_s.append(f"neighbor {loop0['address']} update-source loopback0")

        vpnv4_s.append(f"neighbor {loop0['address']} activate")
        vpnv4_s.append(f"neighbor {loop0['address']} send-community extended")

    vpnv4_s.append("exit-address-family")
    bgp_s.append({f"address-family vpnv4": vpnv4_s})

    for index, row in ip_data.iterrows():
        ipv4_s = []
        vrf = row['vrf']
        if vrf == "UNET":
            continue

        network = row['nett id']
        mask = row['mask']
        ipv4_s.append(f"network {network} mask {mask}")
        ipv4_s.append("exit-address-family")
        
        bgp_s.append({f"address-family ipv4 vrf {vrf}": ipv4_s})

    my_data["config"][f"ip router bgp {as_num}"] = bgp_s
    
    return my_data

d_vrf = create_vrf(vrf_data)
my_data["config"].update(d_vrf["config"])
my_data["network_info"].update(d_vrf["network_info"])

d_ip = create_interface(ip_data, intf_prefix)
my_data["config"].update(d_ip["config"])
my_data["network_info"].update(d_ip["network_info"])

d_bgp = create_mp_bgp_config(vrf_data, ip_data, data)
my_data["config"].update(d_bgp["config"])

with open(config_file, 'w') as f:
    my_data["intf_prefix"] = intf_prefix
    data[f"site {sn}"] = my_data
    json.dump(data, f, indent=4)