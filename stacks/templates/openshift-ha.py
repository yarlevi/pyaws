#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53, elb, iam


def stack():
    t = template.create(description='openshift-ha')

    keypair = template.add_keypair_parameter(t)
    hostedzonename = template.add_parameter(t, name='ClusterDnsDomainName', description='Domain name for cluster')
    deployer_ami = template.add_parameter(t, name='deployerami', description='ami used for deployer instance')
    worker_ami = template.add_parameter(t, name='workerami', description='ami used for worker, master instance')
    centos_hardned = template.add_parameter(t, name='centoshardned', description='ami used for bastion instance')
    zone1 = template.add_parameter(t, name='zone1', description='availability zone 1')
    zone2 = template.add_parameter(t, name='zone2', description='availability zone 2')
    # iam & placement group
    # group = ec2.placement_group(template=t, name='openshiftgroup')
    iam_role = iam.InstanceProfiles.ecr_full(template=t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)

    # zone a
    public1 = ec2.subnet(template=t, name='public1', availability_zone=zone1, cidr='10.0.1.0/24', vpc=network,
                         gateway=ig)
    nat1 = ec2.nat_gateway(template=t, public_subnet=public1, gateway_attachement=iga, name='nat1')
    private1 = ec2.subnet(template=t, name='private1', availability_zone=zone1, cidr='10.0.100.0/24', vpc=network,
                          nat=nat1)

    # zone b
    public2 = ec2.subnet(template=t, name='public2', availability_zone=zone2, cidr='10.0.2.0/24', vpc=network,
                         gateway=ig)
    nat2 = ec2.nat_gateway(template=t, public_subnet=public2, gateway_attachement=iga, name='nat2')
    private2 = ec2.subnet(template=t, name='private2', availability_zone=zone2, cidr='10.0.200.0/24', vpc=network,
                          nat=nat2)

    publicnets = [public1, public2]
    privatenets = [private1, private2]

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.0.0/16', desc='private')
    elb_sg = security.get_elb_security_group(template=t, vpc=network)
    mpe_out = security.rule(protocol='tcp', from_port='80', to_port='80', cidr='0.0.0.0/0')
    elb_sg.SecurityGroupIngress=[mpe_out]
    master_elb_sg = security.get_elb_security_group(template=t, vpc=network, sg_name='mastersecuritygroup',
                                                    cidr=security.CISCO_CIDR)

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=centos_hardned, type='c4.large',
                                 keypair=keypair, role='bastion',
                                 interfaces=[(public1, '10.0.1.4', bastion_sg, iga)], volume_size=64)

    # deployer
    ec2.instance_with_interfaces(template=t, name='deployer', ami=deployer_ami, type='c4.2xlarge',
                                 keypair=keypair, role='deployer', iam_role=iam_role,
                                 interfaces=[(private1, '10.0.100.5', private_sg, None)], volume_size=64)

    # masters
    master1 = ec2.instance_with_interfaces(template=t, name='master1', ami=worker_ami, type='c4.2xlarge',
                                           keypair=keypair, role='master',
                                           interfaces=[(private1, '10.0.100.11', private_sg, None)], volume_size=64)

    master2 = ec2.instance_with_interfaces(template=t, name='master2', ami=worker_ami, type='c4.2xlarge',
                                           keypair=keypair, role='master',
                                           interfaces=[(private2, '10.0.200.11', private_sg, None)], volume_size=64)

    masterlb = elb.elastic_lb(template=t, name="masterLB", instances=[master1, master2], subnets=publicnets,
                              instance_port=8443, load_balancer_port=8443, securitygroups=[master_elb_sg],
                              load_balancer_proto='TCP', instance_proto='TCP',
                              health_check=elb.health_check(name='masterlbhealthcheck'))
    route53.elb(template=t, name="masterDns", hostedzonename=hostedzonename, elasticLB=masterlb, dns='master')
    masterlbint = elb.elastic_lb(template=t, name="masterLBint", instances=[master1, master2], subnets=privatenets,
                                 instance_port=8443, load_balancer_port=8443, securitygroups=[private_sg],
                                 load_balancer_proto='TCP', instance_proto='TCP',
                                 health_check=elb.health_check(name='masterlbhealthcheck'), scheme="internal")
    route53.elb(template=t, name="masterDnsInt", hostedzonename=hostedzonename, elasticLB=masterlbint, dns='int-master')

    # workers
    instances = []
    nodes = 2

    for i in range(0, nodes):
        if i % 2 == 0:
            # zone a
            node_network = private1
            node_ip = '10.0.100.2{}'
        else:
            # zone b
            node_network = private2
            node_ip = '10.0.200.2{}'

        worker = ec2.instance_with_interfaces(template=t, name='node{}'.format(i+1), ami=worker_ami,
                                              type='c4.4xlarge', keypair=keypair, role='worker',
                                              volume_size=32,
                                              interfaces=[(node_network, node_ip.format(i), private_sg, None)])
        instances.append(worker)

    mpelb = elb.app_elb(template=t, name="mpeLB", subnets=publicnets, instances=instances, vpc=network,
                        securitygroups=[elb_sg], instance_port=80, load_balancer_port=80, instance_proto="HTTP",
                        load_balancer_proto="HTTP")
    route53.elb(template=t, name="mpeRoute", hostedzonename=hostedzonename, elasticLB=mpelb, subdomain='*')

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
