"""
exercise_classifier.py — GymVision Auto-detecção de Exercício
=============================================================
Detecta o tipo de exercício a partir de landmarks MediaPipe via regras biomecânicas.
Confiança < CONFIDENCE_THRESHOLD → retorna UNKNOWN (fallback para seleção manual).

Regras por exercício:
  SQUAT:          joelho < 120°, tronco ereto < 35°, pés simétricos
  LUNGE:          joelho < 120°, pés assimétricos (um à frente)
  DEADLIFT:       tronco inclinado > 30°, joelhos quase retos > 130°
  BENCH_PRESS:    ombros horizontais (deitado), cotovelos abaixo dos ombros
  BENT_OVER_ROW:  tronco inclinado > 45°
"""

import math
from dataclasses import dataclass
from typing import Optional

from models import LandmarkInput, ExerciseType
from angle_calculator import (
    _get,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
)

CONFIDENCE_THRESHOLD = 0.65  # confiança mínima para retornar exercício detectado


@dataclass
class ClassificationResult:
    exercise_type: ExerciseType
    confidence: float
    reason: str


def _angle_3pts(a, b, c) -> Optional[float]:
    if a is None or b is None or c is None:
        return None
    v1x, v1y = a.x - b.x, a.y - b.y
    v2x, v2y = c.x - b.x, c.y - b.y
    dot = v1x * v2x + v1y * v2y
    mag = math.hypot(v1x, v1y) * math.hypot(v2x, v2y)
    if mag < 1e-6:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def _classify_frame(landmarks: list) -> dict:
    """Retorna {ExerciseType -> confidence} para um único frame."""
    lm = {lm.landmark_type: lm for lm in landmarks}

    l_sh  = _get(lm, LEFT_SHOULDER)
    r_sh  = _get(lm, RIGHT_SHOULDER)
    l_hip = _get(lm, LEFT_HIP)
    r_hip = _get(lm, RIGHT_HIP)
    l_kn  = _get(lm, LEFT_KNEE)
    r_kn  = _get(lm, RIGHT_KNEE)
    l_an  = _get(lm, LEFT_ANKLE)
    r_an  = _get(lm, RIGHT_ANKLE)
    l_el  = _get(lm, LEFT_ELBOW)
    r_el  = _get(lm, RIGHT_ELBOW)

    # Ângulo do joelho (flexão)
    knee_angle = (_angle_3pts(l_hip, l_kn, l_an)
                  or _angle_3pts(r_hip, r_kn, r_an))

    # Inclinação do tronco em relação à vertical (0° = de pé, 90° = deitado)
    trunk_angle = None
    if l_sh and l_hip:
        dy = abs(l_sh.y - l_hip.y)
        dx = abs(l_sh.x - l_hip.x)
        if dy > 1e-6:
            trunk_angle = math.degrees(math.atan2(dx, dy))

    # Assimetria vertical dos tornozelos (SQUAT simétrico vs LUNGE assimétrico)
    foot_asymmetry = abs(l_an.y - r_an.y) if l_an and r_an else None

    scores: dict = {}

    # ── SQUAT: joelho < 120° + tronco ereto + pés simétricos ─────────────────
    if knee_angle is not None and knee_angle < 120.0:
        c = 0.35
        if trunk_angle is not None and trunk_angle < 35.0:
            c += 0.35
        if foot_asymmetry is not None and foot_asymmetry < 0.08:
            c += 0.20
        if knee_angle < 100.0:
            c += 0.10
        if c >= 0.50:
            scores[ExerciseType.SQUAT] = min(c, 0.95)

    # ── LUNGE: joelho < 120° + pés assimétricos ──────────────────────────────
    if (knee_angle is not None and knee_angle < 120.0
            and foot_asymmetry is not None and foot_asymmetry >= 0.08):
        scores[ExerciseType.LUNGE] = 0.70

    # ── DEADLIFT: tronco inclinado (> 30°) + joelhos retos (> 130°) ──────────
    if trunk_angle is not None and trunk_angle > 30.0:
        if knee_angle is not None and knee_angle > 130.0:
            c = min(0.90, 0.50 + (trunk_angle - 30.0) / 80.0)
            scores[ExerciseType.DEADLIFT] = c

    # ── BENCH PRESS: ombros horizontais + cotovelos abaixo dos ombros ─────────
    if l_sh and r_sh and l_el and r_el:
        sh_dy = abs(l_sh.y - r_sh.y)
        if sh_dy < 0.06:
            el_avg_y = (l_el.y + r_el.y) / 2
            sh_avg_y = (l_sh.y + r_sh.y) / 2
            if el_avg_y > sh_avg_y + 0.04:
                scores[ExerciseType.BENCH_PRESS] = 0.72

    # ── BENT-OVER ROW: tronco muito inclinado (> 45°) ─────────────────────────
    if trunk_angle is not None and trunk_angle > 45.0:
        c = min(0.90, 0.55 + (trunk_angle - 45.0) / 45.0)
        scores[ExerciseType.BENT_OVER_ROW] = c

    return scores


def classify_frames(frames: list) -> ClassificationResult:
    """
    Classifica o exercício a partir de múltiplos frames.
    Votação ponderada por confiança — maior score acumulado vence.
    Retorna UNKNOWN se confiança < CONFIDENCE_THRESHOLD.
    """
    if not frames:
        return ClassificationResult(ExerciseType.UNKNOWN, 0.0, "sem frames")

    total: dict = {}
    for frame_lms in frames:
        for ex_type, conf in _classify_frame(frame_lms).items():
            total[ex_type] = total.get(ex_type, 0.0) + conf

    if not total:
        return ClassificationResult(ExerciseType.UNKNOWN, 0.0, "nenhuma regra ativada")

    n = len(frames)
    best = max(total, key=lambda t: total[t])
    confidence = min(total[best] / n, 1.0)

    if confidence < CONFIDENCE_THRESHOLD:
        return ClassificationResult(
            ExerciseType.UNKNOWN, confidence,
            f"confiança baixa ({confidence:.0%}) para {best.value}"
        )

    return ClassificationResult(best, confidence, f"score={confidence:.0%}")


def classify_single(landmarks: list) -> ClassificationResult:
    """Classifica um único frame."""
    return classify_frames([landmarks])
