import os
import time
import logging
import boto3
import botocore.exceptions


class O2ZBucket:
    def __init__(self):
        access_key = os.getenv("P2Z_S3_ACCESS_KEY", default="")
        secret_key = os.getenv("P2Z_S3_SECRET_KEY", default="")
        region = os.getenv("P2Z_S3_REGION", default="us-east-1")
        self.bucket = os.getenv("P2Z_S3_BUCKET", default="")

        self.s3 = boto3.resource(
            "s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key
        )
        self.s3_client = boto3.client(
            "s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key
        )

    def list_objects(self):
        objects = self.s3.Bucket(self.bucket).objects.all()
        for o in objects:
            print(o.key)

    def print_objects(self, obj):
        logging.debug(obj)
        response = self.s3_client.get_object(Bucket=self.bucket, Key=obj)
        logging.debug(response)
        print(response["Body"].read().decode("utf-8"))

    def delete_object(self, obj):
        try:
            logging.debug(obj)
            response = self.s3_client.delete_object(Bucket=self.bucket, Key=obj)
            logging.info(response)
        except botocore.exceptions.ClientError as e:
            logging.error(e)

    # Publishes reports to:
    #    s3://mesh-support-reports/zabbix/csv/YYYY/MM/DD/noisiest.csv
    # Optionally, publishes the pretty-printed version to:
    #    s3://mesh-support-reports/zabbix/pretty/YYYY/MM/DD/noisiest.csv
    def publish_noise_reports(self, triggers, pretty=False, test=False):
        title = os.getenv("P2Z_CSV_TITLE")
        if title is None:
            raise ValueError(
                "P2Z_CSV_TITLE is not set. Please set a title for this data!"
            )
        t = time.gmtime()
        t_string = f"{t.tm_year}/{t.tm_mon}/{t.tm_mday}"
        t_string = "".join(f"{x.zfill(2)}/" for x in t_string.split("/"))
        csv_path = f"zabbix/csv/{t_string}noisiest.csv"

        # Assemble CSV to push
        body = f"{title}\n"
        for t in triggers.trigger_list:
            body += f"{t.host}, {t.description}, {t.priority}, {t.count},\n"

        if test:
            print(csv_path)
            print(body)
            return

        # Publish CSV data to S3
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=csv_path, Body=body)
            logging.info(f"Objects successfully reported to {csv_path}")
        except botocore.exceptions.ClientError as e:
            logging.error(f"Could not upload csv data to S3: {e}")

        if pretty:
            pretty_path = f"zabbix/pretty/{t_string}noisiest.csv"

            # We do this rigamarole so we can check the assertion
            pretty_triggers = triggers.pretty_print()
            assert pretty_triggers is not None
            pretty_triggers = f"{pretty_triggers}"

            try:
                self.s3_client.put_object(
                    Bucket=self.bucket, Key=pretty_path, Body=pretty_triggers
                )
                logging.info(f"Objects successfully reported to {pretty_path}")
            except botocore.exceptions.ClientError as e:
                logging.error(f"Could not upload pretty data to S3: {e}")
