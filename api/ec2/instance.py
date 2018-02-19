import logging
import boto3

from tags import tags_to_tag_specification


log = logging.getLogger(__name__)


def interface(name, subnet_id, ip_address=None, security_group_id=None):
    i = dict(DeleteOnTermination=True,
             Description=name,
             DeviceIndex=int(name[-1]),
             SubnetId=subnet_id
             )
    if ip_address:
        i['PrivateIpAddresses'] = [dict(Primary=True, PrivateIpAddress=ip_address)]

    if security_group_id:
        i['Groups'] = [security_group_id]
    return i


def create(name, role, ami, flavor, key_name, interfaces=None, tags=None, user_data='', wait_until_running=False,
           dry_run=False):
    ec2 = boto3.resource('ec2')
    if tags is None:
        tags = {}
    tags.update(dict(Name=name, Role=role))

    log.info('creating instance name={}'.format(name))
    instances = ec2.create_instances(ImageId=ami,
                                     InstanceType=flavor,
                                     KeyName=key_name,
                                     MaxCount=1,
                                     MinCount=1,
                                     UserData=user_data,
                                     DryRun=dry_run,
                                     TagSpecifications=[tags_to_tag_specification(resource='instance', tags=tags)],
                                     **dict(NetworkInterfaces=interfaces) if interfaces else {}
                                     )
    instance = instances[0]
    log.debug('instance name={} with id={} created'.format(name, instance.id))

    if wait_until_running:
        log.debug('waiting until instance id={} is running'.format(instance.id))
        instance.wait_until_running()
        log.info('instance id={} is running'.format(instance.id))
    return instance.id


def terminate(instance_id, wait_until_terminated=False, dry_run=False):
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(id=instance_id)
    log.info('terminating instance with id {}'.format(instance_id))
    instance.terminate(DryRun=dry_run)
    if wait_until_terminated:
        log.debug('waiting on termination of instance_id {}'.format(instance_id))
        instance.wait_until_terminated()
        log.info('instance_id {} terminated'.format(instance_id))
