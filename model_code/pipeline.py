
import os
import boto3
import sagemaker


from sagemaker.estimator import Estimator
from sagemaker.inputs import TrainingInput
from sagemaker.processing import (
    ProcessingInput,
    ProcessingOutput,
    ScriptProcessor,
)
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.parameters import (
    ParameterInteger,
    ParameterString,
    ParameterFloat,
)
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.steps import (
    ProcessingStep,
    TrainingStep,
)
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.retry import (
    StepRetryPolicy,
    StepExceptionTypeEnum,
    SageMakerJobExceptionTypeEnum,
    SageMakerJobStepRetryPolicy,
)
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionLessThanOrEqualTo
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.functions import JsonGet, Join

def get_pipeline(
    region,
    role=None,
    default_bucket=None,
    sagemaker_session=None,
    model_package_group_name="AbalonePackageGroup",
    pipeline_name="AbalonePipeline",
    base_job_prefix="Abalone",
    processing_instance_type="ml.m5.xlarge",
    training_instance_type="ml.m5.xlarge",
):
    if sagemaker_session is None:
        sagemaker_session = sagemaker.Session()
    
    if role is None:
        try:
            role = sagemaker.get_execution_role()
        except Exception:
            # Fallback for local/CodeBuild testing
            role = "arn:aws:iam::000000000000:role/service-role/AmazonSageMaker-ExecutionRole-Dummy"
            
    if default_bucket is None:
        try:
            default_bucket = sagemaker_session.default_bucket()
        except Exception:
            default_bucket = "dummy-bucket"

    # Parameters
    processing_instance_count = ParameterInteger(name="ProcessingInstanceCount", default_value=1)
    model_approval_status = ParameterString(
        name="ModelApprovalStatus", default_value="PendingManualApproval"
    )
    input_data = ParameterString(
        name="InputDataUrl",
        default_value=f"s3://sagemaker-sample-files/datasets/tabular/abalone/abalone.csv",
    )
    execution_role = ParameterString(name="ExecutionRole", default_value=role)
    mse_threshold = ParameterFloat(name="MseThreshold", default_value=6.0)

    # 1. Processing Step
    sklearn_processor = SKLearnProcessor(
        framework_version="0.23-1",
        instance_type=processing_instance_type,
        instance_count=processing_instance_count,
        base_job_name=f"{base_job_prefix}-process",
        role=execution_role,
        sagemaker_session=sagemaker_session,
    )
    
    step_process = ProcessingStep(
        name="PreprocessData",
        processor=sklearn_processor,
        inputs=[
            ProcessingInput(source=input_data, destination="/opt/ml/processing/input"),
        ],
        outputs=[
            ProcessingOutput(output_name="train", source="/opt/ml/processing/train"),
            ProcessingOutput(output_name="test", source="/opt/ml/processing/test"),
        ],
        code="model_code/preprocess.py",
    )

    # 2. Training Step
    image_uri = sagemaker.image_uris.retrieve(
        framework="xgboost",
        region=region,
        version="1.0-1",
        py_version="py3",
        instance_type=training_instance_type,
    )
    
    xgb_train = Estimator(
        image_uri=image_uri,
        instance_type=training_instance_type,
        instance_count=1,
        output_path=f"s3://{default_bucket}/{base_job_prefix}/output",
        role=execution_role,
        sagemaker_session=sagemaker_session,
    )
    
    xgb_train.set_hyperparameters(
        objective="reg:linear",
        num_round=50,
        max_depth=5,
        eta=0.2,
        gamma=4,
        min_child_weight=6,
        subsample=0.7,
    )
    
    step_train = TrainingStep(
        name="TrainModel",
        estimator=xgb_train,
        inputs={
            "train": TrainingInput(
                s3_data=step_process.properties.ProcessingOutputConfig.Outputs[
                    "train"
                ].S3Output.S3Uri,
                content_type="text/csv",
            )
        },
    )

    # 3. Evaluation Step
    script_eval = ScriptProcessor(
        image_uri=image_uri,
        command=["python3"],
        instance_type=processing_instance_type,
        instance_count=1,
        base_job_name=f"{base_job_prefix}-eval",
        role=execution_role,
        sagemaker_session=sagemaker_session,
    )
    
    step_eval = ProcessingStep(
        name="EvaluateModel",
        processor=script_eval,
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
            ),
            ProcessingInput(
                source=step_process.properties.ProcessingOutputConfig.Outputs[
                    "test"
                ].S3Output.S3Uri,
                destination="/opt/ml/processing/test",
            ),
        ],
        outputs=[
            ProcessingOutput(output_name="evaluation", source="/opt/ml/processing/evaluation"),
        ],
        code="model_code/evaluate.py",
        property_files=[
            PropertyFile(
                name="evaluation",
                output_name="evaluation",
                path="evaluation.json"
            )
        ]
    )

    # 4. Register Step
    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri=Join(
                on="/",
                values=[
                    step_eval.properties.ProcessingOutputConfig.Outputs["evaluation"].S3Output.S3Uri,
                    "evaluation.json",
                ],
            ),
            content_type="application/json",
        )
    )
    
    step_register = RegisterModel(
        name="RegisterModel",
        estimator=xgb_train,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        content_types=["text/csv"],
        response_types=["text/csv"],
        inference_instances=["ml.m5.large", "ml.c5.large"],
        transform_instances=["ml.m5.large"],
        model_package_group_name=model_package_group_name,
        approval_status=model_approval_status,
        model_metrics=model_metrics,
    )

    # Condition Step
    cond_lte = ConditionLessThanOrEqualTo(
        left=JsonGet(
            step_name="EvaluateModel",
            property_file=step_eval.property_files[0],
            json_path="regression_metrics.mse.value",
        ),
        right=mse_threshold,
    )
    
    step_cond = ConditionStep(
        name="CheckMse",
        conditions=[cond_lte],
        if_steps=[step_register],
        else_steps=[],
    )

    # Pipeline
    pipeline = Pipeline(
        name=pipeline_name,
        parameters=[
            processing_instance_count,
            model_approval_status,
            input_data,
            mse_threshold,
            execution_role,
        ],
        steps=[step_process, step_train, step_eval, step_cond],
    )
    
    return pipeline

if __name__ == "__main__":
    # If run as a script, just print definition
    import sys
    pipeline = get_pipeline(region="us-east-1", role="arn:aws:iam::257949588515:role/service-role/AmazonSageMaker-ExecutionRole-20231230T105318") 
    print(pipeline.definition())
