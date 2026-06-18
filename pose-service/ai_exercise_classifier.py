"""
ai_exercise_classifier.py — GymVision Auto-detecção de Exercício (IA)
=========================================================================
Substitui exercise_classifier.py (regras biomecânicas hardcoded) por um
RandomForestClassifier treinado em ai/train_classifier.py sobre dataset
sintético gerado por ai/dataset_generator.py — reconhece os 5 tipos de
exercício (SQUAT, DEADLIFT, LUNGE, BENCH_PRESS, BENT_OVER_ROW).

API idêntica à do módulo antigo (classify_single / classify_frames /
ClassificationResult) para ser um drop-in replacement em main.py.
"""

import logging
import os
from dataclasses import dataclass

import joblib
import numpy as np

from models import ExerciseType
from ai.features import extract_features

logger = logging.getLogger(__name__)

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "ai", "models_ai", "exercise_classifier.joblib")
_bundle: dict | None = None

# Confiança mínima para aceitar a predição do modelo — abaixo disso,
# cai para UNKNOWN (fallback para seleção manual no app).
CONFIDENCE_THRESHOLD = 0.55


@dataclass
class ClassificationResult:
    exercise_type: ExerciseType
    confidence: float
    reason: str


def _load_bundle() -> dict:
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(_MODEL_PATH)
        logger.info("Modelo de classificação de exercício carregado de %s", _MODEL_PATH)
    return _bundle


def classify_frames(frames: list) -> ClassificationResult:
    """
    Classifica o exercício a partir de múltiplos frames — faz a média das
    probabilidades previstas pelo modelo por frame (mais robusto que votar
    por classe). Retorna UNKNOWN se a confiança média ficar abaixo do
    threshold.
    """
    if not frames:
        return ClassificationResult(ExerciseType.UNKNOWN, 0.0, "sem frames")

    vectors = []
    for landmarks in frames:
        if not landmarks:
            continue
        vector, *_ = extract_features(landmarks)
        vectors.append(vector)

    if not vectors:
        return ClassificationResult(ExerciseType.UNKNOWN, 0.0, "sem landmarks")

    bundle = _load_bundle()
    pipeline = bundle["pipeline"]

    X = np.array(vectors, dtype=float)
    proba = pipeline.predict_proba(X)
    avg_proba = proba.mean(axis=0)
    classes = pipeline.classes_

    best_idx = int(avg_proba.argmax())
    confidence = float(avg_proba[best_idx])
    best_label = classes[best_idx]

    if confidence < CONFIDENCE_THRESHOLD:
        return ClassificationResult(
            ExerciseType.UNKNOWN, confidence,
            f"confiança baixa ({confidence:.0%}) para {best_label} (modelo IA)",
        )

    return ClassificationResult(
        ExerciseType(best_label), confidence, f"modelo IA: {confidence:.0%} de confiança",
    )


def classify_single(landmarks: list) -> ClassificationResult:
    """Classifica um único frame."""
    return classify_frames([landmarks])
