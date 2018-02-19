from troposphere.cloudfront import DefaultCacheBehavior, ForwardedValues, DistributionConfig, Origin
from troposphere.cloudfront import Distribution, CustomOrigin
from troposphere import GetAtt


def cloudfront_custom(template, name, elbname, originname, enabled=True):
    """Create a cloudfront distribution of the custom origin type """
    template.add_resource(Distribution(
        name,
        DistributionConfig=DistributionConfig(
            Origins=[Origin(Id=originname,
                            DomainName=GetAtt(elbname, 'DNSName'),
                            CustomOriginConfig=CustomOrigin(OriginProtocolPolicy="match-viewer"))],
            DefaultCacheBehavior=DefaultCacheBehavior(
                            TargetOriginId=originname,
                            ForwardedValues=ForwardedValues(
                                QueryString=False),
                            ViewerProtocolPolicy="allow-all"),
            Enabled=enabled)
         ))
