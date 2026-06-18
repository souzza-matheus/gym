"""
ai/train_classifier.py — treina o classificador de tipo de exercício
========================================================================
Lê ai/data/exercise_classification.csv (gerado por dataset_generator.py)
e treina um RandomForestClassifier dentro de um Pipeline sklearn que já
inclui a imputação de valores ausentes (NaN) — o artefato salvo em
ai/models_ai/exercise_classifier.joblib é autocontido: quem carrega não
precisa saber como tratar landmarks faltantes.
"""

import csv
import json
import os
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ai.features import FEATURE_NAMES  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models_ai")
os.makedirs(MODELS_DIR, exist_ok=True)


def load_dataset(path: str):
    with open(path) as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    n_features = len(FEATURE_NAMES)
    X = np.array([[float(v) if v not in ("", "nan") else np.nan for v in row[:n_features]]
                  for row in rows], dtype=float)
    y = np.array([row[n_features] for row in rows])
    return X, y


def main():
    path = os.path.join(DATA_DIR, "exercise_classification.csv")
    X, y = load_dataset(path)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value=-1.0)),
        ("clf", RandomForestClassifier(
            n_estimators=200, max_depth=14, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred)
    print(f"Acurácia (held-out): {acc:.4f}\n{report}")

    model_path = os.path.join(MODELS_DIR, "exercise_classifier.joblib")
    joblib.dump({
        "pipeline": pipeline,
        "feature_names": FEATURE_NAMES,
        "classes": sorted(set(y.tolist())),
    }, model_path)

    meta_path = os.path.join(MODELS_DIR, "exercise_classifier.meta.json")
    with open(meta_path, "w") as f:
        json.dump({"accuracy": acc, "n_train": len(X_train), "n_test": len(X_test)}, f, indent=2)

    print(f"Modelo salvo em {model_path}")


if __name__ == "__main__":
    main()
