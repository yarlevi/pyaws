from troposphere import Ref, Join


def aws_name(name):
    """Helper function that takes a resource name and add a heading stack name to it for standardization.

    :param name: The resource name
    :return: formatted resource name
    """
    return Join('-', [Ref("AWS::StackName"), name])
