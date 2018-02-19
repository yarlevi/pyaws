#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53, elb, iam, cloudfront


def stack():
    t = template.create(description='openshift')
    keypair = template.add_keypair_parameter(t)
    hostedzonename = template.add_parameter(t, name='ClusterDnsDomainName', description='Domain name for cluster')
    deployer_ami = template.add_parameter(t, name='deployerami', description='ami used for deployer instance')
    worker_ami = template.add_parameter(t, name='workerami', description='ami used for worker, master instance')
    centos_hardned = template.add_parameter(t, name='centoshardned', description='ami used for bastion instance')
    zone1 = template.add_parameter(t, name='zone1', description='availability zone 1')
    mpeELB = "mpeELB1"

    # iam & placement group
    group = ec2.placement_group(template=t, name='openshiftgroup')
    iam_role = iam.InstanceProfiles.ecr_full(template=t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public = ec2.subnet(template=t, name='public', availability_zone=zone1, cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public, gateway_attachement=iga)
    private = ec2.subnet(template=t, name='private', availability_zone=zone1, cidr='10.0.100.0/24', vpc=network, nat=ng)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.0.0/16', desc='private')
    elb_sg = security.get_elb_security_group(template=t, vpc=network)
    openshift_gui = security.rule(protocol='tcp', from_port='8443', to_port='8443', cidr='0.0.0.0/0')
    mpe_out = security.rule(protocol='tcp', from_port='80', to_port='80', cidr='0.0.0.0/0')
    elb_sg.SecurityGroupIngress.append(openshift_gui)
    elb_sg.SecurityGroupIngress.append(mpe_out)

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=centos_hardned, type='c4.large',
                                 keypair=keypair, role='bastion', placement_group=group, iam_role=iam_role,
                                 interfaces=[(public, '10.0.0.4', bastion_sg, iga)], volume_size=64)

    # deployer
    ec2.instance_with_interfaces(template=t, name='deployer', ami=deployer_ami, type='c4.2xlarge',
                                 keypair=keypair, role='deployer', placement_group=group, iam_role=iam_role,
                                 interfaces=[(private, '10.0.100.5', private_sg, None)], volume_size=64)

    instances = []
    masters = 1
    for i in range(0, masters):
        master = ec2.instance_with_interfaces(template=t, name='master{}'.format(i+1), ami=worker_ami,
                                              type='c4.2xlarge', keypair=keypair, role='master', placement_group=group,
                                              iam_role=iam_role, interfaces=[(private, '10.0.100.1{}'.format(i),
                                                                              private_sg, None)],
                                              volume_size=64)
        instances.append(master)
    masterlb = elb.elastic_lb(template=t, name="masterELB", instances=instances, subnets=[public],
                              instance_port=8443, load_balancer_port=8443, securitygroups=[elb_sg],
                              instance_proto="TCP", load_balancer_proto="TCP",
                              health_check=elb.health_check(name='masterlbhealthcheck'))
    route53.elb(template=t, name="masterRoute", hostedzonename=hostedzonename, elasticLB=masterlb, dns='master')

    instances = []
    nodes = 2
    for i in range(0, nodes):
        worker = ec2.instance_with_interfaces(template=t, name='node{}'.format(i+1), ami=worker_ami,
                                              type='c4.4xlarge', keypair=keypair, role='worker', placement_group=group,
                                              iam_role=iam_role, volume_size=32,
                                              interfaces=[(private, '10.0.100.2{}'.format(i), private_sg, None)])
        instances.append(worker)

    mpelb = elb.elastic_lb(template=t, name=mpeELB, instances=instances, subnets=[public], instance_port=80,
                           load_balancer_port=80, instance_proto="TCP", load_balancer_proto="TCP",
                           securitygroups=[elb_sg], health_check=elb.health_check(name='masterlbhealthcheck'))
    route53.elb(template=t, name="mpeRoute", hostedzonename=hostedzonename, elasticLB=mpelb, subdomain='*')

    cloudfront.cloudfront_custom(template=t, name="cloudfront", elbname=mpeELB, originname="mpelb", enabled=True)

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
