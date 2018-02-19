#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, iam


def stack():
    t = template.create(description='base vpc')
    keypair = template.add_keypair_parameter(t)

    zone_1 = template.add_parameter(t, name='zone1', description='availability zone 1')
    zone_2 = template.add_parameter(t, name='zone2', description='availability zone 2')
    zone_3 = template.add_parameter(t, name='zone3', description='availability zone 3')

    worker_ami = template.add_parameter(t, name='workerami', description='ami used for worker, master instance')
    centos_hardned = template.add_parameter(t, name='centoshardned', description='ami used for bastion instance')

    iam_role = iam.InstanceProfiles.ec2_full(t)

    # vpc
    vpc_param = ec2.vpc(template=t, name='vpc', cidr='10.242.0.0/16')
    # network & subnets
    ig, iga = ec2.internet_gateway(template=t, vpc=vpc_param)

    public_net_1 = ec2.subnet(template=t, name='PublicA', vpc=vpc_param, availability_zone=zone_1,
                              cidr='10.242.0.0/26', gateway=ig)
    public_net_2 = ec2.subnet(template=t, name='PublicB', vpc=vpc_param, availability_zone=zone_2,
                              cidr='10.242.0.64/26', gateway=ig)
    public_net_3 = ec2.subnet(template=t, name='PublicC', vpc=vpc_param, availability_zone=zone_3,
                              cidr='10.242.0.128/26', gateway=ig)
    ng_a = ec2.nat_gateway(template=t, public_subnet=public_net_1, gateway_attachement=iga, name='NatgatewayA')
    ng_b = ec2.nat_gateway(template=t, public_subnet=public_net_2, gateway_attachement=iga, name='NatgatewayB')
    ng_c = ec2.nat_gateway(template=t, public_subnet=public_net_3, gateway_attachement=iga, name='NatgatewayC')
    private_net_1 = ec2.subnet(template=t, name='PrivateA', vpc=vpc_param, availability_zone=zone_1,
                               cidr='10.242.2.0/24', nat=ng_a)
    private_net_2 = ec2.subnet(template=t, name='PrivateB', vpc=vpc_param, availability_zone=zone_2,
                               cidr='10.242.3.0/24', nat=ng_b)
    private_net_3 = ec2.subnet(template=t, name='PrivateC', vpc=vpc_param, availability_zone=zone_3,
                               cidr='10.242.4.0/24', nat=ng_c)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=vpc_param)

    # create bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=centos_hardned, type='c4.large',
                                 keypair=keypair, role='bastion',
                                 interfaces=[(public_net_1, '10.242.0.4', bastion_sg, iga)])

    # vpc deployer
    ec2.instance_with_interfaces(template=t, name='vpcdeployer', ami=worker_ami, type='c4.large',
                                 keypair=keypair, role='vpcdeployer', iam_role=iam_role,
                                 interfaces=[(public_net_1, '10.242.0.5', bastion_sg, iga)], volume_size=32)

    template.add_output_ref(template=t, description='vpc_id', value=vpc_param)
    template.add_output_ref(template=t, description='public_net_1', value=public_net_1)
    template.add_output_ref(template=t, description='public_net_2', value=public_net_2)
    template.add_output_ref(template=t, description='public_net_3', value=public_net_3)
    template.add_output_ref(template=t, description='private_net_1', value=private_net_1)
    template.add_output_ref(template=t, description='private_net_2', value=private_net_2)
    template.add_output_ref(template=t, description='private_net_3', value=private_net_3)
    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
