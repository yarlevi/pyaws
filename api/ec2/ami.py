import logging
import boto3


log = logging.getLogger(__name__)


def get_all_my_amis():
    ec2 = boto3.resource('ec2')
    images = ec2.describe_images(Owners=['self'])['Images']
    return images
