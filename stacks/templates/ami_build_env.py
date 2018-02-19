#!/usr/bin/env python
from pyaws.stacks import template, ec2, security, iam


def stack():
    t = template.create(description='stack used to build a vdcm ami')
    keypair = template.add_keypair_parameter(t)

    # iam service user & instance profile
    packer_iam_role = iam.InstanceProfiles.packer(template=t)
    iam.user(template=t, user_name='srvc_jenkins', policies=iam.Policies.jenkins(name='jenkins'), generate_key_serial=1)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public = ec2.subnet(template=t, name='public', cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public, gateway_attachement=iga)
    private = ec2.subnet(template=t, name='private', cidr='10.0.1.0/24', vpc=network, nat=ng)

    # security groups
    bastion_security_group = security.get_bastion_security_group(template=t, vpc=network)
    management_security_group = security.get_vdcm_management_security_group(template=t, vpc=network, cidr='0.0.0.0/0')

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=ec2.AMI.public_centos, type='t2.small',
                                 tags={'auto-power': 'no'}, user_data=ec2.ETH1_USER_DATA,
                                 keypair=keypair, role='bastion', placement_group=None,
                                 interfaces=[
                                     (public, '10.0.0.6', bastion_security_group, iga),
                                     (private, '10.0.1.6', management_security_group, None)
                                 ])

    # builder
    ec2.instance_with_interfaces(template=t, name='build', ami=ec2.AMI.public_centos, type='t2.small', user_data=None,
                                 keypair=keypair, role='builder', placement_group=None, tags={'auto-power': 'no'},
                                 iam_role=packer_iam_role, volume_size=40,
                                 interfaces=[
                                     (private, '10.0.1.7', management_security_group, None),
                                 ])
    return t


if __name__ == '__main__':
    stack = stack()
    template.save_template_to_file(template=stack)
