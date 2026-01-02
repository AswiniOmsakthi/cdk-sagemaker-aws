from aws_cdk import (
    Stack,
    Stage,
    pipelines,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
from infra_stack_aws.sagemaker_s3_stack import SageMakerS3Stack

# Stage to deploy the SageMaker Stack
class MyServiceStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        SageMakerS3Stack(self, "SageMakerS3Stack")

class PipelineStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, repo_owner: str, repo_name: str, branch: str = "main", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get GitHub token from Secrets Manager
        github_token_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "GitHubToken",
            secret_name="github-token"
        )

        # Create GitHub source with authentication
        source = pipelines.CodePipelineSource.git_hub(
            f"{repo_owner}/{repo_name}",
            branch,
            authentication=github_token_secret.secret_value
        )

        pipeline = pipelines.CodePipeline(
            self, "Pipeline",
            pipeline_name="SageMakerS3Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    # Set AWS region for pipeline generation
                    "export AWS_REGION=us-east-1",
                    # Install Python dependencies
                    "pip install -r requirements.txt",
                    # Install AWS CDK CLI
                    "npm install -g aws-cdk",
                    # Generate pipeline definition
                    "python3 model_code/generate_pipeline_definition.py",
                    # Synthesize CDK app
                    "cdk synth"
                ],
                primary_output_directory="cdk.out"
            ),
            # Enable self-mutation so pipeline can update itself
            self_mutation=True
        )

        pipeline.add_stage(MyServiceStage(self, "Prod", env=kwargs.get("env")))
