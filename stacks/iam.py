from troposphere import Ref, GetAtt
from troposphere.iam import Role, Policy, InstanceProfile, User, AccessKey

import awacs.aws
from awacs.aws import Allow, Deny, Principal, Action  # noqa
from awacs.aws import Condition, IpAddress  # noqa
import awacs.ec2 as ec2  # noqa
import awacs.s3 as s3  # noqa

from .tools import aws_name
from .template import add_output
from .security import ALL_CISCO_CIDRS


ASSUME_POLICY_DOCUMENT = awacs.aws.Policy(Version='2012-10-17',
                                          Statement=[awacs.aws.Statement(Effect=Allow,
                                                                         Principal=Principal('Service',
                                                                                             'ec2.amazonaws.com'),
                                                                         Action=[Action('sts', 'AssumeRole')])])


def policy(name, statements):
    if not isinstance(statements, list):
        statements = [statements]
    policy = Policy()
    policy.PolicyName = aws_name(name)
    policy.PolicyDocument = awacs.aws.Policy(Statement=statements)
    return policy


def role(template, name, policies):
    if policies:
        if not isinstance(policies, list):
            policies = [policies]

    role = Role(name, template=template)
    role.RoleName = aws_name(name)
    role.AssumeRolePolicyDocument = ASSUME_POLICY_DOCUMENT
    role.Path = '/'
    if policies:
        role.Policies = policies
    return role


def statement(actions, resource='*', effect=awacs.aws.Allow, condition=None):
    if not isinstance(actions, list):
        actions = [actions]
    if not isinstance(resource, list):
        resource = [resource]
    s = awacs.aws.Statement(Action=actions, Resource=resource, Effect=effect,
                            **({'Condition': condition} if condition else {}))  # only pass condition if it was provided
    return s


def role_with_statements(template, name, statemenets):
    p = policy(name='{}policy'.format(name), statements=statemenets)
    r = role(template=template, name=name, policies=p)
    return r


def instance_profile(template, name, role):
    profile = InstanceProfile(name, template=template)
    profile.InstanceProfileName = aws_name(name)
    # per awacs documentation a max of 1 role can be defined
    profile.Roles = [Ref(role)]
    return profile


def user(template, user_name, policies=None, generate_key_serial=False):
    user = User(template=template, title=user_name.replace('_', ''))
    user.UserName = user_name
    if policies:
        if not isinstance(policies, list):
            policies = [policies]
        user.Policies = policies
    if generate_key_serial is not False:
        key(template=template, user=user, serial=generate_key_serial)

    return user


def key(template, user, serial=0):
    user_name = user.UserName
    key = AccessKey(template=template, title='{}key'.format(user_name.replace('_', '')))
    key.UserName = user_name
    key.Serial = serial
    key.DependsOn = user.title

    add_output(template=template, description=user_name + 'ACCESS_KEY_ID', value=Ref(key))
    add_output(template=template, description=user_name + 'SECRET_ACCESS_KEY', value=GetAtt(key, 'SecretAccessKey'))

    return key


class Policies(object):
    @staticmethod
    def jenkins(name):

        read_only_ec2 = [Action('ec2', 'DescribeInstances'),
                         Action('ec2', 'DescribeImages'),
                         Action('ec2', 'DescribeTags'),
                         Action('ec2', 'DescribeSnapshots')
                         ]
        cisco_cidr_only_condition = Condition(IpAddress({awacs.aws.SourceIp: ALL_CISCO_CIDRS}))
        jenkins_statement = statement(actions=read_only_ec2, resource=['*'], effect=Allow,
                                      condition=cisco_cidr_only_condition)
        jenkins = policy(name=name, statements=[jenkins_statement])
        return jenkins


class Roles(object):
    @staticmethod
    def ec2_full(template, name):
        role = role_with_statements(template=template, name=name, statemenets=[statement(Action('ec2', '*'))])
        return role

    @staticmethod
    def s3_full(template, name):
        role = role_with_statements(template=template, name=name, statemenets=[statement(Action('s3', '*'))])
        return role

    @staticmethod
    def ecr_full(template, name):
        role = role_with_statements(template=template, name=name, statemenets=[statement(Action('ecr', '*'))])
        return role


class InstanceProfiles(object):
    @staticmethod
    def packer(template, name='packerinstanceprofile'):
        role = Roles.ec2_full(template=template, name='{}role'.format(name))
        profile = instance_profile(template=template, name=name, role=role)
        return profile

    @staticmethod
    def ec2_full(template, name='ec2fullinstanceprofile'):
        role = Roles.ec2_full(template=template, name='{}role'.format(name))
        profile = instance_profile(template=template, name=name, role=role)
        return profile

    @staticmethod
    def s3_full(template, name='s3fullinstanceprofile'):
        role = Roles.s3_full(template=template, name='{}role'.format(name))
        profile = instance_profile(template=template, name=name, role=role)
        return profile

    @staticmethod
    def ecr_full(template, name='ecrfullinstanceprofile'):
        role = Roles.ecr_full(template=template, name='{}role'.format(name))
        profile = instance_profile(template=template, name=name, role=role)
        return profile
