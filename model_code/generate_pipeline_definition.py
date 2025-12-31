
import os
import sys
import json

# Add parent directory to path to import pipeline
sys.path.append(os.path.dirname(__file__))

from pipeline import get_pipeline


def generate():
    try:
        print("Starting pipeline generation...")
        # We use dummy values because the actual execution will use the role/bucket from the environment
        # The definition is what's important.
        region = os.environ.get("AWS_REGION", "us-east-1")
        print(f"Using region: {region}")
        
        # Use PipelineSession for purely local generation without calling AWS
        from sagemaker.workflow.pipeline_context import PipelineSession
        import boto3
        dummy_boto_session = boto3.Session(region_name=region)
        mock_session = PipelineSession(boto_session=dummy_boto_session)
        # Mock default_bucket to prevent HeadBucket calls in CodeBuild
        mock_session.default_bucket = lambda: "dummy-bucket"
        # Mock upload_data to prevent actual S3 uploads during generation
        def mock_upload(path, bucket=None, key_prefix="data", **kwargs):
            return f"s3://{bucket or 'dummy-bucket'}/{key_prefix}/{os.path.basename(path)}"
        mock_session.upload_data = mock_upload
        print("Created mock PipelineSession with dummy boto3 session and flexible S3 mocks")
        
        print("Calling get_pipeline...")
        pipeline = get_pipeline(
            region=region,
            role="arn:aws:iam::257949588515:role/service-role/AmazonSageMaker-ExecutionRole-Dummy",
            default_bucket="dummy-bucket",
            sagemaker_session=mock_session,
            pipeline_name="AbalonePipeline",
            model_package_group_name="AbalonePackageGroup"
        )
        print("Pipeline object created")
        
        print("Generating definition JSON...")
        definition = pipeline.definition()
        print("Definition JSON generated")
        
        output_path = os.path.join(os.path.dirname(__file__), "pipeline_definition.json")
        with open(output_path, "w") as f:
            f.write(definition)
        
        print(f"Pipeline definition generated successfully at {output_path}")
    except Exception as e:
        print(f"FAILED to generate pipeline definition: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    generate()
