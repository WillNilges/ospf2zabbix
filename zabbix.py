import os
import logging
from pyzabbix.api import ZabbixAPI, ZabbixAPIException
from explorer import O2ZExplorer
import snmp

class O2ZZabbix():
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
    def get_or_create_hostgroup(self):
        nycmesh_node_hostgroup = "NYCMeshNodes"
        try:
            groupid = self.zapi.hostgroup.get(filter={"name": nycmesh_node_hostgroup})[0].get(
                "groupid"
            )
            return groupid
        except (ZabbixAPIException, IndexError):
            logging.warn(f"Did not find host group. Creating {nycmesh_node_hostgroup}")
            groupid = self.zapi.hostgroup.create(name=nycmesh_node_hostgroup)["groupids"][0]
            return groupid


    # Get the templateID for the generic SNMP device
    def get_generic_snmp_templateid(self):
        return int(
            self.zapi.template.get(filter={"name": "Network Generic Device by SNMP"})[0].get(
                "templateid"
            )
        )


    # Logic that makes API call to zabbix to enroll a single host
    def zabbix_enroll_node(self, ip, host_name, omnitik_groupid, omnitik_templateid):
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
    def enroll_device(self, ip):
        # Get groupid and templateid in preparation
        omnitik_groupid = self.get_or_create_hostgroup()
        omnitik_templateid = self.get_generic_snmp_templateid()
        host_name = snmp.snmp_get_hostname(ip)
        hostid = self.zabbix_enroll_node(
            ip, host_name, omnitik_groupid, omnitik_templateid
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
    def enroll_popular_devices(self, link_floor):
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
        omnitik_groupid = self.get_or_create_hostgroup()
        omnitik_templateid = self.get_generic_snmp_templateid()

        for ip, ct in route_dict.items():
            # Do nothing if the device does not have enough links
            if ct < link_floor:
                continue

            host_name = snmp.snmp_get_hostname(ip)

            logging.info(f"Host: {host_name}, Router: {ip}, Links: {ct}")
            hostid = self.zabbix_enroll_node(
                ip, host_name, omnitik_groupid, omnitik_templateid
            )
            if hostid is not None:
                logging.info(f"{host_name} enrolled as hostid {hostid}")


