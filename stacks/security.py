from copy import deepcopy
from troposphere import Ref, Tags
from troposphere.ec2 import SecurityGroup, SecurityGroupRule, NetworkAcl, NetworkAclEntry, PortRange

from .tools import aws_name

# This cidr is the one we break out from in Kortrijk as well as Amsterdam VPN
# We can use it to make our security group rules a bit tighter.
CISCO_CIDR = "173.38.128.0/17"
DOMA_CIDR = "64.102.249.0/24"
PDYKSTRA_CIDR = "192.118.76.0/24"
JOVO_CIDR = "173.38.0.0/17"
JOVOVPN_CIDR = "198.135.0.0/21"
TEKTRONIX_CIDR = "192.65.41.0/24"


# got these from Maish Saidel-Keesing, this is a shorter list than the ones
# based on https://cisco.jiveon.com/docs/DOC-1818522
# using these to avoid aws limitations on number of rules (50)
ALL_CISCO_CIDRS = [
    '173.36.0.0/14',
    '64.100.0.0/14',
    '128.107.0.0/16',
    '144.254.0.0/16',
    '161.44.0.0/16',
    '64.104.0.0/16',
    '171.68.0.0/14',
    '192.118.76.0/22',
    '72.163.0.0/16',
    '198.135.0.0/21',
    '172.163.0.0/16',
    '171.70.0.0/16'
    ]


def get_bastion_security_group(template, vpc, sg_name='bastionsecuritygroup', cidr=ALL_CISCO_CIDRS):
    """Get a securty group that fits for a bastion host"""
    sg = SecurityGroup(title=sg_name, template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'security group for bastion ssh https icmp'
    sg.VpcId = Ref(vpc)
    rules = Rules()
    rs = [rules.ssh, rules.https, rules.all_icmp]
    if cidr:
        if not isinstance(cidr, list):
            cidr = [cidr]
        rs = [rules.override_cidr(rule=r, cidr=cidr_item) for r in rs for cidr_item in cidr]

    sg.SecurityGroupIngress = rs

    return sg


def get_http_security_group(template, vpc, sg_name='httpsecuritygroup', cidr=ALL_CISCO_CIDRS):
    """Get a securty group that fits for plain http"""
    sg = SecurityGroup(title=sg_name, template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'security group for http'
    sg.VpcId = Ref(vpc)
    rules = Rules()
    rs = [rules.http]
    if cidr:
        if not isinstance(cidr, list):
            cidr = [cidr]
        rs = [rules.override_cidr(rule=r, cidr=cidr_item) for r in rs for cidr_item in cidr]

    sg.SecurityGroupIngress = rs

    return sg


def get_vdcm_management_security_group(template, vpc, sg_name='vdcmmanagementsecuritygroup', cidr=CISCO_CIDR):
    """Get a vdcm security group containing the vdcm rules for management

    :param name: unique name of the security group.
    :param template: the template to add this subnet too.
    :param vpc: the vpc to add this subnet too.
    :param cidr: the cidr to use to create this security group rule. Defaults to the CISCO_CIDR.
    :return: security_group
    """
    sg = SecurityGroup(sg_name, template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'vdcm security group for management'
    sg.VpcId = Ref(vpc)

    rules = Rules()
    rs = [rules.ssh, rules.http, rules.https, rules.influxdb, rules.vnc, rules.rest, rules.graphana, rules.all_icmp,
          rules.abr2ts]
    if cidr:
        rs = [rules.override_cidr(rule=r, cidr=cidr) for r in rs]

    rs.append(rules.all_sn)

    sg.SecurityGroupIngress = rs

    return sg


def get_elb_security_group(template, vpc, sg_name='elbsecuritygroup', cidr="10.0.0.0/16"):
    """Get elb security group containing the elb rules for management

    :param template: the template to add this subnet too.
    :param vpc: the vpc to add this subnet too.
    :param cidr: the cidr to use to create this security group rule. Defaults to the CISCO_CIDR.
    :return: security_group
    """
    sg = SecurityGroup(sg_name, template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'security group for elb'
    sg.VpcId = Ref(vpc)

    rules = Rules()
    rs = [rules.rest, rules.https]
    if cidr:
        rs = [rules.override_cidr(rule=r, cidr=cidr) for r in rs]
    sg.SecurityGroupIngress = rs
    return sg


def get_vsm_security_group(template, vpc, sg_name='vsmsecuritygroup', cidr=CISCO_CIDR):
    """Get a vsm security group containing the vsm rules for management

    :param name: unique name of the security group.
    :param template: the template to add this subnet too.
    :param vpc: the vpc to add this subnet too.
    :param cidr: the cidr to use to create this security group rule. Defaults to the CISCO_CIDR.
    :return: security_group
    """
    sg = SecurityGroup(sg_name, template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'security group for vsm'
    sg.VpcId = Ref(vpc)

    rules = Rules()
    rs = [rules.ssh, rules.http, rules.https, rules.rest, rules.all_icmp, rules.vsm1, rules.vsm2]
    if cidr:
        rs = [rules.override_cidr(rule=r, cidr=cidr) for r in rs]

    sg.SecurityGroupIngress = rs

    return sg


def get_vdcm_video_security_group(template, vpc, cidr=None):
    """Get a vdcm security group containing the default vdcm rules for video.

    :param template: the template to add this subnet too.
    :param vpc: the vpc to add this subnet too.
    :param cidr: the cidr to use to create this security group rule.
    :return: security_goup
    """
    sg = SecurityGroup('vdcmvideosecuritygroup', template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'vdcm security group for video'
    sg.VpcId = Ref(vpc)
    rules = Rules()
    rs = [rules.all_udp, rules.all_icmp, rules.all_sn]
    if cidr:
        rs = [rules.override_cidr(rule=r, cidr=cidr) for r in rs]

    sg.SecurityGroupIngress = rs
    return sg


def get_private_security_group(template, vpc, cidr, desc):
    """Get a security group containing the rules to allow all protocol on all ports from "CIDR-subnet".
    only to be used behind bastion

    :param template: the template to add this subnet too.
    :param vpc: the vpc to add this subnet too.
    :return: security_goup
    """
    sg = SecurityGroup('{}securitygroup'.format(desc), template=template)
    sg.Tags = Tags(Name=aws_name(sg.title))
    sg.GroupDescription = 'security group for {} subnet'.format(desc)
    sg.VpcId = Ref(vpc)
    rules = Rules()
    rs = [rules.all]
    if cidr:
        rs = [rules.override_cidr(rule=r, cidr=cidr) for r in rs]
    sg.SecurityGroupIngress = rs
    return sg


def rule(protocol, from_port, to_port, cidr):
    return SecurityGroupRule(IpProtocol=protocol, FromPort=from_port, ToPort=to_port, CidrIp=cidr)


class Rules(object):
    """Collection of frequently used security group rules"""

    def __init__(self):
        self.all_udp = SecurityGroupRule(IpProtocol='udp', FromPort='1', ToPort='65535', CidrIp='0.0.0.0/0')
        self.all_icmp = SecurityGroupRule(IpProtocol='icmp', FromPort='-1', ToPort='-1', CidrIp='0.0.0.0/0')
        self.all = SecurityGroupRule(IpProtocol='-1', FromPort='-1', ToPort='-1', CidrIp='0.0.0.0/0')
        self.ssh = SecurityGroupRule(IpProtocol='tcp', FromPort='22', ToPort='22', CidrIp='0.0.0.0/0')
        self.http = SecurityGroupRule(IpProtocol='tcp', FromPort='80', ToPort='80', CidrIp='0.0.0.0/0')
        self.https = SecurityGroupRule(IpProtocol='tcp', FromPort='443', ToPort='443', CidrIp='0.0.0.0/0')
        self.graphana = SecurityGroupRule(IpProtocol='tcp', FromPort='3000', ToPort='3000', CidrIp='0.0.0.0/0')
        self.iiop = SecurityGroupRule(IpProtocol='tcp', FromPort='5003', ToPort='5003', CidrIp='0.0.0.0/0')
        self.vnc = SecurityGroupRule(IpProtocol='tcp', FromPort='5901', ToPort='5901', CidrIp='0.0.0.0/0')
        self.influxdb = SecurityGroupRule(IpProtocol='tcp', FromPort='8086', ToPort='8086', CidrIp='0.0.0.0/0')
        self.rest = SecurityGroupRule(IpProtocol='tcp', FromPort='8443', ToPort='8443', CidrIp='0.0.0.0/0')
        self.all_sn = SecurityGroupRule(IpProtocol='tcp', FromPort='0', ToPort='65535', CidrIp='10.0.0.0/16')
        self.mc = SecurityGroupRule(IpProtocol='47', FromPort='0', ToPort='65535', CidrIp='10.0.0.0/16')
        self.lisa = SecurityGroupRule(IpProtocol='tcp', FromPort='8080', ToPort='8080', CidrIp='0.0.0.0/0')
        self.vsm1 = SecurityGroupRule(IpProtocol='tcp', FromPort='8902', ToPort='8902', CidrIp='0.0.0.0/0')
        self.vsm2 = SecurityGroupRule(IpProtocol='tcp', FromPort='8699', ToPort='8701', CidrIp='0.0.0.0/0')
        self.abr2ts = SecurityGroupRule(IpProtocol='tcp', FromPort='8050', ToPort='8051', CidrIp='0.0.0.0/0')
        self.ocgui = SecurityGroupRule(IpProtocol='tcp', FromPort='8443', ToPort='8443', CidrIp='0.0.0.0/0')

    @staticmethod
    def override_cidr(rule, cidr):
        """Override the cidr of a SecurityGroupRule and return the modified version"""
        new_rule = deepcopy(rule)
        new_rule.CidrIp = cidr
        return new_rule


def acl_table(template, name, vpc):
    """Create an acl table in a vpc. Individual entries need to be added using acl_entry()."""
    acl = NetworkAcl(name, template=template)
    acl.Tags = Tags(Name=aws_name(acl.title))
    acl.VpcId = Ref(vpc)
    return acl


def acl_entry(template, acl_table, name, number, protocol=-1, from_port=None, to_port=None, cidr='0.0.0.0/0',
              action='ALLOW', egress=False):
    """Create an entry in a network acl table"""
    acl_entry = NetworkAclEntry(name, template)
    acl_entry.NetworkAclId = Ref(acl_table)
    acl_entry.CidrBlock = cidr
    acl_entry.Egress = egress
    acl_entry.Protocol = protocol
    if from_port or to_port:
        acl_entry.PortRange = PortRange(From=from_port, To=to_port)
    acl_entry.RuleAction = action
    acl_entry.RuleNumber = number
    return acl_entry
