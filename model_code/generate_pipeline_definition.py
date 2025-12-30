
import os
import sys
import json

# Add parent directory to path to import pipeline
sys.path.append(os.path.dirname(__file__))

from pipeline import get_pipeline

def generate():
    # We use dummy values because the actual execution will use the role/bucket from the environment
    # The definition is what's important.
    region = os.environ.get("AWS_REGION", "us-east-1")
    pipeline = get_pipeline(
        region=region,
        role="arn:aws:iam::257949588515:role/service-role/AmazonSageMaker-ExecutionRole-Dummy",
        default_bucket="dummy-bucket",
        pipeline_name="AbalonePipeline",
        model_package_group_name="AbalonePackageGroup"
    )
    
    definition = pipeline.definition()
    
    output_path = os.path.join(os.path.dirname(__file__), "pipeline_definition.json")
    with open(output_path, "w") as f:
        f.write(definition)
    
    print(f"Pipeline definition generated at {output_path}")

if __name__ == "__main__":
    generate()
