#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra_stack_aws.pipeline_stack import PipelineStack

app = cdk.App()

# Replace these with your actual details
REPO_OWNER = "AswiniOmsakthi"
REPO_NAME = "cdk-sagemaker-aws"
BRANCH = "main"

PipelineStack(app, "PipelineStack",
    repo_owner=REPO_OWNER,
    repo_name=REPO_NAME,
    branch=BRANCH,
    env=cdk.Environment(account="257949588515", region="us-east-1"),
)

app.synth()
