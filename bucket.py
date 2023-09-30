import boto3
import botocore.exceptions
import os

def bucket_setup():
    access_key = os.getenv("P2Z_S3_ACCESS_KEY")
    secret_key = os.getenv("P2Z_S3_SECRET_KEY")
    region = os.getenv("P2Z_S3_REGION", default='us-east-1')

    print(access_key)
    print(secret_key)

    s3 = boto3.client('s3', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    #response = s3.list_buckets()
    #print(response)
    response = s3.list_objects_v2(Bucket='mesh-support-reports')
    print(response)

