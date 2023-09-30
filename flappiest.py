#!/usr/bin/env python3
import os
import time
from main import get_or_create_hostgroup
import psycopg2
from prettytable import PrettyTable


# Queries the DB directly for loudest triggers
# https://www.zabbix.com/forum/zabbix-troubleshooting-and-problems/26057-reporting-top-10-triggers
# Not that we need it, but this is the source code for the top triggers page.
# It has a few queries we could use
# https://git.zabbix.com/projects/ZT/repos/rsm-scripts/browse/ui/toptriggers.php#26
def get_noisiest_triggers(conn, group_id, days_ago, limit):
    cursor = conn.cursor()
    current_time = time.time()
    timestamp = current_time - (
        days_ago * 24 * 60 * 60
    )  # 7 days * 24 hours * 60 minutes * 60 seconds
    query = f"""
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
    """

    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return result


def pretty_print_noisiest_triggers(trigger_list):
    t = PrettyTable()
    # This is a little confusing, so here's an explaination:
    # I get the env var into a variable called title, then check if that worked
    # Then I capitalize all the words using title()
    # Then I split the string into an array by its commas
    # Then I strip away the blank item in the array using filter()
    title = os.getenv("P2Z_CSV_TITLE") 
    if title is None:
        raise ValueError("P2Z_CSV_TITLE is not set. Please set a title for this data!")
    t.field_names = filter(None, title.title().split(","))
    for row in trigger_list:
        t.add_row(row)
    return t


def connect_to_db():
    db_params = {
        "host": os.getenv("P2Z_PGSQL_HOST"),
        "database": os.getenv("P2Z_PGSQL_DB"),
        "user": os.getenv("P2Z_PGSQL_UNAME"),
        "password": os.getenv("P2Z_PGSQL_PWORD"),
        "port": "5432",
    }

    return psycopg2.connect(**db_params)
