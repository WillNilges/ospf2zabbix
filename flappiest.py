#!/usr/bin/env python3
import os
from main import get_or_create_hostgroup
# import zabbix_utils as z
import mysql.connector

# https://www.zabbix.com/forum/zabbix-troubleshooting-and-problems/26057-reporting-top-10-triggers

def get_busiest_triggers(conn):
    cursor = conn.cursor()

    query = "SELECT h.name,count(distinct e.eventid) AS cnt_event FROM triggers t,events e,functions f, items i,hosts h,hosts_groups hg WHERE t.triggerid=e.objectid AND e.source=0 AND e.object=0 AND e.clock>UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 day)) AND t.flags IN ('0','4') AND f.triggerid = t.triggerid AND i.itemid = f.itemid AND i.hostid = h.hostid AND h.hostid = hg.hostid GROUP BY h.hostid ORDER BY cnt_event desc LIMIT 20;"

    cursor.execute(query)
    result = cursor.fetchall()
    print("Flappiest Triggers")
    for row in result:
        print(row)
    cursor.close()


def get_flappiest_triggers(conn):
    cursor = conn.cursor()

    query = "SELECT h.name,count(distinct e.eventid) AS cnt_event FROM triggers t,events e,functions f, items i,hosts h,hosts_groups hg WHERE t.triggerid=e.objectid AND e.source=0 AND e.object=0 AND e.clock>UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 day)) AND t.flags IN ('0','4') AND f.triggerid = t.triggerid AND i.itemid = f.itemid AND i.hostid = h.hostid AND h.hostid = hg.hostid GROUP BY h.hostid ORDER BY cnt_event desc LIMIT 20;"

    cursor.execute(query)
    result = cursor.fetchall()
    print("Flappiest Triggers")
    for row in result:
        print(row)
    cursor.close()


def get_noisiest_triggers(conn):
    cursor = conn.cursor()

    group_id = get_or_create_hostgroup()

    query = f"SELECT h.name,t.description,t.priority,count(distinct e.eventid) AS cnt_event FROM triggers t,events e,functions f, items i,hosts h,hosts_groups hg WHERE t.triggerid=e.objectid AND e.source=0 AND e.object=0 AND e.clock>UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 7 day)) AND t.flags IN ('0','4') AND t.priority >= 1 AND f.triggerid = t.triggerid AND i.itemid = f.itemid AND i.hostid = h.hostid AND h.hostid = hg.hostid AND hg.groupid={group_id} GROUP BY e.objectid ORDER BY cnt_event desc LIMIT 100 OFFSET 0;"

    cursor.execute(query)
    result = cursor.fetchall()
    print("Noisiest Triggers")
    for row in result:
        print(row)
    cursor.close()


def connect_to_db():
    pgsql_host = os.getenv("P2Z_PGSQL_HOST")
    pgsql_uname = os.getenv("P2Z_PGSQL_UNAME")
    pgsql_pword = os.getenv("P2Z_PGSQL_PWORD")
    pgsql_db = os.getenv("P2Z_PGSQL_DB")

    # Create a connection to the database
    return mysql.connector.connect(
        host=pgsql_host,
        user=pgsql_uname,
        password=pgsql_pword,
        database=pgsql_db
    )

