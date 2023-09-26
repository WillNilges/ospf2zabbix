#!/usr/bin/env python3
import os
import time
from main import get_or_create_hostgroup
import psycopg2
from prettytable import PrettyTable

# https://www.zabbix.com/forum/zabbix-troubleshooting-and-problems/26057-reporting-top-10-triggers

def get_noisiest_triggers(conn, group_id, days_ago, limit):
    cursor = conn.cursor()
    current_time = time.time()
    timestamp = current_time - (days_ago * 24 * 60 * 60)  # 7 days * 24 hours * 60 minutes * 60 seconds
    query = f'''
    SELECT h.name, t.description, t.priority, COUNT(DISTINCT e.eventid) AS cnt_event
    FROM triggers t, events e, functions f, items i, hosts h, hosts_groups hg
    WHERE t.triggerid = e.objectid
      AND e.source = 0
      AND e.object = 0
      AND e.clock > {timestamp} 
      AND t.flags IN ('0', '4')
      AND t.priority >= 3
      AND f.triggerid = t.triggerid
      AND i.itemid = f.itemid
      AND i.hostid = h.hostid
      AND h.hostid = hg.hostid
      AND hg.groupid = {group_id}
    GROUP BY h.name, t.description, t.priority  -- Added h.name to GROUP BY
    ORDER BY cnt_event DESC
    LIMIT {limit} OFFSET 0;
    '''

    # Hmmmmm I wonder if 
    # https://git.zabbix.com/projects/ZT/repos/rsm-scripts/browse/ui/toptriggers.php#26

    cursor.execute(query)
    result = cursor.fetchall()
    print(f"{limit} Noisiest Triggers from the last {days_ago} days")
    #print("name, description, priority, eventid")
    #for row in result:
    #    print(row)

    x = PrettyTable()
    x.field_names = ["Host", "Description", "Priority", "Trip Count"]
    for row in result:
        x.add_row(row)

    print(x)
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

