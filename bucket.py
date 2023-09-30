import os
import time
import logging
import tempfile
import boto3
import botocore.exceptions

class O2ZBucket():
    def __init__(self):
        access_key = os.getenv("P2Z_S3_ACCESS_KEY")
        secret_key = os.getenv("P2Z_S3_SECRET_KEY")
        region = os.getenv("P2Z_S3_REGION", default='us-east-1')
        self.bucket = os.getenv("P2Z_S3_BUCKET")

        self.s3 = boto3.resource('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        self.s3_client = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    def list_objects(self):
        objects = self.s3.Bucket(self.bucket).objects.all()
        for o in objects:
            print(o.key)

    def print_objects(self, obj):
        print(obj)
        response = self.s3_client.get_object(Bucket=self.bucket, Key=obj)
        print(response)
        print(response['Body'].read().decode('utf-8'))

    # Publishes reports to:
    #    s3://mesh-support-reports/zabbix/csv/YYYY/MM/DD/noisiest.csv
    #    s3://mesh-support-reports/zabbix/pretty/YYYY/MM/DD/noisiest.txt
    def publish_noise_reports(self, noisiest_triggers, noisiest_triggers_pretty):
        title = os.getenv("P2Z_CSV_TITLE")
        if title is None:
            raise ValueError("P2Z_CSV_TITLE is not set. Please set a title for this data!") 
        t = time.gmtime()
        csv_path=f"zabbix/test/{t.tm_year}/{t.tm_mon}/{t.tm_mday}/noisiest.csv"
        pretty_path=f"zabbix/test_pretty/{t.tm_year}/{t.tm_mon}/{t.tm_mday}/noisiest.txt"
        with tempfile.NamedTemporaryFile() as tmp:
            n = f"{title}\n"
            for l in noisiest_triggers:
                for i in l:
                    n += str(i) + ', '
                n += "\n"
            tmp.write(str.encode(n))
            self.s3.Object(self.bucket, csv_path).put(Body=tmp)
            logging.info(f"Objects successfully reported. [{csv_path}] ")

        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(str.encode(noisiest_triggers_pretty))
            self.s3.Object(self.bucket, pretty_path).put(Body=tmp)
            logging.info(f"Objects successfully reported. [{pretty_path}]")

