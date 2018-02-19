def common_tags(owner, environment_name, business_unit='spvss', product_family='vdcm', environment_type='development',
                migratability='0'):
    tags = {'BU': business_unit,
            'Environment Name': environment_name,
            'Environment Type': environment_type,
            'Migratability': migratability,
            'Product Family': product_family,
            'Owner': owner,
            'Data Classification': 'Cisco Restricted',
            'Data Taxonomy': 'Cisco Strategic Data',
            'Environment': 'Non-Prod',
            'Application Name': environment_name,
            'Resource Owner': owner,
            'Cisco Mail Alias': owner + '@cisco.com'
            }
    return tags


def extract_common_tags(from_tags):
    if isinstance(from_tags, list):
        from_tags_dict = tags_list_to_dict(from_tags)

    tags = {}
    for key in ['BU', 'Environment Name', 'Environment Type', 'Migratability', 'Product Family', 'Owner',
                'Data Classification', 'Data Taxonomy', 'Environment', 'Application Name', 'Resource Owner',
                'Cisco Mail Alias'
                ]:
        tags[key] = from_tags_dict[key]
    return tags


def extract_extra_tags(from_tags, tag_keys=None):
    if isinstance(from_tags, list):
        from_tags_dict = tags_list_to_dict(from_tags)

    tags = {}
    for key in tag_keys:
        try:
            tags[key] = from_tags_dict[key]
        except KeyError:
            pass
    return tags


def tags_dict_to_list(tags):
    if tags:
        tags_list = [dict(Key=key, Value=value) for key, value in tags.items()]
    else:
        tags_list = []
    return tags_list


def tags_list_to_dict(tags_list):
    tags = {tag['Key']: tag['Value'] for tag in tags_list}
    return tags


def tags_to_tag_specification(resource, tags):
    tag_specification = dict(ResourceType=resource,
                             Tags=tags_dict_to_list(tags))
    return tag_specification
