#!/usr/bin/env python3
import os
import time
from main import get_or_create_hostgroup
import psycopg2

# https://www.zabbix.com/forum/zabbix-troubleshooting-and-problems/26057-reporting-top-10-triggers

def get_flappiest_triggers(conn):
    cursor = conn.cursor()

    query = "SELECT h.name,count(distinct e.eventid) AS cnt_event FROM triggers t,events e,functions f, items i,hosts h,hosts_groups hg WHERE t.triggerid=e.objectid AND e.source=0 AND e.object=0 AND e.clock>UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 day)) AND t.flags IN ('0','4') AND f.triggerid = t.triggerid AND i.itemid = f.itemid AND i.hostid = h.hostid AND h.hostid = hg.hostid GROUP BY h.hostid ORDER BY cnt_event desc LIMIT 20;"

    cursor.execute(query)
    result = cursor.fetchall()
    print("Flappiest Triggers")
    for row in result:
        print(row)
    cursor.close()


def get_noisiest_triggers(conn, group_id):
    cursor = conn.cursor()
    current_time = time.time()
    week_ago = current_time - (7 * 24 * 60 * 60)  # 7 days * 24 hours * 60 minutes * 60 seconds
    #query = f"SELECT h.name,t.description,t.priority,count(distinct e.eventid) AS cnt_event FROM triggers t,events e,functions f, items i,hosts h,hosts_groups hg WHERE t.triggerid=e.objectid AND e.source=0 AND e.object=0 AND e.clock>{week_ago} AND t.flags IN ('0','4') AND t.priority >= 1 AND f.triggerid = t.triggerid AND i.itemid = f.itemid AND i.hostid = h.hostid AND h.hostid = hg.hostid AND hg.groupid={group_id} GROUP BY e.objectid ORDER BY cnt_event desc LIMIT 100 OFFSET 0;"
    query = f'''
    SELECT h.name, t.description, t.priority, COUNT(DISTINCT e.eventid) AS cnt_event
    FROM triggers t, events e, functions f, items i, hosts h, hosts_groups hg
    WHERE t.triggerid = e.objectid
      AND e.source = 0
      AND e.object = 0
      AND e.clock > {week_ago} 
      AND t.flags IN ('0', '4')
      AND t.priority >= 1
      AND f.triggerid = t.triggerid
      AND i.itemid = f.itemid
      AND i.hostid = h.hostid
      AND h.hostid = hg.hostid
      AND hg.groupid = {group_id}
    GROUP BY h.name, t.description, t.priority  -- Added h.name to GROUP BY
    ORDER BY cnt_event DESC
    LIMIT 100 OFFSET 0;
    '''

    #https://git.zabbix.com/projects/ZT/repos/rsm-scripts/browse/ui/toptriggers.php#26

    #query = f"SELECT h.name, t.description, COUNT(e.eventid) 'count' FROM hosts h INNER JOIN items i ON h.hostid = i.hostid INNER JOIN functions f ON i.itemid = f.itemid INNER JOIN triggers t ON f.triggerid = t.triggerid INNER JOIN events e ON t.triggerid = e.objectid AND e.object = 0 AND e.source = 0 AND e.value = 1 AND e.clock > {time.time()} - 86400*30 WHERE h.status = 0 AND i.status = 0 AND t.status = 0 GROUP BY h.name, t.description ORDER BY count DESC LIMIT 100;"

    cursor.execute(query)
    result = cursor.fetchall()
    print("Noisiest Triggers")
    for row in result:
        print(row)
    cursor.close()


def connect_to_db():
    db_params = {
        "host": os.getenv("P2Z_PGSQL_HOST"),
        "database": os.getenv("P2Z_PGSQL_DB"),
        "user": os.getenv("P2Z_PGSQL_UNAME"),
        "password": os.getenv("P2Z_PGSQL_PWORD"),
        "port": "5432",
    }

    return psycopg2.connect(**db_params)

