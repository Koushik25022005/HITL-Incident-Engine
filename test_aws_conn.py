"""
test_aws_connection.py

Standalone sanity check for your AWS/boto3 setup — run this BEFORE
wiring lookup_server/reboot_instance into the Streamlit app, so you
can isolate credential/region issues from graph/app issues.

Usage:
    python test_aws_connection.py i-0abcd1234efgh5678

If you don't have an instance ID yet, run without an argument to just
verify that credentials + region work and list what instances (if any)
exist in that region.
"""

import sys

import boto3 # type: ignore
from dotenv import load_dotenv

load_dotenv()


def main():
    region = None
    try:
        from config.settings import AWS_REGION
        region = AWS_REGION
    except ImportError:
        region = "us-west-2"
        print(f"Could not import AWS_REGION from config.settings — defaulting to {region}")

    print(f"Connecting to EC2 in region: {region}")

    try:
        ec2 = boto3.client("ec2", region_name=region)
        # A cheap, harmless call that confirms credentials + region + network all work.
        identity = boto3.client("sts", region_name=region).get_caller_identity()
        print("✅ Credentials valid.")
        print(f"   Account: {identity['Account']}")
        print(f"   IAM ARN: {identity['Arn']}")
    except Exception as e:
        print("❌ Failed to authenticate with AWS.")
        print(f"   Error: {e}")
        print("\nCommon causes:")
        print("  - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY missing or wrong in .env")
        print("  - Using root keys that were later deactivated, or a disabled IAM user")
        print("  - No internet/network access from this machine")
        sys.exit(1)

    if len(sys.argv) > 1:
        instance_id = sys.argv[1]
        print(f"\nLooking up instance: {instance_id}")
        try:
            response = ec2.describe_instances(InstanceIds=[instance_id])
            instance = response["Reservations"][0]["Instances"][0]
            print("✅ Instance found.")
            print(f"   State: {instance['State']['Name']}")
            print(f"   Type: {instance['InstanceType']}")
            print(f"   AZ: {instance['Placement']['AvailabilityZone']}")
        except ec2.exceptions.ClientError as e:
            print("❌ Could not find or access that instance.")
            print(f"   Error: {e}")
            print("\nCommon causes:")
            print("  - Instance ID typo")
            print("  - Instance exists in a DIFFERENT region than AWS_REGION")
            print("  - IAM policy doesn't grant ec2:DescribeInstances")
            sys.exit(1)
    else:
        print("\nNo instance ID passed — listing instances in this region instead:")
        try:
            response = ec2.describe_instances()
            found_any = False
            for reservation in response.get("Reservations", []):
                for instance in reservation["Instances"]:
                    found_any = True
                    print(f"  {instance['InstanceId']}  state={instance['State']['Name']}  "
                          f"type={instance['InstanceType']}")
            if not found_any:
                print("  (no instances found in this region — launch one via the AWS Console first)")
        except Exception as e:
            print(f"❌ Could not list instances: {e}")
            sys.exit(1)

    print("\nAll checks passed. Safe to wire this into nodes.py's lookup_server/reboot_instance.")


if __name__ == "__main__":
    main()