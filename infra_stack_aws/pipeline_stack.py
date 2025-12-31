from aws_cdk import (
    Stack,
    Stage,
    pipelines,
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

        pipeline = pipelines.CodePipeline(
            self, "Pipeline",
            pipeline_name="SageMakerS3Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.git_hub(f"{repo_owner}/{repo_name}", branch),
                commands=[
                    "pip install -r requirements.txt",
                    "python3 model_code/generate_pipeline_definition.py",
                    "npx cdk synth"
                ]
            )
        )

        pipeline.add_stage(MyServiceStage(self, "Prod", env=kwargs.get("env")))
