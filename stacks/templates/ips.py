#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, iam


def stack():
    t = template.create(description='IPS')
    keypair = template.add_keypair_parameter(t)
    template.add_parameter(t, name='ClusterDnsDomainName', description='Domain name for cluster')
    centos_hardned = template.add_parameter(t, name='centoshardned', description='ami used for bastion instance')
    vdcm_ami = template.add_parameter(t, name='vdcm8', description='ami used for vdcm instance')
    zone1 = template.add_parameter(t, name='zone1', description='availability zone 1')
    template.add_parameter(t, name='zone2', description='availability zone 2')

    # iam & placement group
    group = ec2.placement_group(template=t, name='ipsgroup')
    iam_role = iam.InstanceProfiles.s3_full(template=t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public = ec2.subnet(template=t, name='public', availability_zone=zone1, cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public, gateway_attachement=iga)
    private = ec2.subnet(template=t, name='private', availability_zone=zone1, cidr='10.0.100.0/24', vpc=network, nat=ng)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.0.0/16', desc='private')

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=centos_hardned, type='c4.large',
                                 keypair=keypair, role='bastion', placement_group=group, iam_role=iam_role,
                                 interfaces=[(public, '10.0.0.4', bastion_sg, iga)], volume_size=64)

    # streamer
    ec2.instance_with_interfaces(template=t, name='ipstreamer', ami=centos_hardned, type='c4.2xlarge',
                                 keypair=keypair, role='ips', placement_group=group, iam_role=iam_role,
                                 interfaces=[(private, '10.0.100.5', private_sg, None)], volume_size=64)

    # vdcm
    ec2.instance_with_interfaces(template=t, name='vdcm', ami=vdcm_ami, type='c4.2xlarge',
                                 keypair=keypair, role='vdcm', placement_group=group, iam_role=iam_role,
                                 interfaces=[(private, '10.0.100.10', private_sg, None)],
                                 volume_size=64)

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
