import troposphere


def create(description):
    template = troposphere.Template(Description=description)
    return template


def add_parameter(template, name, description, type='String'):
    p = template.add_parameter(troposphere.Parameter(name, Type=type, Description=description))
    return p


def add_keypair_parameter(template, name='KeyPair'):
    keypair = add_parameter(template=template, name=name, description='public ssh key')
    return keypair


def add_vpcid_parameter(template):
    vpcid_param = add_parameter(template=template,
                                name="VpcId",
                                description="VpcId of your existing Virtual Private Cloud (VPC)"
                                )
    return vpcid_param


def add_publicsubnet_parameter(template, name="PublicSubnet",):
    publicsubnet_param = add_parameter(template=template,
                                       name=name,
                                       description="SubnetId of your existing Public subnet"
                                       )
    return publicsubnet_param


def add_privatesubnet_parameter(template, name="PrivateSubnet"):
    privatesubnet_param = add_parameter(template=template,
                                        name=name,
                                        description="SubnetId of your existing Private subnet"
                                        )
    return privatesubnet_param


def add_output(template, description, value):
    title = description.replace(' ', '').replace('-', '').replace('_', '')
    template.add_output([troposphere.Output(title, Description=description, Value=value)])


def add_output_ref(template, description, value):
    title = description.replace(' ', '').replace('-', '').replace('_', '')
    template.add_output([troposphere.Output(title, Description=description, Value=troposphere.Ref(value),
                                            Export=troposphere.Export(title))])


def import_value(name):
    return troposphere.ImportValue(name)


def save_file(content, file_name='stack.json'):
    """ Dump content to a file

    :param content: string content
    :param file_name: path to dump to.
    :return: None
    """
    print('* saving {}'.format(file_name))
    with open(file_name, 'w') as f:
        f.write(content)


def save_template_to_file(template, file_name='stack.json', debug=True):
    json = template.to_json()
    if debug:
        print(json)
    save_file(content=json, file_name=file_name)
