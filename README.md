# AWS CDK SageMaker & S3 Pipeline (Python)

This project automates the provisioning of an Amazon SageMaker Domain and an S3 Bucket using the AWS Cloud Development Kit (CDK) in Python. It features a self-mutating CI/CD pipeline powered by AWS CodePipeline.

## Architecture

*   **PipelineStack**: Sets up AWS CodePipeline + CodeBuild to verify and deploy changes automatically.
*   **SageMakerS3Stack**: Provisions:
    *   S3 Bucket (Versioning Enabled)
    *   SageMaker Domain (`my-sagemaker-domain`)
    *   Default User Profile

## Workflow

This project follows a **GitOps** workflow:

1.  **Develop**: Modify the Python code in `infra_stack_aws/`.
2.  **Push**: Commit changes to the `main` branch.
3.  **Deploy**: The AWS CodePipeline detects the commit, builds the project, and updates the infrastructure.

## Prerequisites

*   AWS CDK CLI installed (`npm install -g aws-cdk`)
*   Python 3.9+ and `virtualenv`
*   AWS Credentials configured for region `us-east-1`.

## Setup (Local)

1.  Create and activate virtual environment:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Operations

*   **Monitor Pipeline**: [AWS CodePipeline Console](https://us-east-1.console.aws.amazon.com/codesuite/codepipeline/pipelines/SageMakerS3Pipeline/view?region=us-east-1)
*   **Access SageMaker**: [SageMaker Console](https://us-east-1.console.aws.amazon.com/sagemaker/home?region=us-east-1#/domains)

## Project Structure
*   `app.py`: Entry point.
*   `infra_stack_aws/pipeline_stack.py`: CI/CD configuration.
*   `infra_stack_aws/sagemaker_s3_stack.py`: Infrastructure resources.
