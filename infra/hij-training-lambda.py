"""
Lambda function to launch EC2 spot instance for HIJ model training.

Triggered by CloudWatch Events (weekly schedule) or manual invocation.
"""
import boto3
import json
import base64
import os

EC2_CLIENT = boto3.client("ec2", region_name="us-east-2")
SNS_CLIENT = boto3.client("sns", region_name="us-east-2")

# Configuration
INSTANCE_TYPE = "r5.xlarge"  # 16GB RAM, 4 vCPU
AMI_ID = os.environ.get("EC2_AMI_ID", "ami-0ea3405d2d2522162")  # Amazon Linux 2023 us-east-2
SUBNET_ID = os.environ.get("EC2_SUBNET_ID")
SECURITY_GROUP_ID = os.environ.get("EC2_SG_ID")
IAM_INSTANCE_PROFILE = os.environ.get("EC2_INSTANCE_PROFILE", "hij-training-role")
SNS_TOPIC_ARN = os.environ.get("HIJ_SNS_TOPIC_ARN", "")
S3_BUCKET = os.environ.get("HIJ_MODEL_BUCKET", "secondbrain-models")

USER_DATA_TEMPLATE = """#!/bin/bash
set -euo pipefail
exec > /var/log/hij-training.log 2>&1

echo "=== HIJ Training Bootstrap ==="
date

yum update -y
yum install -y python3.12 python3.12-pip git

cd /opt
git clone https://github.com/MrIDK-crypto/2ndBRAINPRANAV.git app
cd app/backend

pip3.12 install scikit-learn requests boto3 numpy

export HIJ_MODEL_BUCKET="{s3_bucket}"
export AWS_S3_REGION="us-east-2"
export HIJ_SNS_TOPIC_ARN="{sns_topic}"

python3.12 -m scripts.ec2_train_and_upload --target {target} --workers 8

echo "=== Training Complete ==="
"""


def handler(event, context):
    target = event.get("target_papers", 1_000_000)

    user_data = USER_DATA_TEMPLATE.format(
        s3_bucket=S3_BUCKET,
        sns_topic=SNS_TOPIC_ARN,
        target=target,
    )

    launch_spec = {
        "ImageId": AMI_ID,
        "InstanceType": INSTANCE_TYPE,
        "UserData": base64.b64encode(user_data.encode()).decode(),
        "InstanceMarketOptions": {
            "MarketType": "spot",
            "SpotOptions": {
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate",
            },
        },
        "TagSpecifications": [{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": f"hij-training-{target}"},
                {"Key": "Project", "Value": "2ndBrain"},
                {"Key": "Purpose", "Value": "HIJ-model-training"},
            ],
        }],
        "MinCount": 1,
        "MaxCount": 1,
    }

    if SUBNET_ID:
        launch_spec["SubnetId"] = SUBNET_ID
    if SECURITY_GROUP_ID:
        launch_spec["SecurityGroupIds"] = [SECURITY_GROUP_ID]
    if IAM_INSTANCE_PROFILE:
        launch_spec["IamInstanceProfile"] = {"Name": IAM_INSTANCE_PROFILE}

    response = EC2_CLIENT.run_instances(**launch_spec)
    instance_id = response["Instances"][0]["InstanceId"]

    msg = f"Launched EC2 spot instance {instance_id} for HIJ training ({target} papers)"
    print(msg)

    if SNS_TOPIC_ARN:
        SNS_CLIENT.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="HIJ Training Launched",
            Message=msg,
        )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "instance_id": instance_id,
            "target_papers": target,
            "instance_type": INSTANCE_TYPE,
        }),
    }
