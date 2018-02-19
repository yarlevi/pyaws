#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53, elb, iam

def stack():
    t = template.create(description='helloansible webservers')
    keypair = template.add_keypair_parameter(t)
    hostedzonename = template.add_parameter(t, name='ClusterDnsDomainName', description='Domain name')
    webserverami = template.add_parameter(t, name='webserverami', description='ami used for worker, master instance')
    centos_hardned = template.add_parameter(t, name='centoshardned', description='ami used for bastion instance')
    zone1 = template.add_parameter(t, name='zone1', description='availability zone 1')
    zone2 = template.add_parameter(t, name='zone2', description='availability zone 2')

    # iam & placement group
    group = ec2.placement_group(template=t, name='helloansible')
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

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.0.0/16', desc='private')
    elb_sg = security.get_elb_security_group(template=t, vpc=network)
    rule1 = security.rule(protocol='tcp', from_port='8443', to_port='8443', cidr='0.0.0.0/0')
    rule2 = security.rule(protocol='tcp', from_port='80', to_port='80', cidr='0.0.0.0/0')
    elb_sg.SecurityGroupIngress.append(rule1)
    elb_sg.SecurityGroupIngress.append(rule2)

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=centos_hardned, type='c4.large',
                                 keypair=keypair, role='bastion', placement_group=group, iam_role=iam_role,
                                 interfaces=[(public1, '10.0.1.4', bastion_sg, iga)], volume_size=64)

    # webservers
    instances = []
    count = 2

    for i in range(0, count):
        if i % 2 == 0:
            # zone a
            webserver_network = private1
            webserver_ip = '10.0.100.2{}'
        else:
            # zone b
            webserver_network = private2
            webserver_ip = '10.0.200.2{}'

        webserver = ec2.instance_with_interfaces(template=t, name='webserver{}'.format(i+1), ami=webserverami,
                                              type='c4.large', keypair=keypair, role='webserver',
                                              volume_size=32,
                                              interfaces=[(webserver_network, webserver_ip.format(i), private_sg, None)])
        instances.append(webserver)

    websrvelb = elb.elastic_lb(template=t, name="websrvelb", instances=instances, subnets=[public1,public2], instance_port=80,
                           load_balancer_port=80, instance_proto="TCP", load_balancer_proto="TCP",
                           securitygroups=[elb_sg], health_check=elb.health_check(name='masterlbhealthcheck'))

    route53.elb(template=t, name="webserverRoute", hostedzonename=hostedzonename, elasticLB=websrvelb, subdomain='*')

    return t
if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
