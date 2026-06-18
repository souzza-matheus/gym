"""
ai/features.py — GymVision AI Exercise Engine
================================================
Extrai um vetor de features numéricas a partir dos landmarks de um frame,
usado tanto pelo classificador de exercício quanto pelo analisador de forma.

Reaproveita angle_calculator.calculate_joint_angles() (mesma matemática usada
pela API em produção) para que o vetor de treino seja idêntico ao que o
modelo verá em inferência real.

Valores ausentes (landmark não detectado / baixa visibilidade) são
representados como NaN — a imputação fica encapsulada no Pipeline sklearn
salvo junto do modelo (ver train_*.py), nunca duplicada aqui.
"""

import math
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import LandmarkInput, JointAngles  # noqa: E402
from angle_calculator import (  # noqa: E402
    calculate_joint_angles, calculate_angle, _get,
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST, LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX,
)

NaN = float("nan")

# Ordem fixa para codificar MovementPhase como feature numérica (mesma
# constante usada em treino e inferência — nunca duplicar em outro lugar).
PHASE_ORDER: list[str] = ["UNKNOWN", "STANDING", "DESCENDING", "BOTTOM", "ASCENDING"]


def phase_to_code(phase_value: str) -> int:
    try:
        return PHASE_ORDER.index(phase_value)
    except ValueError:
        return 0


FORM_FEATURE_NAMES: list[str] = []  # preenchido abaixo, após FEATURE_NAMES

FEATURE_NAMES: list[str] = [
    "knee_angle_left", "knee_angle_right", "knee_angle_avg",
    "hip_angle_left", "hip_angle_right",
    "ankle_angle_left", "ankle_angle_right",
    "back_angle", "hip_hinge_angle",
    "frontal_weight",
    "foot_asymmetry",
    "knee_cave_pct_left", "knee_cave_pct_right",
    "knee_over_toe_left", "knee_over_toe_right",
    "shoulder_width", "hip_width", "elbow_width",
    "elbow_flare_pct", "elbow_flare_angle_lateral",
    "arm_angle_left", "arm_angle_right",
    "wrist_dev_left", "wrist_dev_right",
]

# Vetor de features usado pelo analisador de forma — inclui a fase do
# movimento (necessária para saber se, por ex., profundidade deve ser
# avaliada). O classificador de exercício usa apenas FEATURE_NAMES.
FORM_FEATURE_NAMES = FEATURE_NAMES + ["phase_code"]


def _arm_angle(sh, el, wr) -> Optional[float]:
    if sh is None or el is None or wr is None:
        return None
    return calculate_angle(sh, el, wr)


def extract_features(
    landmarks: list[LandmarkInput],
    orientation=None,
) -> tuple[list[float], dict, JointAngles, float, dict]:
    """
    Calcula o vetor de features para um frame.

    Returns:
        (vector, feature_dict, joint_angles, frontal_weight, lm_map)
        — os 4 últimos retornados para reuso por quem chama (evita
          recalcular ângulos/orientação duas vezes).
    """
    lm_map: dict[int, LandmarkInput] = {lm.landmark_type: lm for lm in landmarks}

    if orientation is None and landmarks:
        try:
            from orientation_detector import detect_orientation
            orientation = detect_orientation(landmarks)
        except ImportError:
            orientation = None

    frontal_weight: float = (
        getattr(orientation, "frontal_weight", 0.0) if orientation else 0.0
    )

    angles = calculate_joint_angles(landmarks, orientation)

    def g(idx: int):
        return _get(lm_map, idx)

    l_hip, r_hip = g(LEFT_HIP), g(RIGHT_HIP)
    l_knee, r_knee = g(LEFT_KNEE), g(RIGHT_KNEE)
    l_ankle, r_ankle = g(LEFT_ANKLE), g(RIGHT_ANKLE)
    l_sh, r_sh = g(LEFT_SHOULDER), g(RIGHT_SHOULDER)
    l_el, r_el = g(LEFT_ELBOW), g(RIGHT_ELBOW)
    l_wr, r_wr = g(LEFT_WRIST), g(RIGHT_WRIST)
    l_foot, r_foot = g(LEFT_FOOT_INDEX), g(RIGHT_FOOT_INDEX)

    knee_vals = [v for v in (angles.left_knee, angles.right_knee) if v is not None]
    knee_avg = sum(knee_vals) / len(knee_vals) if knee_vals else NaN

    foot_asymmetry = (
        abs(l_ankle.y - r_ankle.y) if (l_ankle and r_ankle) else NaN
    )

    knee_cave_left = (
        (l_knee.x - l_ankle.x) * 100 if (l_knee and l_ankle) else NaN
    )
    knee_cave_right = (
        (r_ankle.x - r_knee.x) * 100 if (r_knee and r_ankle) else NaN
    )

    knee_over_toe_left = (
        l_knee.x - l_foot.x if (l_knee and l_foot) else NaN
    )
    knee_over_toe_right = (
        r_foot.x - r_knee.x if (r_knee and r_foot) else NaN
    )

    shoulder_width = abs(r_sh.x - l_sh.x) if (l_sh and r_sh) else NaN
    hip_width = abs(r_hip.x - l_hip.x) if (l_hip and r_hip) else NaN
    elbow_width = abs(r_el.x - l_el.x) if (l_el and r_el) else NaN

    elbow_flare_pct = NaN
    if l_sh and r_sh and l_el and r_el and shoulder_width and shoulder_width > 1e-6:
        elbow_flare_pct = ((elbow_width - shoulder_width) / shoulder_width) * 100

    elbow_flare_angle_lateral = NaN
    if l_sh and l_el:
        dy = l_sh.y - l_el.y
        dz = abs(l_sh.z - l_el.z)
        if dy != 0:
            elbow_flare_angle_lateral = math.degrees(math.atan2(dz, abs(dy)))

    arm_angle_left = _arm_angle(l_sh, l_el, l_wr)
    arm_angle_right = _arm_angle(r_sh, r_el, r_wr)

    wrist_dev_left = abs(l_wr.x - l_el.x) if (l_wr and l_el) else NaN
    wrist_dev_right = abs(r_wr.x - r_el.x) if (r_wr and r_el) else NaN

    feats = {
        "knee_angle_left": angles.left_knee if angles.left_knee is not None else NaN,
        "knee_angle_right": angles.right_knee if angles.right_knee is not None else NaN,
        "knee_angle_avg": knee_avg,
        "hip_angle_left": angles.left_hip if angles.left_hip is not None else NaN,
        "hip_angle_right": angles.right_hip if angles.right_hip is not None else NaN,
        "ankle_angle_left": angles.left_ankle if angles.left_ankle is not None else NaN,
        "ankle_angle_right": angles.right_ankle if angles.right_ankle is not None else NaN,
        "back_angle": angles.back_angle if angles.back_angle is not None else NaN,
        "hip_hinge_angle": angles.hip_hinge_angle if angles.hip_hinge_angle is not None else NaN,
        "frontal_weight": frontal_weight,
        "foot_asymmetry": foot_asymmetry,
        "knee_cave_pct_left": knee_cave_left,
        "knee_cave_pct_right": knee_cave_right,
        "knee_over_toe_left": knee_over_toe_left,
        "knee_over_toe_right": knee_over_toe_right,
        "shoulder_width": shoulder_width,
        "hip_width": hip_width,
        "elbow_width": elbow_width,
        "elbow_flare_pct": elbow_flare_pct,
        "elbow_flare_angle_lateral": elbow_flare_angle_lateral,
        "arm_angle_left": arm_angle_left if arm_angle_left is not None else NaN,
        "arm_angle_right": arm_angle_right if arm_angle_right is not None else NaN,
        "wrist_dev_left": wrist_dev_left,
        "wrist_dev_right": wrist_dev_right,
    }

    vector = [feats[name] for name in FEATURE_NAMES]
    return vector, feats, angles, frontal_weight, lm_map
