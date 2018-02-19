from ...stacks import template, iam


def test_iam_packer_instance_profile_stack():
    t = template.create(description='test')
    iam.InstanceProfiles.packer(template=t)
    template.save_template_to_file(template=t, file_name='/tmp/stack.json')


def test_jenkins_user_and_policy_stack():
    t = template.create(description='test')
    iam.user(template=t, user_name='test', policies=iam.Policies.jenkins(name='policy'), generate_key_serial=0)
    template.save_template_to_file(template=t, file_name='/tmp/stack.json')
