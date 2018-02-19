"""Collection of tools that can run on an aws machine to gather information."""
import subprocess
import shlex
from tempfile import NamedTemporaryFile
import requests


def run_shell(command):
    """Run a shell command.

    Raise an exception in case of a non-zero return code or time out.
    Prints stdout and stderr on screen.
    """
    print('+' + command)
    args = shlex.split(command)
    subprocess.check_call(args)


def read_magic_url(resource):
    metadata_url = 'http://169.254.169.254/latest/{}'.format(resource)
    text = requests.get(metadata_url).text
    return text


def read_metadata(resource):
    text = read_magic_url('meta-data/{}'.format(resource))
    return text


def assert_is_aws_instance():
    # based on http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/identify_ec2_instances.html
    # could be implemented with pure python:
    # https://stackoverflow.com/questions/32048703/pkcs7-signature-verifies-with-openssl-but-not-with-m2crypto

    try:
        with open('/sys/hypervisor/uuid') as f:
            uuid = f.read()
    except IOError:
        raise(EnvironmentError('Not an aws instance'))

    # probabbly and ec2 instance if we find ec2 here
    if uuid[0:3].lower() != 'ec2':
        raise(EnvironmentError('Not an aws instance'))


def assert_is_aws_instance_secure():
    # get to the metadata service
    identity_document = read_magic_url('dynamic/instance-identity/document')
    # identity_signature = read_magic_url('dynamic/instance-identity/signature')
    identity_pkcs7 = read_magic_url('dynamic/instance-identity/pkcs7')

    temp_identity_pkcs7 = NamedTemporaryFile()
    temp_identity_pkcs7.write('-----BEGIN PKCS7-----\n')
    temp_identity_pkcs7.write(identity_pkcs7 + '\n')
    temp_identity_pkcs7.write('-----END PKCS7-----\n')
    temp_identity_pkcs7.flush()

    temp_identity_document = NamedTemporaryFile()
    temp_identity_document.write(identity_document)
    temp_identity_document.flush()

    call = 'openssl smime -verify -in {pkcs7} -inform PEM -content {document} -certfile aws.pub -noverify > /dev/null'
    call = call.format(pkcs7=temp_identity_pkcs7.name, document=temp_identity_document.name)
    try:
        run_shell(call)
    except subprocess.CalledProcessError:
        raise (EnvironmentError('Not an aws instance'))


def get_instance_id():
    instance_id = read_metadata('instance-id')
    return instance_id


def get_instance_region():
    availability_zone = read_metadata('placement/availability-zone')
    return availability_zone[:-1]
