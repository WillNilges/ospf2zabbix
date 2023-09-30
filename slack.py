import os
from slack_sdk import WebClient

class O2ZSlack():
    def __init__(self):
        slack_token = os.getenv("P2Z_SLACK_TOKEN")
        self.channel = os.getenv("P2Z_SLACK_CHANNEL")
        self.client = WebClient(token=slack_token)

    def publish_noise_reports(self, triggers):
        self.client.chat_postMessage(
                channel=self.channel,
                text=f"```{triggers}```",
            )

    def delete_report(self, url):
        # https://nycmesh.slack.com/archives/C05TPHA43PD/p1696054569736259
        us = url.split("/")
        # Goddammit Slack. Gotta peel off the 'p', then add a period about
        # 6 characters from the front to get a timestamp.
        ts=us[-1][1:]
        ts=f"{ts[:-6]}.{ts[-6:]}"
        self.client.chat_delete(channel=us[-2], ts=ts)
