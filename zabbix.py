import os
import logging
from pyzabbix.api import ZabbixAPI, ZabbixAPIException
from explorer import O2ZExplorer
import snmp

# Template ID names
SNMP_TID = "Network Generic Device by SNMP"
UBIQUITI_AIROS_TID = "Ubiquiti AirOS by SNMP"

AIROS_SNMP_VER = 1
OMNI_SNMP_VER = 2

OMNI_HOSTGROUP = "NYCMeshNodes"
RADIO_HOSTGROUP = "Radios"

class O2ZZabbix:
    def __init__(self):
        zabbix_url = os.getenv("P2Z_ZABBIX_URL")
        zabbix_uname = os.getenv("P2Z_ZABBIX_UNAME")
        zabbix_pword = os.getenv("P2Z_ZABBIX_PWORD")
        if zabbix_url is None or zabbix_uname is None or zabbix_pword is None:
            logging.error(f"Zabbix credentials not provided")
            raise ValueError("Zabbix credentials not provided.")
        logging.info("Logging into zabbix...")
        self.zapi = ZabbixAPI(zabbix_url)
        self.zapi.login(zabbix_uname, zabbix_pword)
        logging.info(f"Logged into zabbix @ {zabbix_url}")

    # Get the hostgroup, and create it if it doesn't exist
    def get_or_create_hostgroup(self, hostgroup):
        try:
            groupid = self.zapi.hostgroup.get(filter={"name": hostgroup})[
                0
            ].get("groupid")
            return groupid
        except (ZabbixAPIException, IndexError):
            logging.warn(f"Did not find host group. Creating {hostgroup}")
            groupid = self.zapi.hostgroup.create(name=hostgroup)[
                "groupids"
            ][0]
            return groupid

    # Get the templateID for the generic SNMP device
    def get_templateid(self, template_name):
        return int(
            self.zapi.template.get(filter={"name": template_name})[
                0
            ].get("templateid")
        )

    # Logic that makes API call to zabbix to enroll a single host
    def enroll_snmp(self, ip, host_name, groupid, templateid, snmp_version):
        # Check if Zabbix already knows about it
        maybe_host = self.zapi.host.get(filter={"host": host_name})

        # Skip it if it already exists in zabbix
        # TODO: Add a "force" option that could overwrite an existing
        # host?
        if len(maybe_host) > 0:
            logging.warning(f"{host_name} ({ip}) already exists. Skipping.")
            return

        new_snmp_host = self.zapi.host.create(
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
                        "version": snmp_version, # 2 if omni, 1 if ubiquiti
                        "bulk": 1,
                        "community": "public",
                    },
                }
            ],
            groups=[
                {
                    "groupid": groupid,
                }
            ],
            templates=[
                {
                    "templateid": templateid,
                }
            ],
        )
        hostid = new_snmp_host["hostids"][0]
        return hostid

    def enroll_single_antenna(self, ip):
        # Get groupid and templateid in preparation
        groupid = self.get_or_create_hostgroup(RADIO_HOSTGROUP)
        templateid = self.get_templateid(UBIQUITI_AIROS_TID)
        host_name = snmp.snmp_get_hostname(ip)
        hostid = self.enroll_snmp(
            ip, host_name, groupid, templateid, UBIQUITI_AIROS_TID
        )
        if hostid is not None:
            logging.info(f"{host_name} ({ip}) enrolled as hostid {hostid}")

    # Enroll a single device in zabbix
    def enroll_single_node(self, ip):
        # Get groupid and templateid in preparation
        omnitik_groupid = self.get_or_create_hostgroup(OMNI_HOSTGROUP)
        omnitik_templateid = self.get_templateid(SNMP_TID)
        host_name = snmp.snmp_get_hostname(ip)
        hostid = self.enroll_snmp(
            ip, host_name, omnitik_groupid, omnitik_templateid, OMNI_SNMP_VER
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
    def enroll_popular_nodes(self, link_floor):
        e = O2ZExplorer()
        # Fetch JSON data from the URL
        logging.info("Getting OSPF Data...")
        try:
            json_data = e.fetch_ospf_json()
        except Exception as err:
            print("An exception occured fetching OSPF data!")
            print(err)
            return

        # Get the number of links that each node has
        route_dict = e.extract_routes_count(json_data)

        # Get groupid and templateid in preparation
        omnitik_groupid = self.get_or_create_hostgroup(OMNI_HOSTGROUP)
        omnitik_templateid = self.get_templateid(SNMP_TID)

        for ip, ct in route_dict.items():
            # Do nothing if the device does not have enough links
            if ct < link_floor:
                continue

            host_name = snmp.snmp_get_hostname(ip)

            logging.info(f"Host: {host_name}, Router: {ip}, Links: {ct}")
            hostid = self.enroll_snmp(
                ip, host_name, omnitik_groupid, omnitik_templateid, OMNI_SNMP_VER
            )
            if hostid is not None:
                logging.info(f"{host_name} enrolled as hostid {hostid}")
