
import json
import os
import tarfile
import logging
import pickle
import pandas as pd
import xgboost

import joblib
from sklearn.metrics import mean_squared_error

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

if __name__ == "__main__":
    logger.info("Starting evaluation.")
    
    # Paths in the processing container
    model_path = "/opt/ml/processing/model/model.tar.gz"
    test_path = "/opt/ml/processing/test/test.csv"
    evaluation_dir = "/opt/ml/processing/evaluation"
    output_path = os.path.join(evaluation_dir, "evaluation.json")
    
    # Ensure output directory exists
    os.makedirs(evaluation_dir, exist_ok=True)

    logger.info("Loading model.")
    with tarfile.open(model_path) as tar:
        tar.extractall(path=".")
    
    # XGBoost model is usually saved as xgboost-model
    model = pickle.load(open("xgboost-model", "rb"))
    
    logger.info("Reading test data.")
    df = pd.read_csv(test_path, header=None)
    
    y_test = df.iloc[:, 0].to_numpy()
    df.drop(df.columns[0], axis=1, inplace=True)
    X_test = xgboost.DMatrix(df.values)
    
    logger.info("Performing predictions.")
    predictions = model.predict(X_test)
    
    # Calculate MSE
    mse = mean_squared_error(y_test, predictions)
    logger.info(f"MSE: {mse}")
    
    report_dict = {
        "regression_metrics": {
            "mse": {
                "value": mse,
                "standard_deviation": "NaN"
            },
        },
    }
    
    logger.info("Writing evaluation report.")
    with open(output_path, "w") as f:
        f.write(json.dumps(report_dict))
