"""ec2 functions"""

from troposphere import Ref, Join, GetAtt, Base64, Tags
from troposphere.ec2 import Instance, NetworkInterface, NetworkInterfaceProperty
from troposphere.ec2 import EIP, EIPAssociation
from troposphere.ec2 import SubnetNetworkAclAssociation
from troposphere.ec2 import VPC, Subnet, InternetGateway, VPCGatewayAttachment, NatGateway
from troposphere.ec2 import Route, RouteTable, SubnetRouteTableAssociation
from troposphere.ec2 import PlacementGroup
from troposphere.ec2 import BlockDeviceMapping
from troposphere.ec2 import EBSBlockDevice

from .tools import aws_name


# cloud init user data to bring up a single additional network interfaces
ETH1_USER_DATA = """#cloud-config
write_files:
  - content: |
      # created by cloud-init
      DEVICE=eth1
      ONBOOT=yes
      BOOTPROTO=dhcp
      TYPE=Ethernet
      NM_CONTROLLED=yes
      DEFROUTE=no
    path: /etc/sysconfig/network-scripts/ifcfg-eth1
    permissions: '0644'
runcmd:
  - "echo restart networking"
  - "systemctl restart network"
"""


class AMI(object):
    """Collection of frequently used AMI"""
    v2pc_image = 'ami-34ced252'
    public_centos = 'ami-0d063c6b'
    centos_sriov = 'ami-a0ed06d9'
    centos_sriov_us = 'ami-38ebe658'
    centos_hardned = 'ami-5a68af23'
    centos_hardned_us = 'ami-2a9f934a'
    vdcm_6 = 'ami-15ee156c'
    vdcm_7 = 'ami-456a913c'
    vdcm_8 = 'ami-9f6fbfe6'
    vdcm_9 = 'ami-500ec729'
    public_suse = 'ami-8bfda0ed'  # 42.2
    deployer = 'ami-e167e298'
    deployer_us = 'ami-a0e4e9c0'


class Type(object):
    T2_NANO = 't2.nano'
    T2_MICRO = 't2.micro'
    T2_SMALL = 't2.small'
    C4_LARGE = 'c4.large'
    C4_XLARGE = 'c4.xlarge'
    C4_2XLARGE = 'c4.2xlarge'
    C4_4XLARGE = 'c4.4xlarge'
    C4_8XLARGE = 'c4.8xlarge'


# aws functions
def instance(template, name, ami, type, keypair, interfaces,
             availability_zone=None, user_data=None, placement_group=None, role='unknown', iam_role=None,
             volume_size=None, tags=None):
    """Create an aws instance.

    :param template: the template to add this subnet too.
    :param name: name of the instance
    :param ami: ami for the instance
    :param type: instance type (ex: c4.8xlarge)
    :param keypair: the keypair to use of this instance
    :param interfaces: interfaces list for this instance.
    Note: when providing a single interface in a public subnet a public ip is given.
          In all other cases one should use an elastic ip.
    :param availability_zone: (optional) name of the availability zone to place this instance in.
    :param user_data: (optional) #cloud_init style or #!/bin/bash style cloud init user data to pass to the instance.
    :param placement_group: the placement group to put this instance in
    :param role: (optional) the Role tag to apply to this instance
    :param volume_size: (optional) size of the rfs in GB
    :param iam_role: (optional) name or object that points to an IamInstanceRole
    :return: instance
    """
    i = Instance(name, template=template)
    i.ImageId = ami
    i.InstanceType = type
    i.KeyName = Ref(keypair)

    i.Tags = Tags(Name=aws_name(i.title))
    if role:
        i.Tags += Tags(Role=role)

    if tags:
        i.Tags += Tags(**tags)

    if iam_role:
        if isinstance(iam_role, str):
            i.IamInstanceProfile = iam_role
        else:
            i.DependsOn = iam_role.title
            i.IamInstanceProfile = Ref(iam_role)

    if availability_zone:
        i.AvailabilityZone = availability_zone

    if placement_group:
        i.PlacementGroupName = Ref(placement_group)

    if volume_size:
        i.BlockDeviceMappings = [
            BlockDeviceMapping(DeviceName="/dev/sda1", Ebs=EBSBlockDevice(VolumeSize=volume_size))
        ]

    if interfaces:
        i.NetworkInterfaces = [NetworkInterfaceProperty(DeviceIndex=index,
                                                        NetworkInterfaceId=Ref(interface))
                               for (index, interface) in enumerate(interfaces)]

    if user_data:
        i.UserData = Base64(Join('', [line + '\n' for line in user_data.splitlines()]))

    return i


def placement_group(template, name):
    """Create an aws placement group
    :param template: the template to add this placement group too.
    :param name: name of the placement group
    :return: placement group
    """
    p = PlacementGroup(name, template=template)
    p.Strategy = 'cluster'
    return p


def interface(template, name, subnet, ip_address=None, security_groups=None, gateway_attachment=None, description=''):
    """Create an aws interface
    :param template: the template to add this subnet too.
    :param name: the name of the interface
    :param subnet: the subnet of the interface
    :param (optional) ip_address: ip address for this interface needs to match the subnet or use dhcp when empty.
    :param (list|security_group) security_groups: list of security groups for this interface
    :param gateway_attachment: dependency for an elastic ip. When provided the interface gets an elastic ip
    :param description: description for the interface
    :return: interface
    """
    n = NetworkInterface(name, template=template)
    n.Tags = Tags(Name=aws_name(n.title))
    n.Description = description
    n.SubnetId = Ref(subnet)

    if ip_address:
        n.PrivateIpAddress = ip_address

    if security_groups:
        # ensure we have a list
        if not isinstance(security_groups, list):
            security_groups = [security_groups]

        # now ref it
        n.GroupSet = [Ref(sg) for sg in security_groups]

    if gateway_attachment:
        elastic_ip(template=template, name='{}EIP'.format(name), network_interface=n,
                   gateway_attachment=gateway_attachment)

    n.SourceDestCheck = True
    return n


def vpc(template, name, cidr='10.0.0.0/16'):
    """Create an aws vpc.

    :param template: the template to add this vpc too.
    :param name: name of the vpc
    :param cidr: cidr of the vpc (ex: 10.0.0.0/16)
    :return: vpc
    """
    v = VPC(name, template=template)
    v.CidrBlock = cidr
    v.EnableDnsSupport = True
    v.EnableDnsHostnames = True
    v.Tags = Tags(Name=aws_name(v.title))
    return v


def internet_gateway(template, vpc, name='InternetGateway'):
    """"Create an aws internet_gateway and attach to a vpc.

    Both the internet_gateway and the internet_gateway_attachment are returned as these are dependencies for other
    resources.

    :param template: the template to add this vpc too.
    :param vpc: vpc to attach this internet gateway too
    :param name: name of the internet gateway
    :return: (tuple) internet_gateway, internet_gateway_attachment
    """
    ig = InternetGateway(name, template=template)
    ig.Tags = Tags(Name=aws_name(ig.title))
    iga = VPCGatewayAttachment('{}Attachment'.format(name), VpcId=Ref(vpc), InternetGatewayId=Ref(ig),
                               template=template)
    return ig, iga


def subnet(template, name, vpc, availability_zone='eu-west-1a', cidr='10.0.36.0/24', gateway=None, nat=None,
           map_public_ip=False, acl_table=None):
    """Create an aws subnet in a vpc.
    :param template: the template to add this subnet too.
    :param name: subnet name
    :param vpc: the vpc to attach this subnet to.
    :param cidr: cidr of the subnet (example: 10.0.0.0/24)
    :param (optional) availability_zone: availability_zone to use.
    :param (optional) gateway: gateway of the subnet. This makes this a public subnet by adding an internet route.
    :param (optional) map_public_ip: This only seems to work when an instance only has a single interface.
    :param (optional) acl_table: ACL table to use for this subnet. Defaults to the default acl table (ALL/ALL)
    :return: subnet
    """
    s = Subnet(name, template=template)
    s.Tags = Tags(Name=aws_name(s.title))
    s.VpcId = Ref(vpc)
    s.CidrBlock = cidr
    s.MapPublicIpOnLaunch = map_public_ip

    if availability_zone:
        s.AvailabilityZone = Ref(availability_zone)

    if gateway and nat:
        raise(RuntimeError("Don't provide an internet gateway (public) and nat gateway (private) at the same time."))

    # add public route if an internet gateway is given
    if gateway:
        # route table
        rt = RouteTable('{}RouteTable'.format(name), template=template)
        rt.Tags = Tags(Name=aws_name(rt.title))
        rt.VpcId = Ref(vpc)

        # route
        r = Route('{}Route'.format(name), template=template)
        r.DestinationCidrBlock = '0.0.0.0/0'
        r.GatewayId = Ref(gateway)
        # r.DependsOn = InternetGatewayAttachment.title
        r.RouteTableId = Ref(rt)

        # associate
        SubnetRouteTableAssociation('{}SubnetRouteTableAssociation'.format(name), template=template,
                                    RouteTableId=Ref(rt), SubnetId=Ref(s))

    # add nat route if an nat gateway is given
    if nat:
        # route table
        rt = RouteTable('{}RouteTable'.format(name), template=template)
        rt.Tags = Tags(Name=aws_name(rt.title))
        rt.VpcId = Ref(vpc)

        # route
        r = Route('{}Route'.format(name), template=template)
        r.DestinationCidrBlock = '0.0.0.0/0'
        r.NatGatewayId = Ref(nat)
        # r.DependsOn = InternetGatewayAttachment.title
        r.RouteTableId = Ref(rt)

        # associate
        SubnetRouteTableAssociation('{}SubnetRouteTableAssociation'.format(name), template=template,
                                    RouteTableId=Ref(rt), SubnetId=Ref(s))

    # add acl table if one is provided. Defaults to vpc default acl if None is provided
    if acl_table:
        at = SubnetNetworkAclAssociation('{}SubnetAclTableAssociation'.format(name), template=template)
        at.SubnetId = Ref(s)
        at.NetworkAclId = Ref(acl_table)

    return s


def elastic_ip(template, name, network_interface, gateway_attachment):
    """Create an aws elastic ip and optionally attach it to for a network interface.

    :param template: the template to add this subnet too.
    :param name: name of the elastic ip
    :param network_interface: network interface to attach this elastic ip too
    :param gateway_attachment: this is a dependency for the creation of the elastic ip.
    :return:
    """
    # Create the ip
    ip = EIP(name, template=template)
    ip.Domain = 'vpc'
    ip.DependsOn = gateway_attachment.title

    # associate the ip
    if network_interface:
        a = EIPAssociation('{}Association'.format(name), template=template)
        a.AllocationId = GetAtt(ip, 'AllocationId')
        a.NetworkInterfaceId = Ref(network_interface)
    return ip


def instance_with_interfaces(template, name, ami, type, keypair, role, interfaces, user_data=None, placement_group=None,
                             iam_role=None, volume_size=None, tags=None):
    """Create an instance with interfaces in one shot."""
    eths = []
    for i, (sn, ip, sg, iga) in enumerate(interfaces):
        eth = interface(template=template, name='{}eth{}'.format(name, i), subnet=sn,
                        ip_address=ip, security_groups=sg, gateway_attachment=iga)
        eths.append(eth)

    return instance(template=template, name=name, ami=Ref(ami), type=type, keypair=keypair,
                    interfaces=eths, role=role, user_data=user_data, placement_group=placement_group, iam_role=iam_role,
                    volume_size=volume_size, tags=tags)


def nat_gateway(template, public_subnet, gateway_attachement, name='natgateway'):
    ng = NatGateway(name, template=template)
    ng.SubnetId = Ref(public_subnet)
    ng.DependsOn = gateway_attachement.title

    # Request a public ip for the nat gateway
    eip = elastic_ip(template=template, name='{}eip'.format(name), network_interface=None,
                     gateway_attachment=gateway_attachement)
    # We need to get the AllocationID attribute rather than a typical Ref here for some inconsistent reason
    ng.AllocationId = GetAtt(eip, 'AllocationId')
    return ng
