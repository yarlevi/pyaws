#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53, iam


def stack():
    t = template.create(description='Verizon defec debiss density test')
    keypair = template.add_keypair_parameter(t)
    hostedzonename = template.add_parameter(t, name='ClusterDnsDomainName', description='Domain name for cluster')
    zone1 = template.add_parameter(t, name='zone1', description='availability zone 1')
    template.add_parameter(t, name='zone2', description='availability zone 2')
    centos_hardned = template.add_parameter(t, name='centoshardned', description='ami used for bastion instance')
    worker_ami = template.add_parameter(t, name='workerami', description='ami used for worker, master instance')
    vdcm_ami = template.add_parameter(t, name='vdcm9', description='ami used for vdcm instance')

    # iam & placement group
    group = ec2.placement_group(template=t, name='verizongrp')
    iam_role = iam.InstanceProfiles.s3_full(template=t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public = ec2.subnet(template=t, name='public', availability_zone=zone1, cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public, gateway_attachement=iga)
    private = ec2.subnet(template=t, name='private', availability_zone=zone1, cidr='10.0.100.0/24', vpc=network, nat=ng)
    video = ec2.subnet(template=t, name='video', availability_zone=zone1, cidr='10.0.200.0/24', vpc=network, nat=ng)

    # security groups
    bastion_sg = security.get_bastion_security_group(template=t, vpc=network)
    vsm_sg = security.get_vsm_security_group(template=t, vpc=network)
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.0.0/16', desc='private')
    video_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.200.0/24', desc='video')

    # bastion
    bastion = ec2.instance_with_interfaces(template=t, name='bastion', ami=centos_hardned, type='c4.large',
                                           keypair=keypair, role='bastion', placement_group=group, iam_role=iam_role,
                                           interfaces=[(public, '10.0.0.4', bastion_sg, iga)], volume_size=64)
    route53.route53(template=t, hostedzonename=hostedzonename, instance=bastion, subdomain='bastion',
                    depends='bastioneth0EIPAssociation')

    # VSM
    vsm = ec2.instance_with_interfaces(template=t, name='vsm', ami=worker_ami, type='c4.2xlarge',
                                       keypair=keypair, role='vsm', placement_group=group, iam_role=iam_role,
                                       interfaces=[(public, '10.0.0.8', vsm_sg, iga),
                                                   (private, '10.0.100.8', private_sg, None)],
                                       volume_size=64)
    route53.route53(template=t, hostedzonename=hostedzonename, instance=vsm, subdomain='vsm',
                    depends='vsmeth0EIPAssociation')

    # IP streamer
    ec2.instance_with_interfaces(template=t, name='ips', ami=worker_ami, type='c4.2xlarge',
                                 keypair=keypair, role='ips', placement_group=group, iam_role=iam_role,
                                 interfaces=[(private, '10.0.100.9', private_sg, None),
                                             (video, '10.0.200.9', video_sg, None)],
                                 volume_size=32)

    # DCM pool
    vdcm = 3
    for i in range(0, vdcm):
        ec2.instance_with_interfaces(template=t, name='vdcm{}'.format(i), ami=vdcm_ami, type='c4.8xlarge',
                                     keypair=keypair, role='vdcm', placement_group=group, iam_role=iam_role,
                                     interfaces=[(private, '10.0.100.{}'.format(i + 10), private_sg, None),
                                                 (video, '10.0.200.{}'.format(i + 10), video_sg, None)],
                                     volume_size=64)

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
