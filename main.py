#!/usr/bin/env python3
import os
import logging
import argparse
from dotenv import load_dotenv
import socket
import triggers as fl
from bucket import O2ZBucket
from slack import O2ZSlack
from zabbix import O2ZZabbix

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

def main():
    load_dotenv()
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
    logging.debug(args)

    if args.subcommand in ("enroll-popular", "enroll-device", "noisy-triggers"):
        z = O2ZZabbix() 
        if args.subcommand == "enroll-popular":
            z.enroll_popular_devices( ospf_api_url, args.link_floor)
        elif args.subcommand == "enroll-device":
            if not is_valid_ipv4(args.ip):
                raise ValueError("Must pass a valid IPv4 address!")
            z.enroll_device(args.ip)
        elif args.subcommand == "noisy-triggers":
            conn = fl.connect_to_db()

            noisiest_triggers = fl.get_noisiest_triggers(
                conn, z.get_or_create_hostgroup(), args.days_ago, args.leaderboard
            )
            conn.close()

            leaderboard_title = (
                f"{args.leaderboard} Noisiest Triggers from the last {args.days_ago} days"
            )
            noisiest_triggers_pretty = fl.pretty_print_noisiest_triggers(noisiest_triggers)
            noisiest_triggers_pretty = f"{leaderboard_title}\n{noisiest_triggers_pretty}"
            print(noisiest_triggers_pretty)

            if args.publish:
                s3 = O2ZBucket()
                s3.publish_noise_reports(noisiest_triggers, noisiest_triggers_pretty)

            if args.slack:
                slack = O2ZSlack()
                slack.publish_noise_reports(noisiest_triggers_pretty)

    elif args.subcommand == "bucket":
        s3 = O2ZBucket()

        if args.object:
            s3.print_objects(args.object)
            return

        s3.list_objects()
    
    elif args.subcommand == "slack":
        slack = O2ZSlack()
        if args.delete:
            slack.delete_report(args.delete)


if __name__ == "__main__":
    main()
