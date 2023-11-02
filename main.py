#!/usr/bin/env python3
import os
import logging
import argparse
from dotenv import load_dotenv
import socket
from triggers import O2ZTriggers
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

    enroll_parser = subparsers.add_parser(
        "enroll", help="Enroll devices into Zabbix"
    )
    enroll_parser.add_argument("--ip", type=str, help="Enroll a node by IP")
    enroll_parser.add_argument(
        "--popular",
        type=int,
        nargs="?",
        default=int(os.getenv("P2Z_LINK_FLOOR", default=10)),
        help="Get devices on the mesh and automatically add ones that have a minimum number of links (Defaults to 10).",
    )

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
    bucket_parser.add_argument(
        "--delete",
        type=str,
        help="Delete an S3 object",
    )

    slack_parser = subparsers.add_parser("slack", help="Slack helper functions")
    slack_parser.add_argument(
        "--delete",
        type=str,
        help="Deletes a message from the bot",
    )

    args = parser.parse_args()
    logging.debug(args)

    if args.subcommand in ("enroll", "noisy-triggers"):
        z = O2ZZabbix() 
        if args.subcommand == "enroll":
            if args.ip:
                if not is_valid_ipv4(args.ip):
                    raise ValueError("Must pass a valid IPv4 address!")
                z.enroll_device(args.ip)
            elif args.popular:
                z.enroll_popular_devices(args.popular)
            else:
                args.help()

        elif args.subcommand == "noisy-triggers":
            t = O2ZTriggers()

            noisiest_triggers = t.get_noisiest_triggers(
                z.get_or_create_hostgroup(), args.days_ago, args.leaderboard
            )

            noisiest_triggers.sort(key=lambda tup: tup[2], reverse=True)

            if args.publish:
                s3 = O2ZBucket()
                s3.publish_noise_reports(noisiest_triggers)

            if args.slack:
                slack = O2ZSlack()
                slack.publish_noise_reports(noisiest_triggers)

    elif args.subcommand == "bucket":
        s3 = O2ZBucket()

        if args.object:
            s3.print_objects(args.object)
            return

        if args.delete:
            s3.delete_object(args.delete)
            return

        s3.list_objects()
    
    elif args.subcommand == "slack":
        slack = O2ZSlack()
        if args.delete:
            slack.delete_report(args.delete)


if __name__ == "__main__":
    main()
