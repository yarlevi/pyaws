import boto3


def filter_to_power_off(instances):
    """Filter a list of instances to power off.

    Only instances with a tag auto-power: no will be filter out.
    All other instances will be returned"""
    ids = []
    for i in instances:
        tags = i['Tags']
        for tag in tags:
            if tag['Key'] == 'auto-power' and tag['Value'].lower() == 'no':
                break
        else:
            ids.append(i)
    return ids


def lambda_handler(event, context):
    region = 'eu-west-1'
    ec2 = boto3.client('ec2', region_name=region)

    filters = [{'Name': 'instance-state-name', 'Values': ['running']}]

    describe_instances = ec2.describe_instances(Filters=filters)
    instances = [instance for r in describe_instances['Reservations'] for instance in r['Instances']]
    instances_to_power_off = filter_to_power_off(instances)
    ids = [i['InstanceId'] for i in instances_to_power_off]

    if len(ids):
        ec2.stop_instances(InstanceIds=ids, DryRun=False)
        print('Stopped instances: ' + ', '.join(ids))
    else:
        print('No instances are eligible to stop.')


if __name__ == '__main__':
    lambda_handler(None, None)
