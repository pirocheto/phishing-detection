import subprocess
import time

from sklearn.model_selection import ParameterSampler

# DVC stage name
STAGE = "test_model"

# Number of experiments to run
N_EXPS = 30

# Number of jobs for DVC queue processing
N_JOBS = 5

# Seed for reproducibility
RANDOM_STATE = 42

# Flag to remove existing DVC experiments
REMOVE_EXISTING = True

# Define the parameter grid for the XGBoost model
param_grid = {
    "learning_rate": [0.01, 0.1, 0.2, 0.3],
    "n_estimators": [50, 100, 200, 300],
    "max_depth": [3, 5, 7, 9],
    "min_child_weight": [1, 3, 5, 7],
    "subsample": [0.8, 0.9, 1.0],
    "colsample_bytree": [0.8, 0.9, 1.0],
    "gamma": [0, 0.1, 0.2, 0.3],
    "scale_pos_weight": [1, 2, 3, 4],
}

# Generate random parameter samples
param_sample = list(
    ParameterSampler(
        param_grid,
        n_iter=N_EXPS,
        random_state=RANDOM_STATE,
    )
)

# Specify the classifier
classifier = "XGBoostClassifier"

# Loop over the generated parameter samples
for i, params in enumerate(param_sample):
    exp_name = f"opt-xgb-{i}"

    # Remove existing DVC experiment if specified
    if REMOVE_EXISTING:
        subprocess.run(f"dvc exp remove {exp_name} -q", shell=True)

    # Build the DVC experiment run command
    cmd = f"dvc exp run {STAGE} --queue -S classifier={classifier} -n {exp_name}"
    for param_name, param_value in params.items():
        cmd += f" -S +classifier.{param_name}={param_value}"

    try:
        # Execute the DVC experiment run command
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as err:
        print(err)

    print("-" * 15)

# Pause for a short time to allow DVC to process the queue
time.sleep(2)

# Start DVC queue processing with a specified number of jobs
subprocess.run(f"dvc queue start --jobs {N_JOBS}", shell=True, check=True)