from troposphere import Ref, Join, GetAtt
from troposphere.route53 import RecordSetType


def route53(template, instance, hostedzonename, type="A", subdomain=None, dns=None, depends=None):
    """Is is assumed that a hosted zone already has been registered with Amazon Route 53"""

    mydnsrecord = template.add_resource(RecordSetType(
        title=instance.title + "dns",
        HostedZoneName=Join("", [Ref(hostedzonename), '.']),
        Name=Join("", ['' if not subdomain else subdomain + '.',
                       Ref("AWS::StackName"), '' if not dns else "-" + dns, ".",
                       Ref(hostedzonename), '.']),
        Type=type,
        TTL="300",
        ResourceRecords=[GetAtt(instance.title, "PublicIp")],
        ))
    if depends:
        mydnsrecord.DependsOn = depends

    return mydnsrecord


def elb(template, name, elasticLB, hostedzonename, subdomain=None, dns=None):
    """Is is assumed that a hosted zone already has been registered with Amazon Route 53"""
    mydnsrecord = template.add_resource(RecordSetType(
        name,
        HostedZoneName=Join("", [Ref(hostedzonename), '.']),
        Name=Join("", ['' if not subdomain else subdomain + '.',
                       Ref("AWS::StackName"), '' if not dns else "-" + dns, ".",
                       Ref(hostedzonename), '.']),
        Type="CNAME",
        TTL="300",
        ResourceRecords=[GetAtt(elasticLB, "DNSName")],
        ))
    return mydnsrecord
