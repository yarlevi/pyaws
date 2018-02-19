#!/usr/bin/env python
from pyaws.stacks import ec2, security, template, route53


def stack():
    t = template.create(description='ABRE2E')
    keypair = template.add_keypair_parameter(t)
    group = ec2.placement_group(template=t, name='abre2egrp')
    iam_role = 'S3FACC'
    hostzoneID = 'Z32UL3FL00PEML'

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    public_sn = ec2.subnet(template=t, name='public', cidr='10.0.0.0/24', vpc=network, gateway=ig)
    ng = ec2.nat_gateway(template=t, public_subnet=public_sn, gateway_attachement=iga)
    private_sn = ec2.subnet(template=t, name='private', cidr='10.0.100.0/24', vpc=network, nat=ng)

    # security groups
    a = [(security.CISCO_CIDR, 'sgbastionkor')]
    bastion_sg = [security.get_bastion_security_group(template=t, vpc=network, sg_name=name, cidr=cidr)
                  for cidr, name in a]
    b = [(security.CISCO_CIDR, 'sgvsmkor')]
    vsm_sg = [security.get_vsm_security_group(template=t, vpc=network, sg_name=namevsm, cidr=cidrvsm)
              for cidrvsm, namevsm in b]
    c = [(security.CISCO_CIDR, 'sgmpekor')]
    mpe_sg = [security.get_vsm_security_group(template=t, vpc=network, sg_name=namempe, cidr=cidrmpe)
              for cidrmpe, namempe in c]
    private_sg = security.get_private_security_group(template=t, vpc=network, cidr='10.0.100.0/24', desc='private')

    # create bastion
    public_if = ec2.interface(template=t, name='bastioneth0', subnet=public_sn, gateway_attachment=iga,
                              ip_address='10.0.0.4', security_groups=bastion_sg)
    private_if = ec2.interface(template=t, name='bastioneth1', subnet=private_sn, ip_address='10.0.100.4',
                               security_groups=private_sg)
    bastion = ec2.instance(template=t, name='bastion', ami=ec2.AMI.centos_sriov, type='c4.large', keypair=keypair,
                           interfaces=[public_if, private_if], iam_role=iam_role, placement_group=group, role='bastion')
    route53.route53(template=t, hostedzonename=hostzoneID, instance=bastion, depends='bastioneth0EIPAssociation')

    # VSM
    public_if = ec2.interface(template=t, name='vsmeth0', subnet=public_sn, gateway_attachment=iga,
                              ip_address='10.0.0.8', security_groups=vsm_sg)
    private_if = ec2.interface(template=t, name='vsmeth1', subnet=private_sn, ip_address='10.0.100.8',
                               security_groups=private_sg)
    vsm = ec2.instance(template=t, name='vsm', ami=ec2.AMI.centos_sriov, type='c4.large', keypair=keypair,
                       user_data=ec2.ETH1_USER_DATA,
                       interfaces=[public_if, private_if], iam_role=iam_role, placement_group=group, role='vsm')
    route53.route53(template=t, hostedzonename=hostzoneID, instance=vsm, depends='vsmeth0EIPAssociation')

    # v2pc
    for i, name in enumerate(('launcher', 'repo', 'master')):
        mgmt = ec2.interface(template=t, name='{}eth0'.format(name), subnet=private_sn,
                             ip_address='10.0.100.{}'.format(i + 5), security_groups=private_sg)
        ec2.instance(template=t, name='{}'.format(name), ami=ec2.AMI.v2pc_image, type='c4.large', keypair=keypair,
                     interfaces=[mgmt], role=name, iam_role=iam_role, user_data=ec2.ETH1_USER_DATA,
                     placement_group=group)

    # am-mce
    for i, name in enumerate(('am', 'mce')):
        mgmt = ec2.interface(template=t, name='{}eth0'.format(name), subnet=private_sn,
                             ip_address='10.0.100.{}'.format(i + 20),
                             security_groups=private_sg)
        ec2.instance(template=t, name='{}'.format(name), ami=ec2.AMI.v2pc_image, type='c4.large', keypair=keypair,
                     interfaces=[mgmt], placement_group=group, role=name, iam_role=iam_role,
                     user_data=ec2.ETH1_USER_DATA)

    # mpe
    public_if = ec2.interface(template=t, name='mpeeth0', subnet=public_sn, gateway_attachment=iga,
                              ip_address='10.0.0.22', security_groups=mpe_sg)
    private_if = ec2.interface(template=t, name='mpeeth1', subnet=private_sn,
                               ip_address='10.0.100.22', security_groups=private_sg)
    mpe = ec2.instance(template=t, name='mpe', ami=ec2.AMI.v2pc_image, type='c4.large', keypair=keypair,
                       interfaces=[public_if, private_if], placement_group=group, role='mpe', iam_role=iam_role,
                       user_data=ec2.ETH1_USER_DATA)
    route53.route53(template=t, hostedzonename=hostzoneID, instance=mpe, depends='mpeeth0EIPAssociation')

    # vdcm
    private_if = ec2.interface(template=t, name='vdcmeth0', subnet=private_sn, ip_address='10.0.100.10',
                               security_groups=private_sg)
    ec2.instance(template=t, name='vdcm', ami=ec2.AMI.vdcm_8, type='c4.2xlarge', keypair=keypair,
                 interfaces=[private_if], placement_group=group, role='vdcm', iam_role=iam_role)

    return t


if __name__ == '__main__':
    t = stack()
    template.save_template_to_file(t)
