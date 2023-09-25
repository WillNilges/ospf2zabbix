#!/usr/bin/env python3
import os
import logging
import argparse
from dotenv import load_dotenv
import json
import requests
import socket
from pyzabbix import ZabbixAPI, ZabbixAPIException
from pysnmp.hlapi import *
#from flappiest import connect_to_db, get_noisiest_triggers
import flappiest as fl

# OSPF2ZABBIX
# A simple python program designed to fetch data from the NYC Mesh OSPF API,
# check for hosts that have more than X peers, and add them to Zabbix.

# FIXME: I need to get my terminology straight. Is it a "link?" is it a "route?"
# Does the API call it something different from what it actually is?


# Custom validation function to check if the provided argument is a valid IPv4 address
def is_valid_ipv4(ip):
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except socket.error:
        return False


# FIXME: This doesn't seem to exactly match up with what the explorer says.
# probably need to sync up with andrew and see what counts as a 'route'
def extract_routes_count(data):
    routes_count = {}

    areas = data.get("areas", {})
    for area_key, area_value in areas.items():
        routers = area_value.get("routers", {})
        for router_ip, router_info in routers.items():
            links = router_info.get("links", {})
            if links.get("router") == None:
                continue
            link_ct = len(links.get("router"))
            routes_count[router_ip] = link_ct
    return routes_count


def fetch_ospf_json(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return None


def snmp_get(host, oid):
    for errorIndication, errorStatus, errorIndex, varBinds in getCmd(
        SnmpEngine(),
        CommunityData("public", mpModel=0),
        UdpTransportTarget((host, 161)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lookupMib=False,
        lexicographicMode=False,
    ):
        if errorIndication:
            logging.error(errorIndication)
            break

        elif errorStatus:
            logging.error(
                "%s at %s"
                % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                )
            )
            break

        else:
            for varBind in varBinds:
                return varBind


# Get SNMP info from router
def snmp_get_hostname(ip):
    snmp_host_name = "1.3.6.1.2.1.1.5.0"
    return snmp_get(ip, snmp_host_name)[1].prettyPrint()


# Get the hostgroup, and create it if it doesn't exist
def get_or_create_hostgroup(zapi):
    nycmesh_node_hostgroup = "NYCMeshNodes"
    try:
        groupid = zapi.hostgroup.get(filter={"name": nycmesh_node_hostgroup})[0].get(
            "groupid"
        )
        return groupid
    except (ZabbixAPIException, IndexError):
        logging.warn(f"Did not find host group. Creating {nycmesh_node_hostgroup}")
        groupid = zapi.hostgroup.create(name=nycmesh_node_hostgroup)["groupids"][0]
        return groupid


# Get the templateID for the generic SNMP device
def get_generic_snmp_templateid(zapi):
    return int(
        zapi.template.get(filter={"name": "Network Generic Device by SNMP"})[0].get(
            "templateid"
        )
    )


# Logic that makes API call to zabbix to enroll a single host
def zabbix_enroll_node(zapi, ip, host_name, omnitik_groupid, omnitik_templateid):
    # Check if Zabbix already knows about it
    maybe_host = zapi.host.get(filter={"host": host_name})

    # Skip it if it already exists in zabbix
    # TODO: Add a "force" option that could overwrite an existing
    # host?
    if len(maybe_host) > 0:
        logging.warning(f"{host_name} ({ip}) already exists. Skipping.")
        return

    new_snmp_host = zapi.host.create(
        host=host_name,
        interfaces=[
            {
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
            }
        ],
        groups=[
            {
                "groupid": omnitik_groupid,
            }
        ],
        templates=[
            {
                "templateid": omnitik_templateid,
            }
        ],
    )
    hostid = new_snmp_host["hostids"][0]
    return hostid


# Enroll a single device in zabbix
def enroll_device(zapi, ip):
    # Get groupid and templateid in preparation
    omnitik_groupid = get_or_create_hostgroup(zapi)
    omnitik_templateid = get_generic_snmp_templateid(zapi)
    host_name = snmp_get_hostname(ip)
    hostid = zabbix_enroll_node(
        zapi, ip, host_name, omnitik_groupid, omnitik_templateid
    )
    if hostid is not None:
        logging.info(f"{host_name} ({ip}) enrolled as hostid {hostid}")


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
def enroll_popular_devices(zapi, ospf_api_url, link_floor):
    # Fetch JSON data from the URL
    logging.info("Getting OSPF Data...")
    try:
        json_data = fetch_ospf_json(ospf_api_url)
    except Exception as err:
        print("An exception occured fetching OSPF data!")
        print(err)
        return

    # Get the number of links that each node has
    route_dict = extract_routes_count(json_data)

    # Get groupid and templateid in preparation
    omnitik_groupid = get_or_create_hostgroup(zapi)
    omnitik_templateid = get_generic_snmp_templateid(zapi)

    for ip, ct in route_dict.items():
        # Do nothing if the device does not have enough links
        if ct < link_floor:
            continue

        host_name = snmp_get_hostname(ip)

        logging.info(f"Host: {host_name}, Router: {ip}, Links: {ct}")
        hostid = zabbix_enroll_node(
            zapi, ip, host_name, omnitik_groupid, omnitik_templateid
        )
        if hostid is not None:
            logging.info(f"{host_name} enrolled as hostid {hostid}")


def main():
    load_dotenv()
    ospf_api_url = os.getenv("P2Z_OSPF_API_URL")
    link_floor = int(os.getenv("P2Z_LINK_FLOOR"))
    zabbix_url = os.getenv("P2Z_ZABBIX_URL")
    zabbix_uname = os.getenv("P2Z_ZABBIX_UNAME")
    zabbix_pword = os.getenv("P2Z_ZABBIX_PWORD")

    logging.basicConfig(level=logging.INFO)

    # Login to zabbix
    logging.info("Logging into zabbix...")
    zapi = ZabbixAPI(zabbix_url)
    zapi.login(zabbix_uname, zabbix_pword)
    logging.info(f"Logged into zabbix @ {zabbix_url}")

    parser = argparse.ArgumentParser(
        description="Automation and management tools for NYCMesh Zabbix"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--popular", action="store_true", help="Enroll popular routers into Zabbix"
    )
    group.add_argument(
        "--enroll",
        metavar="ip",
        help="Enroll a specific node into zabbix",
    )
    parser.add_argument( # TODO: have option to adjust how many triggers you get
        "--get-noisy-triggers", action="store_true", help="Query the Zabbix DB for noisy triggers"
    )
    args = parser.parse_args()

    if args.popular:
        enroll_popular_devices(zapi, ospf_api_url, link_floor)
    elif args.enroll:
        if not is_valid_ipv4(args.enroll):
            raise ValueError("Must pass a valid IPv4 address!")
        enroll_device(zapi, args.enroll)
    elif args.get_noisy_triggers:
        conn = fl.connect_to_db()
        fl.get_noisiest_triggers(conn)
        conn.close()


if __name__ == "__main__":
    main()
