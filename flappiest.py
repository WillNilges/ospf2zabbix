#!/usr/bin/env python3
# https://www.zabbix.com/forum/zabbix-troubleshooting-and-problems/26057-reporting-top-10-triggers

def get_flappiest():

    # Create a cursor object
    cursor = conn.cursor()

    query = "SELECT h.name,count(distinct e.eventid) AS cnt_event FROM triggers t,events e,functions f, items i,hosts h,hosts_groups hg WHERE t.triggerid=e.objectid AND e.source=0 AND e.object=0 AND e.clock>UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 day)) AND t.flags IN ('0','4') AND f.triggerid = t.triggerid AND i.itemid = f.itemid AND i.hostid = h.hostid AND h.hostid = hg.hostid GROUP BY h.hostid ORDER BY cnt_event desc LIMIT 20;"

    # Execute the query
    cursor.execute(query)

    # Fetch all rows
    result = cursor.fetchall()

    # Loop through the result set and print the data
    for row in result:
        print(row)

    # Close the cursor and the database connection
    cursor.close()

import mysql.connector

def main():
    # Replace these with your own database credentials
    host = "your_host"
    user = "your_username"
    password = "your_password"
    database = "your_database_name"

    # Create a connection to the database
    conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database
    )

    get_flappiest()

    conn.close()
