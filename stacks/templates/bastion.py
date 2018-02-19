from pyaws.stacks import template, ec2, security


def stack():
    t = template.create(description='Bastion')
    keypair = template.add_keypair_parameter(t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')

    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public = ec2.subnet(template=t, name='public', cidr='10.0.0.0/24', vpc=network, gateway=ig)

    ng = ec2.nat_gateway(template=t, public_subnet=public, gateway_attachement=iga)
    private = ec2.subnet(template=t, name='private', cidr='10.0.100.0/24', vpc=network, nat=ng)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    mgmt_sg = security.get_vdcm_management_security_group(template=t, vpc=network, cidr='0.0.0.0/0')

    ec2.instance_with_interfaces(template=t, name='bastion', ami=ec2.AMI.public_centos, type='c4.xlarge',
                                 keypair=keypair, role='bastion', placement_group=None, user_data=ec2.ETH1_USER_DATA,
                                 interfaces=[
                                    (public, '10.0.0.6', bastion_sg, iga),
                                    (private, '10.0.100.6', mgmt_sg, None)
                                 ])

    ec2.instance_with_interfaces(template=t, name='test', ami=ec2.AMI.public_centos, type='c4.large',
                                 keypair=keypair, role='test', placement_group=None,
                                 interfaces=[(private, '10.0.100.7', mgmt_sg, None)], user_data=None)

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
