import aws_cdk as core
import aws_cdk.assertions as assertions

from infra_stack_aws.infra_stack_aws_stack import InfraStackAwsStack

# example tests. To run these tests, uncomment this file along with the example
# resource in infra_stack_aws/infra_stack_aws_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = InfraStackAwsStack(app, "infra-stack-aws")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
