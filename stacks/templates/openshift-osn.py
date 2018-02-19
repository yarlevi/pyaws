#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53, elb, iam


def stack():
    t = template.create(description='openshift')
    keypair = template.add_keypair_parameter(t)
    vpc_param = template.add_vpcid_parameter(t)
    hostedzonename = template.add_parameter(t, name='ClusterDnsDomainName', description='Domain name for cluster')
    hostedzonename_video = template.add_parameter(t, name='VideoDnsDomainName', description='Domain name for cluster')

    worker_ami = template.add_parameter(t, name='workerami', description='ami used for worker, master instance')
    deployer_ami = template.add_parameter(t, name='deployerami', description='ami used for deployer instance')

    public_net_1 = template.add_publicsubnet_parameter(t, "PublicSubnet01")
    public_net_2 = template.add_publicsubnet_parameter(t, "PublicSubnet02")
    public_net_3 = template.add_publicsubnet_parameter(t, "PublicSubnet03")
    public_nets = [public_net_1, public_net_2, public_net_3]

    private_net_1 = template.add_privatesubnet_parameter(t, "PrivateSubnet01")
    private_net_2 = template.add_privatesubnet_parameter(t, "PrivateSubnet02")
    private_net_3 = template.add_privatesubnet_parameter(t, "PrivateSubnet03")
    private_nets = [private_net_1, private_net_2, private_net_3]

    iam_role_ecr = iam.InstanceProfiles.ecr_full(template=t)

    # security groups
    private_sg = security.get_private_security_group(template=t, vpc=vpc_param, cidr='10.242.0.0/16', desc='private')
    video_elb_sg = security.get_http_security_group(template=t, vpc=vpc_param, sg_name='CiscoVideo')
    video_elb_sg_osn = security.get_http_security_group(template=t, vpc=vpc_param, sg_name='OSNVideo',
                                                        cidr=['80.227.100.0/23', '80.227.119.0/24'])
    master_elb_sg = security.get_elb_security_group(template=t, vpc=vpc_param, cidr=security.CISCO_CIDR)

    # deployer
    ec2.instance_with_interfaces(template=t, name='deployer', ami=deployer_ami, type='c4.2xlarge',
                                 keypair=keypair, role='deployer', iam_role=iam_role_ecr,
                                 interfaces=[(private_net_1, '10.242.2.6', private_sg, None)], volume_size=64)
    masters = []
    num_masters = 3
    for i in range(0, num_masters):
        zone = i % 3
        master = ec2.instance_with_interfaces(template=t, name='master{}'.format(i+1), ami=worker_ami,
                                              type='c4.2xlarge', keypair=keypair, role='master',
                                              interfaces=[(private_nets[zone], None, private_sg, None)],
                                              volume_size=64)
        masters.append(master)

    masterelb = elb.elastic_lb(template=t, name="masterELB", instances=masters,
                               subnets=public_nets,
                               instance_port=8443, load_balancer_port=8443,
                               instance_proto='TCP', load_balancer_proto='TCP',
                               securitygroups=[master_elb_sg])
    masterelbint = elb.elastic_lb(template=t, name="masterELBint", instances=masters,
                                  subnets=private_nets,
                                  instance_port=8443, load_balancer_port=8443,
                                  instance_proto='TCP', load_balancer_proto='TCP',
                                  securitygroups=[private_sg], scheme="internal")
    route53.elb(template=t, name="masterdns", hostedzonename=hostedzonename, elasticLB=masterelb,
                dns='master',)
    route53.elb(template=t, name="masterdnsint", hostedzonename=hostedzonename, elasticLB=masterelbint,
                dns='int-master')

    nodes = []
    num_nodes = 2
    for i in range(0, num_nodes):
        zone = i % 3
        worker = ec2.instance_with_interfaces(template=t, name='node{}'.format(i+1), ami=worker_ami,
                                              type='c4.4xlarge', keypair=keypair, role='worker',
                                              volume_size=32,
                                              interfaces=[(private_nets[zone], None, private_sg, None)])
        nodes.append(worker)

    mpeelb = elb.elastic_lb(template=t, name="mpeELB", instances=nodes,
                            subnets=public_nets,
                            instance_port=80, load_balancer_port=80,
                            instance_proto="HTTP", load_balancer_proto="HTTP",
                            securitygroups=[video_elb_sg, video_elb_sg_osn])

    route53.elb(template=t, name="mpeRoute", hostedzonename=hostedzonename_video, elasticLB=mpeelb, subdomain='*')

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
