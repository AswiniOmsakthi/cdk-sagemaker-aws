
import argparse
import os
import requests
import tempfile
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

# Since we are running in SageMaker Processing, we might need to install libraries if not present in the container
import logging
import scipy.sparse

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

def merge_two_dicts(x, y):
    z = x.copy()
    z.update(y)
    return z

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-test-split-ratio", type=float, default=0.3)
    args, _ = parser.parse_known_args()
    
    print("Received arguments {}".format(args))

    input_data_path = os.path.join("/opt/ml/processing/input", "abalone.csv")
    
    if not os.path.exists(input_data_path):
        logger.error(f"Input data not found at {input_data_path}")
        # List files in the directory to help debug
        input_dir = "/opt/ml/processing/input"
        if os.path.exists(input_dir):
            logger.info(f"Files in {input_dir}: {os.listdir(input_dir)}")
        else:
            logger.error(f"Input directory {input_dir} does not exist!")
        raise FileNotFoundError(f"Missing input file: {input_data_path}")

    logger.info("Reading input data from {}".format(input_data_path))
    df = pd.read_csv(input_data_path, header=None)
    df.columns = [
        "sex",
        "length",
        "diameter",
        "height",
        "whole_weight",
        "shucked_weight",
        "viscera_weight",
        "shell_weight",
        "rings",
    ]
    
    # Validation
    # Decrease rings by 1 to verify regression works (or keeps it basic)
    # The task is to predict rings.
    
    # Split Data
    split_ratio = args.train_test_split_ratio
    print("Splitting data with ratio {}".format(split_ratio))
    
    rng = np.random.RandomState(0)
    train = df.sample(frac=1 - split_ratio, random_state=rng)
    test = df.drop(train.index)
    
    # Preprocessing
    # Features: Sex is categorical, rest are numerical
    
    numerical_cols = [
        "length",
        "diameter",
        "height",
        "whole_weight",
        "shucked_weight",
        "viscera_weight",
        "shell_weight",
    ]
    categorical_cols = ["sex"]
    
    target = "rings"
    
    # Transformations
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numerical_cols),
            ("cat", categorical_transformer, categorical_cols),
        ]
    )
    
    # Fit and Transform Train
    y_train = train.pop(target)
    X_train_pre = preprocessor.fit_transform(train)
    
    # Handle sparse matrix if returned by ColumnTransformer
    if scipy.sparse.issparse(X_train_pre):
        logger.info("Converting sparse training matrix to dense.")
        X_train_pre = X_train_pre.toarray()
    
    # Transform Test
    y_test = test.pop(target)
    X_test_pre = preprocessor.transform(test)
    
    if scipy.sparse.issparse(X_test_pre):
        logger.info("Converting sparse test matrix to dense.")
        X_test_pre = X_test_pre.toarray()
    
    # Combine for output (SageMaker Training expects CSV with target in first column)
    train_output = pd.DataFrame(X_train_pre)
    train_output.insert(0, "target", y_train.values)
    
    test_output = pd.DataFrame(X_test_pre)
    test_output.insert(0, "target", y_test.values)
    
    # Save files
    train_output_path = os.path.join("/opt/ml/processing/train", "train.csv")
    test_output_path = os.path.join("/opt/ml/processing/test", "test.csv")
    
    print("Saving training data to {}".format(train_output_path))
    train_output.to_csv(train_output_path, header=False, index=False)
    
    print("Saving test data to {}".format(test_output_path))
    test_output.to_csv(test_output_path, header=False, index=False)
    
    print("Preprocessing complete")
