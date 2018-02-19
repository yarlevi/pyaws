import boto3
import logging

log = logging.getLogger(__name__)


def describe(type, id):
    ec2 = boto3.resource('ec2')
    log.debug('fetching {} details for subnet_id={}'.format(type, id))

    types = dict(instance='Instance',
                 vpc='Vpc',
                 subnet='Subnet'
                 )

    if type not in types:
        raise(NotImplementedError('no method defined to describe type={}'.format(type)))

    func = getattr(ec2, types[type])
    obj = func(id=id)

    return obj


def find_by_name(type, vpc_id, name):
    ec2 = boto3.client('ec2')
    log.debug('Find a {} with name={} in vpc_id={}'.format(type, name, vpc_id))
    filters = [dict(Name='tag:Name', Values=[name]),
               dict(Name='vpc-id', Values=[vpc_id])
               ]

    types = dict(subnet=('describe_subnets', 'Subnets', 'SubnetId'),
                 security_group=('describe_security_groups', 'SecurityGroups', 'GroupId')
                 )

    if type not in types:
        raise(NotImplementedError('no method defined to find type={}'.format(type)))

    describe_function_name, key_name, id_name = types[type]

    func = getattr(ec2, describe_function_name)
    matches = func(Filters=filters)[key_name]

    if not matches:
        raise(LookupError('{} not found in vpc_id with name={}'.format(type, vpc_id, name)))
    elif len(matches) > 1:
        raise(LookupError('too many matches ({}) for filter'.format(len(matches), filters)))
    else:
        match_id = matches[0][id_name]
        log.info('found id={} with filter {}'.format(match_id, filters))

    return match_id
