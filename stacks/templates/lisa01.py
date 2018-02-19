#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, iam, route53, elb


def stack():
    t = template.create(description='Lisa test setup')
    keypair = template.add_keypair_parameter(t)
    group = ec2.placement_group(template=t, name='lisagroup')

    iam_s3_full = iam.InstanceProfiles.s3_full(template=t)
    iam_ec2_full = iam.InstanceProfiles.ec2_full(template=t)

    # network & subnets
    cidr = '10.0.0.0/16'
    network = ec2.vpc(template=t, name='vpc', cidr=cidr)
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public_subnet = ec2.subnet(template=t, name='public', cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public_subnet, gateway_attachement=iga)
    private_subnet = ec2.subnet(template=t, name='management', cidr='10.0.10.0/24', vpc=network, nat=ng)
    video_subnet = ec2.subnet(template=t, name='video', cidr='10.0.100.0/24', vpc=network)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    # in order for the pyaws magic to find this network to work, this needs to be called 'vdcmmanagement'
    mgmt_sg = security.get_private_security_group(template=t, vpc=network, cidr=cidr, desc='vdcmmanagement')
    # in order for the pyaws magic to find this network to work, this needs to be called vdcmvideo
    video_sg = security.get_private_security_group(template=t, vpc=network, cidr=cidr, desc='vdcmvideo')

    # bastion
    ec2.instance_with_interfaces(template=t, name='bastion', ami=ec2.AMI.centos_hardned, type='t2.micro',
                                 keypair=keypair, role='bastion', placement_group=None,
                                 interfaces=[
                                     (public_subnet, '10.0.0.6', bastion_sg, iga),
                                 ])

    # testserver
    testserver = ec2.instance_with_interfaces(template=t, name='testserver', ami=ec2.AMI.public_centos,
                                              type='t2.medium',
                                              keypair=keypair, role='maggie', volume_size=32, iam_role=iam_ec2_full,
                                              interfaces=[(private_subnet, '10.0.10.5', mgmt_sg, None),
                                                          ]
                                              )

    # ips
    ec2.instance_with_interfaces(template=t, name='streamer', ami=ec2.AMI.centos_sriov, type='c4.2xlarge',
                                 keypair=keypair,
                                 role='ips', user_data=ec2.ETH1_USER_DATA, placement_group=group, iam_role=iam_s3_full,
                                 volume_size=64,
                                 interfaces=[(private_subnet, '10.0.10.9', mgmt_sg, None),
                                             (video_subnet, '10.0.100.9', video_sg, None)])
    # vdcm used to stream
    ec2.instance_with_interfaces(template=t, name='vdcmstreamer', ami=ec2.AMI.vdcm_8, type='c4.2xlarge',
                                 keypair=keypair,
                                 role='vdcmstreamer', placement_group=group, iam_role=iam_s3_full,
                                 interfaces=[(private_subnet, '10.0.10.10', mgmt_sg, None),
                                             (video_subnet, '10.0.100.10', video_sg, None)])

    pool_of_vdcm = 0
    for i in range(0, pool_of_vdcm):
        ec2.instance_with_interfaces(template=t, name='vdcm{}'.format(i), ami=ec2.AMI.vdcm_9, type='c4.4xlarge',
                                     keypair=keypair, role='vdcm', placement_group=group,
                                     interfaces=[(private_subnet, '10.0.10.{}'.format(100 + i), mgmt_sg, None),
                                                 (video_subnet, '10.0.100.{}'.format(100 + i), video_sg, None)])

    hostedzonename = 'kortrijkprodops.com.'
    elasticLB = elb.elastic_lb(template=t, name='elb' + testserver.title, instances=[testserver],
                               subnets=[public_subnet],
                               instance_port=443, load_balancer_port=443, securitygroups=[bastion_sg])
    route53.elb(template=t, name='testserverdns', hostedzonename=hostedzonename, elasticLB=elasticLB, dns='testserver')

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
