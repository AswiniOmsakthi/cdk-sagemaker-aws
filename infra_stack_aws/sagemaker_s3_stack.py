from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    Duration,
    aws_s3 as s3,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_sagemaker as sagemaker,
    aws_lambda as lambda_,
    aws_events as events,
    aws_events_targets as targets,
    aws_logs as logs,
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
        
        # Grant access to public S3 for sample data
        # Note: sagemaker-sample-files is a public bucket, but we still need explicit permissions
        pipeline_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:ListBucket",
                "s3:ListBucketMultipartUploads",
                "s3:ListMultipartUploadParts"
            ],
            resources=[
                "arn:aws:s3:::sagemaker-sample-files",
                "arn:aws:s3:::sagemaker-sample-files/*"
            ]
        ))
        
        # Grant access to CDK assets bucket (where preprocess.py and evaluate.py are stored)
        pipeline_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=[
                f"arn:aws:s3:::cdk-hnb659fds-assets-{self.account}-{self.region}",
                f"arn:aws:s3:::cdk-hnb659fds-assets-{self.account}-{self.region}/*"
            ]
        ))
        
        # Add PassRole so the service role can pass the execution role to steps
        pipeline_role.add_to_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[pipeline_role.role_arn]
        ))
        
        # Grant CloudWatch Logs permissions for processing jobs
        pipeline_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogStreams"
            ],
            resources=["*"]
        ))

        # 8. Define and Create SageMaker Pipeline
        # We read the definition JSON that was pre-generated
        import json
        import os
        
        definition_path = os.path.join(os.path.dirname(__file__), "..", "model_code", "pipeline_definition.json")
        
        # We use a placeholder if the file doesn't exist yet (for local synth without generation)
        if os.path.exists(definition_path):
            with open(definition_path, "r") as f:
                pipeline_definition_body = f.read()
        else:
            # Fallback/Placeholder for initial synth if file missing
            pipeline_definition_body = json.dumps({"Version": "2020-12-01", "Steps": []})

        from aws_cdk import aws_s3_assets as s3_assets

        preprocess_asset = s3_assets.Asset(self, "PreprocessAsset", path=os.path.join(os.path.dirname(__file__), "..", "model_code", "preprocess.py"))
        evaluate_asset = s3_assets.Asset(self, "EvaluateAsset", path=os.path.join(os.path.dirname(__file__), "..", "model_code", "evaluate.py"))

        # Replace placeholders in the JSON with real S3 URIs using regex to find any dummy S3 paths
        import re
        pipeline_definition_body = re.sub(
            r's3://[^"]+/preprocess\.py',
            f"s3://{preprocess_asset.s3_bucket_name}/{preprocess_asset.s3_object_key}",
            pipeline_definition_body
        )
        pipeline_definition_body = re.sub(
            r's3://[^"]+/evaluate\.py',
            f"s3://{evaluate_asset.s3_bucket_name}/{evaluate_asset.s3_object_key}",
            pipeline_definition_body
        )
        # Replace the dummy execution role
        pipeline_definition_body = re.sub(
            r'arn:aws:iam::\d+:role/service-role/AmazonSageMaker-ExecutionRole-Dummy',
            pipeline_role.role_arn,
            pipeline_definition_body
        )
        # Replace dummy bucket name
        pipeline_definition_body = pipeline_definition_body.replace("dummy-bucket", sagemaker_bucket.bucket_name)
        
        # Replace the input data URL to use our bucket instead of sagemaker-sample-files
        pipeline_definition_body = re.sub(
            r's3://sagemaker-sample-files/datasets/tabular/abalone/abalone\.csv',
            f"s3://{sagemaker_bucket.bucket_name}/datasets/abalone/abalone.csv",
            pipeline_definition_body
        )

        # Fix entrypoint filenames to match the hashed asset filename in S3
        # Extract just the filename from the S3 object key (in case it has a path)
        preprocess_filename = os.path.basename(preprocess_asset.s3_object_key)
        evaluate_filename = os.path.basename(evaluate_asset.s3_object_key)
        
        # Replace entrypoint paths - handle both with and without .py extension
        pipeline_definition_body = re.sub(
            r'"/opt/ml/processing/input/code/preprocess\.py"',
            f'"/opt/ml/processing/input/code/{preprocess_filename}"',
            pipeline_definition_body
        )
        pipeline_definition_body = re.sub(
            r'"/opt/ml/processing/input/code/evaluate\.py"',
            f'"/opt/ml/processing/input/code/{evaluate_filename}"',
            pipeline_definition_body
        )
        # Also handle cases without quotes (in case JSON structure is different)
        pipeline_definition_body = pipeline_definition_body.replace(
            "/opt/ml/processing/input/code/preprocess.py",
            f"/opt/ml/processing/input/code/{preprocess_filename}"
        )
        pipeline_definition_body = pipeline_definition_body.replace(
            "/opt/ml/processing/input/code/evaluate.py",
            f"/opt/ml/processing/input/code/{evaluate_filename}"
        )

        sagemaker_pipeline = sagemaker.CfnPipeline(
            self, "AbalonePipeline",
            pipeline_name="AbalonePipeline",
            pipeline_definition={"PipelineDefinitionBody": pipeline_definition_body},
            role_arn=pipeline_role.role_arn,
            tags=[{"key": "Project", "value": "Abalone"}]
        )
        sagemaker_pipeline.add_dependency(model_package_group)

        # Grant the role permission to read the assets
        preprocess_asset.grant_read(pipeline_role)
        evaluate_asset.grant_read(pipeline_role)

        # Add custom resource to automatically start pipeline execution after initial deployment only
        # Note: We only trigger on create to avoid cancelling running executions on updates
        from aws_cdk import custom_resources as cr
        
        # Custom resource to trigger pipeline execution (only on create, not on update)
        pipeline_trigger = cr.AwsCustomResource(
            self, "PipelineTrigger",
            on_create=cr.AwsSdkCall(
                service="SageMaker",
                action="startPipelineExecution",
                parameters={"PipelineName": sagemaker_pipeline.pipeline_name},
                physical_resource_id=cr.PhysicalResourceId.of(f"{sagemaker_pipeline.pipeline_name}-{self.account}")
            ),
            # Only trigger on create, not on update to avoid cancelling running executions
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[f"arn:aws:sagemaker:{self.region}:{self.account}:pipeline/{sagemaker_pipeline.pipeline_name}"]
            )
        )
        pipeline_trigger.node.add_dependency(sagemaker_pipeline)

        # 9. Automatic Model Deployment on Approval
        # Lambda function to deploy approved model to endpoint
        deploy_lambda = lambda_.Function(
            self, "ModelDeploymentFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            timeout=Duration.minutes(15),
            environment={
                "EXECUTION_ROLE_ARN": pipeline_role.role_arn,
                "REGION": self.region
            },
            code=lambda_.Code.from_inline("""
import json
import boto3
import os
import time

region = os.environ.get('REGION', 'us-east-1')
execution_role_arn = os.environ.get('EXECUTION_ROLE_ARN')
sagemaker = boto3.client('sagemaker', region_name=region)

def handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    # Extract model package ARN from the event
    model_package_arn = event.get('detail', {}).get('ModelPackageArn', '')
    model_package_group_name = event.get('detail', {}).get('ModelPackageGroupName', '')
    
    if not model_package_arn:
        print("No ModelPackageArn found in event")
        return {"statusCode": 400, "body": "Missing ModelPackageArn"}
    
    try:
        # Get model package details
        model_package = sagemaker.describe_model_package(ModelPackageName=model_package_arn)
        model_approval_status = model_package.get('ModelApprovalStatus', '')
        
        print(f"Model Package ARN: {model_package_arn}")
        print(f"Approval Status: {model_approval_status}")
        
        if model_approval_status != 'Approved':
            print(f"Model not approved. Status: {model_approval_status}")
            return {"statusCode": 200, "body": f"Model not approved. Status: {model_approval_status}"}
        
        # Get the model data
        model_data_url = model_package['InferenceSpecification']['Containers'][0]['ModelDataUrl']
        image_uri = model_package['InferenceSpecification']['Containers'][0]['Image']
        
        endpoint_config_name = f"abalone-endpoint-config-{int(time.time())}"
        endpoint_name = "abalone-endpoint"
        model_name = f"abalone-model-{int(time.time())}"
        
        # Create model
        print(f"Creating model: {model_name}")
        sagemaker.create_model(
            ModelName=model_name,
            PrimaryContainer={
                'Image': image_uri,
                'ModelDataUrl': model_data_url
            },
            ExecutionRoleArn=execution_role_arn
        )
        
        # Create endpoint configuration
        print(f"Creating endpoint config: {endpoint_config_name}")
        sagemaker.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[{
                'VariantName': 'AllTraffic',
                'ModelName': model_name,
                'InstanceType': 'ml.m5.large',
                'InitialInstanceCount': 1,
                'InitialVariantWeight': 1.0
            }]
        )
        
        # Check if endpoint exists, if not create it, else update it
        try:
            sagemaker.describe_endpoint(EndpointName=endpoint_name)
            print(f"Updating existing endpoint: {endpoint_name}")
            sagemaker.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
        except sagemaker.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ValidationException':
                print(f"Creating new endpoint: {endpoint_name}")
                sagemaker.create_endpoint(
                    EndpointName=endpoint_name,
                    EndpointConfigName=endpoint_config_name
                )
            else:
                raise
        
        print(f"Deployment initiated for endpoint: {endpoint_name}")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Deployment initiated",
                "endpoint_name": endpoint_name,
                "endpoint_config": endpoint_config_name,
                "model_name": model_name
            })
        }
        
    except Exception as e:
        print(f"Error deploying model: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
"""),
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Grant permissions to Lambda
        deploy_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker:DescribeModelPackage",
                    "sagemaker:CreateModel",
                    "sagemaker:CreateEndpoint",
                    "sagemaker:CreateEndpointConfig",
                    "sagemaker:UpdateEndpoint",
                    "sagemaker:DescribeEndpoint",
                    "sagemaker:DescribeModel",
                    "sagemaker:DescribeEndpointConfig"
                ],
                resources=["*"]
            )
        )
        
        # Grant PassRole permission so Lambda can use the execution role
        deploy_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[pipeline_role.role_arn]
            )
        )
        
        # EventBridge rule to trigger on model approval
        approval_rule = events.Rule(
            self, "ModelApprovalRule",
            description="Trigger model deployment when model is approved",
            event_pattern=events.EventPattern(
                source=["aws.sagemaker"],
                detail_type=["SageMaker Model Package State Change"],
                detail={
                    "ModelApprovalStatus": ["Approved"],
                    "ModelPackageGroupName": [model_package_group.model_package_group_name]
                }
            )
        )
        
        approval_rule.add_target(targets.LambdaFunction(deploy_lambda))
        
        # Outputs
        CfnOutput(self, "BucketName", value=sagemaker_bucket.bucket_name)
        CfnOutput(self, "SageMakerDomainId", value=sagemaker_domain.attr_domain_id)
        CfnOutput(self, "PipelineName", value=sagemaker_pipeline.pipeline_name)
        CfnOutput(self, "EndpointName", value="abalone-endpoint", description="SageMaker endpoint name for model deployment")
        CfnOutput(self, "ModelPackageGroupName", value=model_package_group.model_package_group_name)
