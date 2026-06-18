"""
ai/train_form_analyzer.py — treina os modelos de análise de forma
======================================================================
Para cada exercício com dataset de forma gerado (ai/data/form_<ex>.csv),
treina:
  1. Um MultiOutputClassifier (RandomForest) que prevê, para cada tipo de
     erro do exercício, um rótulo em {NONE, LOW, MEDIUM, HIGH}.
  2. Um RandomForestRegressor que prevê o score contínuo (0-100).

Ambos dentro de um único Pipeline com imputação embutida, salvos em
ai/models_ai/form_<exercicio>.joblib — autocontidos.
"""

import csv
import json
import os
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models import ExerciseType  # noqa: E402
from ai.features import FORM_FEATURE_NAMES  # noqa: E402
from ai.dataset_generator import FORM_ERROR_COLUMNS  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models_ai")
os.makedirs(MODELS_DIR, exist_ok=True)

N_FEATURES = len(FORM_FEATURE_NAMES)


def load_dataset(path: str, error_columns: list[str]):
    with open(path) as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    X = np.array([[float(v) if v not in ("", "nan") else np.nan for v in row[:N_FEATURES]]
                  for row in rows], dtype=float)
    n_err = len(error_columns)
    Y_err = np.array([row[N_FEATURES:N_FEATURES + n_err] for row in rows])
    y_score = np.array([float(row[N_FEATURES + n_err]) for row in rows])
    return X, Y_err, y_score


def train_one(exercise_type: ExerciseType):
    name = exercise_type.value.lower()
    columns = FORM_ERROR_COLUMNS[exercise_type]
    path = os.path.join(DATA_DIR, f"form_{name}.csv")
    X, Y_err, y_score = load_dataset(path, columns)

    X_train, X_test, Ye_train, Ye_test, ys_train, ys_test = train_test_split(
        X, Y_err, y_score, test_size=0.2, random_state=42,
    )

    imputer = SimpleImputer(strategy="constant", fill_value=-1.0)
    X_train_imp = imputer.fit_transform(X_train)
    X_test_imp = imputer.transform(X_test)

    err_clf = MultiOutputClassifier(
        RandomForestClassifier(
            n_estimators=150, max_depth=12, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    )
    err_clf.fit(X_train_imp, Ye_train)
    Ye_pred = err_clf.predict(X_test_imp)

    accs = {}
    for i, col in enumerate(columns):
        accs[col] = round(accuracy_score(Ye_test[:, i], Ye_pred[:, i]), 4)

    score_reg = RandomForestRegressor(
        n_estimators=150, max_depth=12, min_samples_leaf=3,
        random_state=42, n_jobs=-1,
    )
    score_reg.fit(X_train_imp, ys_train)
    ys_pred = score_reg.predict(X_test_imp)
    mae = mean_absolute_error(ys_test, ys_pred)

    print(f"\n=== {exercise_type.value} ===")
    print("  Acurácia por erro:", accs)
    print(f"  Score MAE (held-out): {mae:.2f}")

    model_path = os.path.join(MODELS_DIR, f"form_{name}.joblib")
    joblib.dump({
        "imputer": imputer,
        "error_classifier": err_clf,
        "score_regressor": score_reg,
        "feature_names": FORM_FEATURE_NAMES,
        "error_columns": columns,
    }, model_path)

    meta_path = os.path.join(MODELS_DIR, f"form_{name}.meta.json")
    with open(meta_path, "w") as f:
        json.dump({"error_accuracy": accs, "score_mae": mae,
                   "n_train": len(X_train), "n_test": len(X_test)}, f, indent=2)

    print(f"  Modelo salvo em {model_path}")


if __name__ == "__main__":
    for ex in (ExerciseType.SQUAT, ExerciseType.DEADLIFT, ExerciseType.BENCH_PRESS):
        train_one(ex)
