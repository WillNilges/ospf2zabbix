import logging
from pysnmp.hlapi import *


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
    data = snmp_get(ip, snmp_host_name)
    if data is not None:
        return data[1].prettyPrint()
    logging.error("Could not get SNMP Hostname")
    raise ValueError("Could not get SNMP Hostname")
