import os
import logging
from dotenv import load_dotenv
import json
import requests
import argparse
from pyzabbix import ZabbixAPI
from pysnmp.hlapi import *

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
#           Add some kind of annotation for common name, "Grand St, SN3, etc"
# Profit

# FIXME: I need to get my terminology straight. Is it a "link?" is it a "route?"
# Does the API call it something different from what it actually is?

# FIXME: This doesn't seem to exactly match up with what the explorer says.
# probably need to sync up with andrew and see what counts as a 'route'
def extract_routes_count(data):
    routes_count = {}

    areas = data.get('areas', {})
    for area_key, area_value in areas.items():
        routers = area_value.get('routers', {})
        for router_ip, router_info in routers.items():
            links = router_info.get('links', {})
            if links.get('router') == None:
                continue
            link_ct = len(links.get('router'))
            routes_count[router_ip] = link_ct
    return routes_count

def fetch_ospf_json(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Failed to fetch data. Status code: {response.status_code}')
        return None

def snmp_get(host, oid):

    for (errorIndication,
         errorStatus,
         errorIndex,
         varBinds) in getCmd(SnmpEngine(),
                             CommunityData('public', mpModel=0),
                             UdpTransportTarget((host, 161)),
                             ContextData(),
                             ObjectType(ObjectIdentity(oid)),
                             lookupMib=False,
                             lexicographicMode=False):

        if errorIndication:
            logging.error(errorIndication)
            break

        elif errorStatus:
            logging.error('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
            break

        else:
            for varBind in varBinds:
                return varBind

def main():
    load_dotenv()
    ospf_api_url = os.getenv('P2Z_OSPF_API_URL')
    link_floor = int(os.getenv('P2Z_LINK_FLOOR'))
    zabbix_url = os.getenv('P2Z_ZABBIX_URL')
    zabbix_uname = os.getenv('P2Z_ZABBIX_UNAME')
    zabbix_pword = os.getenv('P2Z_ZABBIX_PWORD')

    logging.basicConfig(level=logging.INFO)

    # Fetch JSON data from the URL
    logging.info("Getting OSPF Data...")
    try:
        json_data = fetch_ospf_json(ospf_api_url)
    except Exception as e:
        print('An exception occured fetching OSPF data!')
        print(e)
        return

    # Get the number of links that each node has
    route_dict = extract_routes_count(json_data)

    # Login to zabbix
    logging.info("Logging into zabbix...")
    zapi = ZabbixAPI(zabbix_url)
    zapi.login(zabbix_uname, zabbix_pword)
    logging.info(f"Logged into zabbix @ {zabbix_url}")

    parser = argparse.ArgumentParser(description='Automation and management tools for NYCMesh Zabbix')
    parser.add_argument('--enroll', action='store_true', help='Enroll popular routers into Zabbix')
    parser.add_argument('--silence-alerts', action='store_true', help='Silence useless alerts')
    args = parser.parse_args()

    if args.enroll:
        for ip, ct in route_dict.items():
            # Do nothing if the device does not have enough links
            if ct < link_floor:
                continue

            # Get SNMP info from router
            snmp_host_name = '1.3.6.1.2.1.1.5.0'
            host_name = snmp_get(ip, snmp_host_name)[1].prettyPrint()

            logging.info(f'Host: {host_name}, Router: {ip}, Links: {ct}')

            # Check if Zabbix already knows about it
            maybe_host = zapi.host.get(filter={"host": host_name})

            # Skip it if it already exists in zabbix
            # TODO: Add a "force" option that could overwrite an existing
            # host?
            if len(maybe_host) > 0:
                logging.warning(f'{host_name} ({ip}) already exists. Skipping.')
                continue

            omnitik_hostgroup_groupid = zapi.hostgroup.get(
                filter={'name': 'OmniTik'}
            )[0].get('groupid')

            omnitik_template_templateid = int(zapi.template.get(
                filter={'name': 'Network Generic Device by SNMP'}
            )[0].get('templateid'))

            new_snmp_host = zapi.host.create(
                host= host_name,
                interfaces=[{
                    "type": 2,
                    "main": 1,
                    "useip": 1,
                    "ip": ip,
                    "dns": "",
                    "port": 161,
                    "details": {
                        "version": 2,
                        "bulk": 1,
                        "community": "public",
                    },
                }],
                groups=[{
                    "groupid": omnitik_hostgroup_groupid,
                }],
                templates=[{
                    'templateid': omnitik_template_templateid,
                }]
            )
            logging.info(f"Created as hostid {new_snmp_host['hostids'][0]}")


if __name__ == '__main__':
    main()
