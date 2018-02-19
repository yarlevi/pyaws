#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53, elb


def stack():

    # deployer_ami = 'ami-9501bcec'   # cloud-init fixed
    deployer_ami = 'ami-e167e298'   # cloud-init fixed, disabled NM
    worker_ami = ec2.AMI.centos_sriov

    t = template.create(description='Monitoring test setup')
    keypair = template.add_keypair_parameter(t)
    group = ec2.placement_group(template=t, name='monitorgroup')
    iam_role = 'ECRFACC'
    hostedzonename = 'kortrijkprodops.com.'

    # network & subnets
    cidr = '10.0.0.0/16'
    network = ec2.vpc(template=t, name='vpc', cidr=cidr)
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public_subnet = ec2.subnet(template=t, name='public', cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public_subnet, gateway_attachement=iga)
    private_subnet = ec2.subnet(template=t, name='management', cidr='10.0.10.0/24', vpc=network, nat=ng)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr=cidr, desc='vdcmmanagement')
    vsm_sg = security.get_vsm_security_group(template=t, vpc=network)

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=ec2.AMI.centos_hardned, type='t2.micro',
                                 keypair=keypair, role='bastion', placement_group=None,
                                 interfaces=[
                                    (public_subnet, '10.0.0.6', bastion_sg, iga),
                                 ])

    # deployer
    ec2.instance_with_interfaces(template=t, name='deployer', ami=deployer_ami, type='c3.2xlarge',
                                 keypair=keypair, role='deployer', iam_role=iam_role,
                                 interfaces=[(private_subnet, '10.0.10.5', private_sg, None)], volume_size=64)

    master_instances = []
    masters = 1
    for i in range(0, masters):
        private_if = ec2.interface(template=t, name='master{}eth1'.format(i), subnet=private_subnet,
                                   ip_address='10.0.10.1{}'.format(i), security_groups=private_sg)
        master = ec2.instance(template=t, name='master{}'.format(i+1), ami=worker_ami, type='c4.2xlarge',
                              keypair=keypair, role='master', placement_group=group, iam_role=iam_role,
                              interfaces=[private_if], volume_size=64, )
        master_instances.append(master)
    elasticLB = elb.elastic_lb(template=t, name='masterlb', instances=master_instances, subnets=[public_subnet],
                               load_balancer_port=8443, instance_port=8443, securitygroups=[vsm_sg])
    route53.elb(template=t, name='master', hostedzonename=hostedzonename, elasticLB=elasticLB, dns='master')

    worker_instances = []
    workers = 2
    for i in range(0, workers):
        worker = ec2.instance_with_interfaces(template=t, name='worker{}'.format(i+1), ami=worker_ami,
                                              type='c4.2xlarge',
                                              keypair=keypair, role='worker', placement_group=group, iam_role=iam_role,
                                              interfaces=[(private_subnet, '10.0.10.2{}'.format(i), private_sg, None)],
                                              volume_size=32)
        worker_instances.append(worker)
    elasticLB = elb.elastic_lb(template=t, name='workerlb', instances=worker_instances, subnets=[public_subnet],
                               load_balancer_port=80, instance_port=30101, instance_proto="HTTP",
                               load_balancer_proto="HTTP", securitygroups=[vsm_sg])
    route53.elb(template=t, name='worker', hostedzonename=hostedzonename, elasticLB=elasticLB, subdomain='linear.rock')

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
