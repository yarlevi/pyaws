import boto3
import datetime

"""Remove cruft from an aws account.

This code is written in a single file so it could easily be added into a lambda automation.

Currently supports:
 - available volumes (all)
 - vdcm-debug images that meet certain conditions (not shared, not in use and older than 2 weeks)
"""


def tags_list_to_dict(tags_list):
    tags = {tag['Key']: tag['Value'] for tag in tags_list}
    return tags


def delete_unused_volumes(region):
    print('Deleting unused volumes')
    ec2 = boto3.client('ec2', region_name=region)

    filters = [{'Name': 'status', 'Values': ['available']}]

    volumes = ec2.describe_volumes(Filters=filters)
    volume_ids = [volume['VolumeId'] for volume in volumes['Volumes']]

    if len(volume_ids):
        for volume_id in volume_ids:
            print('Deleting volume_id: ' + volume_id)
            ec2.delete_volume(VolumeId=volume_id)
    else:
        print('No Volumes are eligible to delete.')
    return False


def get_all_vdcm_debug_ami(region):
    ec2 = boto3.client('ec2', region_name=region)

    # get all vdcm debug ami's
    images = ec2.describe_images(Filters=[dict(Name='tag:vdcm_version', Values=['*']),
                                          dict(Name='name', Values=['*debug*']),
                                          dict(Name='state', Values=['available']),
                                          ])['Images']

    if not len(images):
        raise(Exception('no images found'))

    return images


def get_amis_that_are_used_by_instances(region):
    ec2 = boto3.resource("ec2", region_name=region)
    instance_images = set([instance.image_id for instance in ec2.instances.all()])
    return instance_images


def images_that_are_too_young(images):
    now = datetime.datetime.utcnow()
    two_weeks_ago = now - datetime.timedelta(weeks=2)
    print(two_weeks_ago)

    young_images = [image['ImageId'] for image in images
                    if datetime.datetime.strptime(image['CreationDate'], "%Y-%m-%dT%H:%M:%S.000Z") > two_weeks_ago]
    return young_images


def images_that_are_shared(images, region):
    shared_images = [image['ImageId'] for image in images if is_image_shared(image['ImageId'], region=region)]
    return shared_images


def is_image_shared(image_id, region):
    ec2 = boto3.resource('ec2', region_name=region)
    image = ec2.Image(image_id)
    response = image.describe_attribute(Attribute='launchPermission')
    permissions = response['LaunchPermissions']
    return True if permissions else False


def get_all_vdcm_ami(region):
    ec2 = boto3.client('ec2', region_name=region)

    # get all vdcm debug ami's
    images = ec2.describe_images(Filters=[dict(Name='tag:vdcm_version', Values=['*']),
                                          dict(Name='name', Values=['*debug*']),
                                          dict(Name='state', Values=['available']),
                                          ])['Images']

    if not len(images):
        print('no images found')
        return False

    for image in images:
        tags = tags_list_to_dict(image['Tags'])

        print('{ami:15}{name:40}{version:12}{creation_date}'.format(ami=image['ImageId'], name=image['Name'],
                                                                    version=tags['vdcm_version'],
                                                                    creation_date=image['CreationDate']))
    return images


def print_image_list(images):
    for image in images:
        tags = tags_list_to_dict(image['Tags'])

        print('{ami:15}{name:40}{version:12}{creation_date}'.format(ami=image['ImageId'], name=image['Name'],
                                                                    version=tags['vdcm_version'],
                                                                    creation_date=image['CreationDate']))


def print_image_list_of_dict(images):
    for image in images:
        print('{ami:15}{name:40}{version:12}{creation_date} {keep}'.format(ami=image['ami'], name=image['name'],
                                                                           version=image['version'],
                                                                           creation_date=image['creation_date'],
                                                                           keep=image['keep']))


def delete_ami(image_id, region):
    ec2 = boto3.resource('ec2', region_name=region)
    image = ec2.Image(image_id)
    snapshot_id = image.block_device_mappings[0]['Ebs']['SnapshotId']
    print('deregister ami {}'.format(image_id))
    image.deregister()
    print('removing snapshot {}'.format(snapshot_id))
    snapshot = ec2.Snapshot(snapshot_id)
    snapshot.delete()


def clean_vdcm_ami(region):
    print('getting all images')
    all_images = get_all_vdcm_ami(region=region)
    print_image_list(all_images)
    print('found: {} images'.format(len(all_images)))

    print('\ngetting shared images')
    shared_images = images_that_are_shared(images=all_images, region=region)
    print(shared_images)
    print('found: {} shared images'.format(len(shared_images)))

    print('\ngetting in use images (all in use images, not limited to vdcm')
    in_use_images = get_amis_that_are_used_by_instances(region=region)
    print(in_use_images)
    print('found: {} in use images'.format(len(in_use_images)))

    print('\ngetting young (< 2 weeks) images')
    young_images = images_that_are_too_young(all_images)
    print(young_images)
    print('found: {} young images'.format(len(young_images)))

    # convert to list of dictionaries with keep flag added
    image_list = []
    for image in all_images:
        d = dict(ami=image['ImageId'],
                 name=image['Name'],
                 version=tags_list_to_dict(image['Tags'])['vdcm_version'],
                 creation_date=image['CreationDate'],
                 keep=''
                 )

        if image['ImageId'] in in_use_images:
            d['keep'] = 'this image is in use by an instance, '

        if image['ImageId'] in shared_images:
            d['keep'] += 'this image is shared, '

        if image['ImageId'] in young_images:
            d['keep'] += 'this image is still young, '

        if not d['keep']:
            d['keep'] = 'DELETE'

        image_list.append(d)

    print('\nall images:')
    print_image_list_of_dict(image_list)
    print('--')

    to_keep = [image for image in image_list if image['keep'] != 'DELETE']
    to_delete = [image for image in image_list if image['keep'] == 'DELETE']

    print('\nto keep images:')
    print_image_list_of_dict(to_keep)
    print('{} images to keep'.format(len(to_keep)))

    print('\nto delete images:')
    print_image_list_of_dict(to_delete)
    print('{} images to delete'.format(len(to_delete)))

    if not to_delete:
        print('No AMI to deregister')
    else:
        print('delete AMIs:')
        for image in to_delete:
            delete_ami(image_id=image['ami'], region=region)


def lambda_handler(event, context):
    region = 'eu-west-1'

    clean_vdcm_ami(region=region)

    delete_unused_volumes(region=region)


if __name__ == '__main__':
    lambda_handler(None, None)
