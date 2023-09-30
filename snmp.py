import logging
from pysnmp.hlapi import *

class O2ZSNMP():
    def __init__(self):
        pass

    def snmp_get(self, host, oid):
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
    def snmp_get_hostname(self, ip):
        snmp_host_name = "1.3.6.1.2.1.1.5.0"
        return self.snmp_get(ip, snmp_host_name)[1].prettyPrint()


