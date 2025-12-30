from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_sagemaker as sagemaker,
)
from constructs import Construct

class SageMakerS3Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. S3 Bucket for SageMaker
        sagemaker_bucket = s3.Bucket(
            self, "SageMakerBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY, # For demo purposes
            auto_delete_objects=True, # For demo purposes
        )

        # 2. VPC
        # Look up the default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)

        # Subnets
        subnet_ids = [subnet.subnet_id for subnet in vpc.public_subnets]

        # 3. IAM Role for SageMaker
        sagemaker_role = iam.Role(
            self, "SageMakerRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            ]
        )
        # Grant S3 access
        sagemaker_bucket.grant_read_write(sagemaker_role)

        # 4. SageMaker Domain
        sagemaker_domain = sagemaker.CfnDomain(
            self, "SageMakerDomain",
            auth_mode="IAM",
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=sagemaker_role.role_arn
            ),
            domain_name="my-sagemaker-domain",
            subnet_ids=subnet_ids,
            vpc_id=vpc.vpc_id
        )

        # 5. Default User Profile
        sagemaker.CfnUserProfile(
            self, "DefaultUserProfile",
            domain_id=sagemaker_domain.attr_domain_id,
            user_profile_name="default-user",
            user_settings=sagemaker.CfnUserProfile.UserSettingsProperty(
                execution_role=sagemaker_role.role_arn
            )
        )

        # 6. Model Package Group (Model Registry)
        model_package_group = sagemaker.CfnModelPackageGroup(
            self, "AbaloneModelPackageGroup",
            model_package_group_name="AbalonePackageGroup",
            model_package_group_description="Model Package Group for Abalone Pipeline"
        )
        
        # 7. IAM Role for Pipeline Execution
        pipeline_role = iam.Role(
            self, "SageMakerPipelineRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
            ]
        )
        sagemaker_bucket.grant_read_write(pipeline_role)

        # 8. Define and Create SageMaker Pipeline
        # We generate the definition JSON locally using the SDK script
        import sys
        import os
        # Add root directory to path so we can import model_code
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if root_dir not in sys.path:
            sys.path.append(root_dir)
            
        from model_code.pipeline import get_pipeline
        
        # We need to render the pipeline definition to JSON
        # Note: We pass dummy role/bucket here because the actual execution will use the ones we define in CDK
        # or defaults. The important part is the steps structure.
        pipeline_def = get_pipeline(
            region=kwargs.get("env").region if kwargs.get("env") else "us-east-1",
            role=pipeline_role.role_arn,
            default_bucket=sagemaker_bucket.bucket_name,
            pipeline_name="AbalonePipeline",
            model_package_group_name="AbalonePackageGroup"
        )
        pipeline_definition_body = pipeline_def.definition()

        sagemaker_pipeline = sagemaker.CfnPipeline(
            self, "AbalonePipeline",
            pipeline_name="AbalonePipeline",
            pipeline_definition={"PipelineDefinitionBody": pipeline_definition_body},
            role_arn=pipeline_role.role_arn,
            tags=[{"key": "Project", "value": "Abalone"}]
        )
        sagemaker_pipeline.add_dependency(model_package_group)


        # Outputs
        CfnOutput(self, "BucketName", value=sagemaker_bucket.bucket_name)
        CfnOutput(self, "SageMakerDomainId", value=sagemaker_domain.attr_domain_id)
