from troposphere import Ref

from troposphere import elasticloadbalancing as elb
from troposphere.elasticloadbalancing import HealthCheck

from troposphere import elasticloadbalancingv2 as elbv2


PROD_OPS_CERTIFICATE = 'arn:aws:acm:eu-west-1:510447007788:certificate/4bffc4c8-90a6-491c-9e4e-cc06a736dd40'


def elastic_lb(template, name, instances, subnets, instance_port=443, load_balancer_port=443, instance_proto="HTTPS",
               load_balancer_proto='HTTPS', securitygroups=None, health_check=None, scheme=None):
    """Create an elastic load balancer """

    elasticlb = elb.LoadBalancer(name,
                                 template=template,
                                 Subnets=[Ref(r) for r in subnets],
                                 SecurityGroups=[Ref(r) for r in securitygroups],
                                 ConnectionDrainingPolicy=elb.ConnectionDrainingPolicy(Enabled=True, Timeout=300),
                                 CrossZone=True,
                                 Instances=[Ref(r.title) for r in instances]
                                 )

    listener = elb.Listener()
    listener.LoadBalancerPort = load_balancer_port
    listener.InstancePort = instance_port
    listener.Protocol = load_balancer_proto
    listener.InstanceProtocol = instance_proto

    if load_balancer_proto == 'HTTPS':
        listener.SSLCertificateId = PROD_OPS_CERTIFICATE

    elasticlb.Listeners = [listener]

    if health_check:
        elasticlb.HealthCheck = health_check

    if scheme:
        elasticlb.Scheme = scheme

    return elasticlb


def app_elb(template, name, subnets, instances, vpc, instance_port=443, load_balancer_port=443, instance_proto='HTTPS',
            load_balancer_proto='HTTPS', securitygroups=None):
    """Create an elastic load balancer """

    applb = elbv2.LoadBalancer(name,
                               template=template,
                               Subnets=[Ref(r) for r in subnets],
                               SecurityGroups=[Ref(r) for r in securitygroups],
                               )

    targetgroup = elbv2.TargetGroup(title=name + 'targetgroup',
                                    template=template,
                                    Port=instance_port,
                                    Protocol=instance_proto,
                                    VpcId=Ref(vpc),
                                    Targets=[elbv2.TargetDescription(Id=Ref(r)) for r in instances],
                                    HealthCheckIntervalSeconds=10,
                                    # HealthCheckPath="/",
                                    # HealthCheckPort="traffic-port",
                                    # HealthCheckProtocol="HTTP",
                                    # HealthCheckTimeoutSeconds=5,
                                    # UnhealthyThresholdCount=10,
                                    # HealthyThresholdCount=2,
                                    )

    elbv2.Listener(title=(name + 'listener'),
                   template=template,
                   DefaultActions=[elbv2.Action(TargetGroupArn=Ref(targetgroup), Type='forward')],
                   LoadBalancerArn=Ref(applb),
                   Port=load_balancer_port,
                   Protocol=load_balancer_proto,
                   )

    return applb


def health_check(name, target='TCP:22', healthy_threashold=2, unhealthy_threashold=3, interval=30, timeout=3):
    """Classic elb health check"""
    hc = HealthCheck(title=name + 'healthcheck')
    hc.HealthyThreshold = healthy_threashold
    hc.UnhealthyThreshold = unhealthy_threashold
    hc.Interval = interval
    hc.Target = target
    hc.Timeout = timeout
    return hc
