import sys
import logging
import boto3
import botocore

from instance import create, terminate, interface
from ec2_tools import describe, find_by_name
from tags import extract_common_tags, extract_extra_tags


log = logging.getLogger(__name__)


VDCM_RT_USER_DATA = """#cloud-config
packages:
  - abrt-cli
disable_root: false
write_files:
  - path: /etc/ntp.conf
    content: |
        driftfile /var/lib/ntp/drift
        restrict default nomodify notrap nopeer noquery
        restrict 127.0.0.1
        restrict ::1
        server {ntp_server} iburst
        includefile /etc/ntp/crypto/pw
        keys /etc/ntp/keys
        disable monitor
  - path: /etc/ntp/step-tickers
    content: |
        {ntp_server}
runcmd:
  - "abrt-auto-reporting enabled"
  - "sed -i 's/OpenGPGCheck = yes/OpenGPGCheck = no/' /etc/abrt/abrt-action-save-package-data.conf"
  - systemctl restart ntpd
"""


class InstanceExists(Exception):
    def __init__(self, ip):
        self.ip = ip

    def __str__(self):
        return repr('Instance with the address \'{}\' already exists.'.format(self.ip))


def get_vdcm_ami(vdcm_version, release=False):
    train = 'release' if release else 'debug'

    ec2 = boto3.client('ec2')
    log.debug('searching for vdcm ami with version={} in train={}'.format(vdcm_version, train))
    images = ec2.describe_images(Filters=[dict(Name='tag:vdcm_version', Values=[vdcm_version]),
                                          dict(Name='name', Values=['*{}*'.format(train)]),
                                          dict(Name='state', Values=['available']),
                                          ])['Images']

    if not len(images):
        raise(LookupError('vdcm ami not found with version {} in train {}'.format(vdcm_version, train)))

    if len(images) > 2:
        raise(LookupError('Found {} vdcm ami with version {} in train {}. Expecting only 1'.
                          format(len(images), vdcm_version, train)))

    ami = images[0]['ImageId']
    log.info('found vdcm ami with version={} in train={}: {}'.format(vdcm_version, train, ami))
    return ami


def create_rt_vdcm(test_server_instance_id, vdcm_version, ip_address, key_name=None, flavor='t2.small'):
    env = get_rt_environment_details(test_server_instance_id=test_server_instance_id)
    ami = get_vdcm_ami(vdcm_version=vdcm_version)
    user_data = VDCM_RT_USER_DATA.format(ntp_server=env['server_private_ip_address'])

    eth0 = interface(name='eth0', subnet_id=env['private_subnet_id'], ip_address=ip_address,
                     security_group_id=env['sg_private_id'])

    eth1 = interface(name='eth1', subnet_id=env['video_subnet_id'], security_group_id=env['sg_video_id'])

    if not key_name:
        key_name = env['server_key_name']
    tags = {}
    tags.update(env['server_default_tags'])
    tags.update(env['server_extra_tags'])
    try:
        instance_id = create(name='{}-vdcm-{}'.format(env['server_default_tags']['Environment Name'], ip_address),
                             role='regression-test-vdcm',
                             ami=ami,
                             flavor=flavor,
                             key_name=key_name,
                             wait_until_running=True,
                             user_data=user_data,
                             tags=tags,
                             interfaces=[eth0, eth1])
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'InvalidIPAddress.InUse':
            raise(InstanceExists(ip_address))
        else:
            raise
    return instance_id


def get_rt_environment_details(test_server_instance_id):
    env = {}
    server = describe(type='instance', id=test_server_instance_id)
    env['server_vpc_id'] = server.vpc_id
    env['server_key_name'] = server.key_name
    env['server_private_ip_address'] = server.private_ip_address
    env['server_default_tags'] = extract_common_tags(server.tags)
    env['extra_tags'] = extract_extra_tags(server.tags, ['auto-power'])
    env['private_subnet_id'] = find_by_name('subnet', vpc_id=server.vpc_id, name='*-management')
    env['video_subnet_id'] = find_by_name('subnet', vpc_id=server.vpc_id, name='*-video')
    env['sg_private_id'] = find_by_name('security_group', vpc_id=server.vpc_id, name='*-vdcmmanagementsecuritygroup')
    env['sg_video_id'] = find_by_name('security_group', vpc_id=server.vpc_id, name='*-vdcmvideosecuritygroup')
    return env


def verify_rt_vdcm(test_server_instance_id, vdcm_version, ip_address, key_name=None, flavor='t2.small'):
    ec2 = boto3.client('ec2')

    env = get_rt_environment_details(test_server_instance_id=test_server_instance_id)
    ami = get_vdcm_ami(vdcm_version=vdcm_version)

    if not key_name:
        key_name = env['server_key_name']

    filters = [dict(Name='private-ip-address', Values=[ip_address]),
               dict(Name='vpc-id', Values=[env['server_vpc_id']])
               ]

    instance = ec2.describe_instances(Filters=filters)['Reservations'][0]['Instances'][0]

    assert 'running' == instance['State']['Name']
    assert flavor == instance['InstanceType']
    assert ami == instance['ImageId']

    assert key_name == instance['KeyName']
    assert env['server_default_tags'] == extract_common_tags(instance['Tags'])

    interfaces = instance['NetworkInterfaces']
    assert len(interfaces) == 2
    eth0 = interfaces[0] if interfaces[0]['Description'] == 'eth0' else interfaces[1]
    eth1 = interfaces[0] if interfaces[0]['Description'] == 'eth1' else interfaces[1]

    assert env['private_subnet_id'] == eth0['SubnetId']
    assert env['video_subnet_id'] == eth1['SubnetId']
    assert env['sg_private_id'] == eth0['Groups'][0]['GroupId']
    assert env['sg_video_id'] == eth1['Groups'][0]['GroupId']

    return instance['InstanceId']


def get_instance_id_by_ip(test_server_instance_id, ip_address):
    ec2 = boto3.client('ec2')
    env = get_rt_environment_details(test_server_instance_id=test_server_instance_id)

    filters = [dict(Name='private-ip-address', Values=[ip_address]),
               dict(Name='vpc-id', Values=[env['server_vpc_id']])
               ]

    instance = ec2.describe_instances(Filters=filters)['Reservations'][0]['Instances'][0]

    return instance['InstanceId']


def is_system_up(instance_id):
    ec2 = boto3.client('ec2')
    instance_status = ec2.describe_instance_status(InstanceIds=[instance_id])
    if instance_status:
        return instance_status['InstanceStatuses'][0]['InstanceStatus']['Status'] == 'ok'
    else:
        return False


class FilterPyaws(logging.Filter):
    def filter(self, record):
        return 'pyaws' in record.pathname


# debugging of the module
if __name__ == '__main__':

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    ch.addFilter(FilterPyaws())
    root.addHandler(ch)
    log.debug('starting')

    subnet = 'subnet-40590e09'
    # subnet = find_free_ip_in_subnet(subnet_id=subnet)

    vdcm_version = '9.0.0-21'
    server_instance_id = 'i-09cfadd92fac66ce4'
    ip_address = '10.0.10.215'
    flavor = 'c4.4xlarge'

    try:
        instance_id = create_rt_vdcm(test_server_instance_id=server_instance_id, vdcm_version=vdcm_version,
                                     ip_address=ip_address, flavor=flavor)
    except InstanceExists as e:
        log.warning(e.message)

    instance_id = verify_rt_vdcm(test_server_instance_id=server_instance_id, vdcm_version=vdcm_version,
                                 ip_address=ip_address, flavor=flavor)

    terminate(instance_id=instance_id, wait_until_terminated=True)
