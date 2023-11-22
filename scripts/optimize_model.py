import logging
import pickle
import sys
import warnings
from pathlib import Path
from pprint import pprint
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd
import yaml
from model import create_model
from rich.logging import RichHandler
from rich.pretty import pprint
from sklearn.exceptions import ConvergenceWarning
from sklearn.model_selection import cross_validate, train_test_split
from sklearn.preprocessing import LabelEncoder

from dvclive import Live

# Ignore this warnings to don't flood the terminal
# Doesn't work for n_jobs > 1
warnings.filterwarnings("ignore", category=ConvergenceWarning)

# Initialize the logger
logger = logging.getLogger("optuna")
# logger.addHandler(logging.StreamHandler(sys.stdout))
optuna.logging.disable_default_handler()
logger.addHandler(RichHandler())


# Create a folder to store Optuna logs
optunalog_path = Path("optunalog")
optunalog_path.mkdir(exist_ok=True)

# Configure storage for Optuna trials
storage = optuna.storages.JournalStorage(
    optuna.storages.JournalFileStorage(f"{str(optunalog_path)}/journal.log"),
)

# Set the random seed
SEED = 796856567
# Path to the data file
DATA_PATH = "data/data.csv"
# Number of trials to perform
N_TRIALS = 3


# Function to load data
def load_data(path):
    df = pd.read_csv(path)

    X_train, X_test, y_train, y_test = train_test_split(
        df["url"],
        df["status"],
        test_size=0.2,
        random_state=SEED,
        stratify=df["status"],
    )
    return X_train, X_test, y_train, y_test


# Function to get parameters for a trial
def get_params(trial):
    max_ngram_1 = trial.suggest_int("max_ngram_1", 1, 5)
    max_ngram_2 = trial.suggest_int("max_ngram_2", 1, 5)

    C = trial.suggest_float("C", 1e-7, 10.0, log=True)
    loss = trial.suggest_categorical("loss", ["hinge", "squared_hinge"])

    return {
        "tfidf__1__ngram_range": (1, max_ngram_1),
        "tfidf__2__ngram_range": (1, max_ngram_2),
        "cls__estimator__C": C,
        "cls__estimator__loss": loss,
    }


# Function to plot various visualizations of the Optuna study
def plot_study(study):
    from optuna.visualization.matplotlib import (
        plot_optimization_history,
        plot_param_importances,
    )

    plots = [
        ("optimization_history", plot_optimization_history),
    ]

    if len(study.trials) > 1:
        plots.append(
            ("param_importances", plot_param_importances),
        )

    for name, plot in plots:
        plt.Figure()
        plot(study)
        plt.savefig(optunalog_path / f"{name}.png")
        plt.close()


# Class to define the objective of the Optuna study
class Objective:
    def __init__(self, X_train, X_test, y_train, y_test) -> None:
        self.X_train = X_train
        self.X_test = X_test

        label_encoder = LabelEncoder()
        self.y_train = label_encoder.fit_transform(y_train)
        self.y_test = label_encoder.transform(y_test)

    def __call__(self, trial) -> Any:
        # Unique name for each experiment based on the trial number
        exp_name = f"svm-opt-{trial.number}"

        # Use dvclive for live experiment tracking
        with Live(exp_name=exp_name) as live:
            # Get parameters to test for this trial
            params = get_params(trial)
            # Log parameters
            live.log_params(trial.params)

            # Create the model using the current parameters
            model = create_model(params)
            # Train the model on the training data
            model.fit(self.X_train, self.y_train)

            # Create a directory to save the model
            model_dir = Path(live.dir) / "model"
            model_dir.mkdir(exist_ok=True)

            # Save the model to a pickle file
            model_path = model_dir / "model.pkl"
            model_path.write_bytes(pickle.dumps(model))

            # Save parameters to a YAML file
            with open(model_dir / "params.yaml", "w") as fp:
                yaml.dump(params, fp)

            # Log the model as an artifact using dvclive
            live.log_artifact(model_path, type="model", cache=False)

            scores = cross_validate(
                model,
                self.X_train,
                self.y_train,
                cv=5,
                n_jobs=1,
                scoring=[
                    "recall",
                    "precision",
                    "f1",
                    "accuracy",
                    "roc_auc",
                ],
            )

            for name, values in scores.items():
                if name.startswith("test_"):
                    value = np.mean(values)
                    live.log_metric(name, value)
                    trial.set_user_attr(name, value)

        # The returned value for optimization
        score = scores["test_roc_auc"]
        return min(np.mean(score), np.median(score))


# Function to print the best trial results
def print_best_trial(study):
    best_trial = study.best_trial
    infos = {
        "Best trial": best_trial.number,
        "Score": best_trial.value,
        "Params": best_trial.params,
        "Attrs": best_trial.user_attrs,
    }
    pprint(infos, expand_all=True)


def main():
    # Create the Optuna study object
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=SEED),
        storage=storage,
        study_name="optimize-model",
        load_if_exists=True,
    )

    # Initialize the study objective
    objective = Objective(*load_data(DATA_PATH))
    study.optimize(objective, n_trials=N_TRIALS)

    # Display the results of the best trial and plot visualizations
    print_best_trial(study)
    plot_study(study)


if __name__ == "__main__":
    main()
