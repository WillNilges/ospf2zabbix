import json
import requests

# OSPF2ZABBIX
# A simple python program designed to fetch data from the NYC Mesh OSPF API,
# check for hosts that have more than X peers, and add them to Zabbix.

# Overview:
# Fetch raw OSPF JSON
# Turn it into a huge dict of IPs and link counts
# Filter for >link_floor links
# For each link,
#   Check for its existence in Zabbix
#   If doesn't exist
#       Use OSPF to get its host name
#       Call Zabbix API to add a host via SNMP, pass hostname, IP, groups
#           Set up monitoring template, add a Slack alert thingy
# Profit

def extract_routes_count(data):
    routes_count = {}

    areas = data.get('areas', {})
    for area_key, area_value in areas.items():
        routers = area_value.get('routers', {})
        for router_key, router_value in routers.items():
            links = router_value.get('links', {})
            if links.get('router') == None:
                continue
            link_ct = len(links.get('router'))
            print(f"Router: {router_key}, Links: {link_ct}")

def fetch_ospf_json(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return None

def main():
    # URL of the OSPF data 
    url = "http://api.andrew.mesh.nycmesh.net/api/v1/ospf/linkdb"

    # Fetch JSON data from the URL
    try:
        json_data = fetch_ospf_json(url)
    except Exception as e:
        print('An exception occured fetching OSPF data!')
        print(e)
        return

    # Call the function to extract routes count
    extract_routes_count(json_data)

if __name__ == '__main__':
    main()