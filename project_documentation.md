# AWS CDK SageMaker & S3 Pipeline (Python)

This project automates the provisioning of an Amazon SageMaker Domain and an S3 Bucket using the AWS Cloud Development Kit (CDK) in Python. It features a self-mutating CI/CD pipeline powered by AWS CodePipeline.

## 🏗️ Architecture Overview

The project is divided into two main stacks:

### 1. `PipelineStack` (The CI/CD Engine)
*   **File**: `infra_stack_aws/pipeline_stack.py`
*   **Purpose**: Creates the delivery pipeline that watches your GitHub repository.
*   **Stages**:
    *   **Source**: pulls code from GitHub (`main` branch) using your `github-token`.
    *   **Build**: Runs `pip install` and `cdk synth` to generate CloudFormation templates.
    *   **UpdatePipeline**: Self-mutates if you change the pipeline code itself.
    *   **prod**: Deploys the application infrastructure.

### 2. `SageMakerS3Stack` (The Infrastructure)
*   **File**: `infra_stack_aws/sagemaker_s3_stack.py`
*   **Purpose**: Defines the actual AWS resources we want to use.
*   **Resources Created**:
    *   **S3 Bucket**: A versioned, encrypted bucket for storing ML data and artifacts.
    *   **SageMaker Domain**: Named `my-sagemaker-domain`. configured with IAM Authentication.
    *   **IAM Role**: grants SageMaker permission to read/write to the creation S3 bucket.
    *   **User Profile**: A default user (`default-user`) to access SageMaker Studio.

---

## 🚀 How It Was Built (Step-by-Step)

Here is the journey of how this environment was set up:

1.  **Project Initialization**:
    *   We started by initializing a CDK project and migrating it to **Python**.
    *   Set up a virtual environment (`.venv`) and installed dependencies (`aws-cdk-lib`, `constructs`).

2.  **Infrastructure Definition**:
    *   We wrote `sagemaker_s3_stack.py` to define the S3 Bucket and SageMaker Domain resources using CDK constructs.

3.  **Pipeline Definition**:
    *   We wrote `pipeline_stack.py` to utilize `pipelines.CodePipeline`.
    *   Configured a `ShellStep` named "Synth" to handle dependency installation and synthesis.

4.  **Configuration**:
    *   In `app.py`, we explicitly set the AWS Account (`257949588515`) and Region (`us-east-1`) to ensure deterministic deployments.
    *   We stored your GitHub Personal Access Token in **AWS Secrets Manager** under the secret name `github-token`.

5.  **Deployment**:
    *   We ran `cdk deploy PipelineStack` once manually to bootstrap the pipeline.
    *   From then on, the pipeline took over.

---

## 🛠️ How to Manage & Update

### Making Changes
You do **not** need to run deployment commands manually.

1.  **Edit Files**: Make changes to your Python code (e.g., change bucket settings, add new resources).
2.  **Commit & Push**:
    ```bash
    git add .
    git commit -m "Describe your changes"
    git push origin main
    ```
3.  **Watch it Run**: The pipeline will automatically pick up the change, build it, and update your AWS resources.

### Accessing Resources
*   **SageMaker Studio**: Go to the [AWS Console > SageMaker > Domains](https://us-east-1.console.aws.amazon.com/sagemaker/home?region=us-east-1#/domains). Launch "Studio" for `default-user`.
*   **Pipeline Status**: Go to [AWS CodePipeline](https://us-east-1.console.aws.amazon.com/codesuite/codepipeline/pipelines/SageMakerS3Pipeline/view?region=us-east-1) to see the build history.

---

## 📂 Key Files
*   `app.py`: Application entry point.
*   `cdk.json`: CDK configuration.
*   `infra_stack_aws/`: Directory containing stack definitions.
    *   `pipeline_stack.py`: CodePipeline logic.
    *   `sagemaker_s3_stack.py`: Resource definitions.

## ⚠️ Important Notes
*   **Cost**: SageMaker resources (like verify active instances) can incur costs. If you are done, remember to **Delete** the CloudFormation stacks.
*   **GitHub Token**: If your token expires, update the `github-token` secret in AWS Secrets Manager.
