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

