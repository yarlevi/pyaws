#!/usr/bin/env python3
from pyaws.stacks import ec2, security, template


def stack():
    t = template.create(description='demo stack')
    keypair = template.add_keypair_parameter(t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    management_subnet = ec2.subnet(template=t, name='ManagementSubnet', cidr='10.0.0.0/24', vpc=network, gateway=ig)

    # security groups
    management_security_group = security.get_vdcm_management_security_group(template=t, vpc=network)

    # 2 machine
    for i in range(1, 3):
        eth = ec2.interface(template=t, name='machine{}eth0'.format(i), subnet=management_subnet,
                            security_groups=management_security_group, gateway_attachment=iga)

        ec2.instance(template=t, name='machine{}'.format(i), ami=ec2.AMI.public_centos, type='t2.micro',
                     keypair=keypair, interfaces=[eth], role='demo-machine')
    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
