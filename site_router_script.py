import sys
import json
import pandas as pd

ip_data = pd.read_csv(sys.argv[1])
vrf_data = pd.read_csv(sys.argv[2])
tunnel_data = pd.read_csv(sys.argv[3])

my_data = {}
my_data["config"] = {}
my_data["network_info"] = {}

config_file = f"sites_config.json"
try:
    data = {}
    with open(config_file, 'r') as f:
        try:
            data = json.load(f)
            is_hub = False
        except json.JSONDecodeError:
            data = {}
            is_hub = True
except FileNotFoundError:
    data = {}
    is_hub = True

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
my_data["config"]["interface loopback0"].append(f"exit")

intf_s = []
intf_s.append("ip address dhcp")
intf_s.append("ip ospf 1 area 0")
intf_s.append("mpls ip")
intf_s.append("no shutdown")
intf_s.append("exit")
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
        vrf_s.append(f"exit")
        my_data["config"][f"ip vrf {vrf_name}"] = vrf_s
        intf_s = []
        intf_s.append(f"ip vrf forwarding {vrf_name}")
        intf_s.append(f"ip address {vrf_laddr} 255.255.255.255")
        intf_s.append(f"exit")
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
        intf_s.append("exit")
        my_data["config"][f"interface {intf_prefix}{intf}.{vlan}" if sub else f"interface {intf_prefix}{intf}"] = intf_s

    return my_data

def create_mp_bgp_config(vrf_data, ip_data, sites_data, router_id):
    my_data = {}
    my_data["config"] = {}
    my_data["network_info"] = {}

    # Example logic for creating MP-BGP config
    bgp_s = []
    vpnv4_s= []
   
    rd = list(vrf_data.iterrows())[0][1]['rd']
         
    as_num = rd.split(":")[0]
        
    tmp = f"neighbor {router_id} remote-as {as_num}"
    tmp2 = f"neighbor {router_id} update-source loopback0"
    vpn_tmp = f"neighbor {router_id} activate"
    vpn_tmp2 = f"neighbor {router_id} send-community extended"
    for site, site_data in sites_data.items():
        net_info = site_data["network_info"]
        loop0 = net_info[f"loopback0"]
        
        bgp_s.append(f"neighbor {loop0['address']} remote-as {as_num}")
        bgp_s.append(f"neighbor {loop0['address']} update-source loopback0")

        vpnv4_s.append(f"neighbor {loop0['address']} activate")
        vpnv4_s.append(f"neighbor {loop0['address']} send-community extended")

        # update BGP neighbor configuration for each site

        sites_data[site]["config"][f"ip router bgp {as_num}"].insert(0, tmp)
        sites_data[site]["config"][f"ip router bgp {as_num}"].insert(1, tmp2)

        sites_data[site]["config"][f"ip router bgp {as_num}"][-3][f"address-family vpnv4"].insert(0, vpn_tmp)
        sites_data[site]["config"][f"ip router bgp {as_num}"][-3][f"address-family vpnv4"].insert(1, vpn_tmp2)

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
    
    return my_data, sites_data

def create_tunnel_config(tunnel_data, sites_data: dict, is_hub: bool):
    my_data = {}
    my_data["network_info"] = {}
    my_data["config"] = {}

    if is_hub:
        hub_data = {}
    else:
        hub_data = list(sites_data.values())[0]["network_info"]

    for idx, row in tunnel_data.iterrows():
        tunnel= row['tunnel id']
        mode = row['gre mode']
        ip_address = row['ip address']
        mask = row['mask']
        vrf = row['vrf']
        source = row['source']
        network_id = row['network-id']

        if mode != "multipoint":
            destination = row['destination']


        tunnel_info = {
            "is hub": is_hub,
            "vrf": vrf,
            "ip address": ip_address,
            "mask": mask,
            "source": source,
            "tunnel id": tunnel,
            "mode": mode,
        }

        my_data["network_info"][tunnel] = tunnel_info

        tun_s = []
        tun_s.append(f"ip vrf forwarding {vrf}")
        tun_s.append(f"ip address {ip_address} mask {mask}")
        tun_s.append(f"tunnel source {source}")

        if mode == "multipoint":
            tun_s.append(f"tunnel mode gre {mode}")
            if not is_hub:
                hub_tun_ip = hub_data.get(tunnel, {}).get("ip address", "")
                hub_source = hub_data.get(tunnel, {}).get("source", "")

                tun_s.append(f"ip nhrp map {hub_tun_ip} {hub_source}")
                tun_s.append(f"ip nhrp map multicast {hub_source}")
                tun_s.append(f"ip nhrp network-id {network_id}")
                tun_s.append(f"ip nhrp nhs {hub_tun_ip}")
        else:
            print(f"Mode må være multipoint for tunnel {tunnel}")

        tun_s.append("exit-tunnel")
        my_data["config"][f"interface {tunnel}"] = tun_s
        my_data["network_info"][tunnel] = tunnel_info

    return my_data

d_vrf = create_vrf(vrf_data)
my_data["config"].update(d_vrf["config"])
my_data["network_info"].update(d_vrf["network_info"])

d_ip = create_interface(ip_data, intf_prefix)
my_data["config"].update(d_ip["config"])
my_data["network_info"].update(d_ip["network_info"])

d_bgp, data = create_mp_bgp_config(vrf_data, ip_data, data, router_id)
my_data["config"].update(d_bgp["config"])

d_tunnel = create_tunnel_config(tunnel_data, data, is_hub)
my_data["config"].update(d_tunnel["config"])
my_data["network_info"].update(d_tunnel["network_info"])

with open(config_file, 'w') as f:
    my_data["intf_prefix"] = intf_prefix
    data[f"site {sn}"] = my_data

    for site, site_data in data.items():
        config = site_data["config"]
        stringV = json.dumps(config)
        stringV = stringV.replace("[", "\n")
        stringV = stringV.replace("]", "")
        stringV = stringV.replace("(", "")
        stringV = stringV.replace(")", "")
        stringV = stringV.replace(",", "\n")
        stringV = stringV.replace("\":", "\n")
        stringV = stringV.replace("\"", "")
        stringV = stringV.replace("{", "\n")
        stringV = stringV.replace("}", "")
        print(stringV)


    json.dump(data, f, indent=4)

with open("config_file.txt", "w") as f:
    f.write(stringV)