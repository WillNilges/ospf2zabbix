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
import triggers as fl
import bucket as b
import slack as s

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
    enrolling_link_floor = int(os.getenv("P2Z_LINK_FLOOR", default=10))
    zabbix_url = os.getenv("P2Z_ZABBIX_URL")
    zabbix_uname = os.getenv("P2Z_ZABBIX_UNAME")
    zabbix_pword = os.getenv("P2Z_ZABBIX_PWORD")
    noisy_days_ago = int(os.getenv("P2Z_NOISY_DAYS_AGO", default=7))
    noisy_leaderboard = int(os.getenv("P2Z_NOISY_LEADERBOARD", default=20))

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Automation and management tools for NYCMesh Zabbix"
    )

    subparsers = parser.add_subparsers(
        help="Zabbix shenanigans to perform", dest="subcommand", required=True
    )

    popular_parser = subparsers.add_parser(
        "enroll-popular", help="Enroll popular routers into Zabbix"
    )
    popular_parser.add_argument(
        "--link-floor",
        type=int,
        default=enrolling_link_floor,
        help="The minimum amount of links a node must have to be added. Defaults to 10",
    )

    enroll_parser = subparsers.add_parser(
        "enroll-device", help="Enroll a specific node into Zabbix by IP"
    )
    enroll_parser.add_argument("ip", type=str, help="IP of node to enroll")

    triggers_parser = subparsers.add_parser(
        "noisy-triggers", help="Query the Zabbix DB directly for noisy triggers"
    )
    triggers_parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish reports (csv file and PrettyTable) of noisy triggers to an S3 Bucket",
    )
    triggers_parser.add_argument(
        "--slack",
        action="store_true",
        help="Publish table of noisy triggers to Slack",
    )
    triggers_parser.add_argument(
        "--days-ago",
        type=int,
        default=noisy_days_ago,
        help="# of days ago to query for triggers",
    )
    triggers_parser.add_argument(
        "--leaderboard",
        type=int,
        default=noisy_leaderboard,
        help="# of days ago to query for triggers",
    )

    bucket_parser = subparsers.add_parser("bucket", help="S3 Bucket helper functions")
    bucket_parser.add_argument(
        "--object",
        type=str,
        help="Path to an S3 object",
    )

    slack_parser = subparsers.add_parser("slack", help="Slack helper functions")
    slack_parser.add_argument(
        "--delete",
        type=str,
        help="Deletes a message from the bot",
    )

    args = parser.parse_args()

    # Login to zabbix
    logging.info("Logging into zabbix...")
    zapi = ZabbixAPI(zabbix_url)
    zapi.login(zabbix_uname, zabbix_pword)
    logging.info(f"Logged into zabbix @ {zabbix_url}")

    logging.debug(args)

    if args.subcommand == "enroll-popular":
        enroll_popular_devices(zapi, ospf_api_url, args.link_floor)
    elif args.subcommand == "enroll-device":
        if not is_valid_ipv4(args.ip):
            raise ValueError("Must pass a valid IPv4 address!")
        enroll_device(zapi, args.ip)
    elif args.subcommand == "noisy-triggers":
        conn = fl.connect_to_db()

        noisiest_triggers = fl.get_noisiest_triggers(
            conn, get_or_create_hostgroup(zapi), args.days_ago, args.leaderboard
        )
        conn.close()

        leaderboard_title = (
            f"{args.leaderboard} Noisiest Triggers from the last {args.days_ago} days"
        )
        noisiest_triggers_pretty = fl.pretty_print_noisiest_triggers(noisiest_triggers)
        noisiest_triggers_pretty = f"{leaderboard_title}\n{noisiest_triggers_pretty}"
        print(noisiest_triggers_pretty)

        if args.publish:
            s3 = b.O2ZBucket()
            s3.publish_noise_reports(noisiest_triggers, noisiest_triggers_pretty)

        if args.slack:
            slack = s.O2ZSlack()
            slack.publish_noise_reports(noisiest_triggers_pretty)

    elif args.subcommand == "bucket":
        s3 = b.O2ZBucket()

        if args.object:
            s3.print_objects(args.object)
            return

        s3.list_objects()
    
    elif args.subcommand == "slack":
        slack = s.O2ZSlack()
        if args.delete:
            slack.delete_report(args.delete)


if __name__ == "__main__":
    main()
