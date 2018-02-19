from ...stacks import ec2, template


def test_simple_stack():
    t = template.create(description='test')
    keypair = template.add_keypair_parameter(t)

    # network & subnets
    network = ec2.vpc(template=t, name='vpc', cidr='10.0.0.0/16')
    ig, iga = ec2.internet_gateway(template=t, vpc=network)
    management_subnet = ec2.subnet(template=t, name='ManagementSubnet', cidr='10.0.0.0/24', vpc=network, gateway=ig)

    eth = ec2.interface(template=t, name='eth0', subnet=management_subnet, gateway_attachment=iga)

    ec2.instance(template=t, name='machine', ami='bla', type='t2.micro', keypair=keypair,
                 interfaces=[eth], role='demo-machine')

    template.save_template_to_file(template=t, file_name='/tmp/stack.json')

    return t
