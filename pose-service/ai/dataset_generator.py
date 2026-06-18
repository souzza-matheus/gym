"""
ai/dataset_generator.py — GymVision AI Exercise Engine
==========================================================
Gera datasets sintéticos rotulados para treinar:
  1. O classificador de tipo de exercício (5 exercícios)
  2. Os analisadores de forma/erro (SQUAT, DEADLIFT, BENCH_PRESS)

Estratégia (bootstrap / weak supervision):
  - Os LANDMARKS são construídos via geometria inversa (ai/synthetic_body.py)
    a partir de alvos biomecânicos amostrados aleatoriamente, cobrindo todo
    o espectro entre "forma perfeita" e "forma claramente errada" — inclui
    ruído gaussiano para evitar que o modelo apenas memorize os mesmos
    cortes rígidos do motor de regras.
  - Os RÓTULOS de erro/score do dataset de forma vêm do motor de regras
    atual (exercise_analyzer.py), usado aqui como "professor". Uma correção
    deliberada é aplicada: o gate de fase do BACK_ROUNDED do deadlift no
    código original só dispara em ASCENDING/BOTTOM, mas a fase ASCENDING
    nunca é produzida em produção (analyze() nunca passa prev_angle) — ou
    seja, o alerta de lombar arredondada efetivamente nunca disparava
    durante a descida. Aqui o gate é ampliado para qualquer fase != STANDING,
    corrigindo esse ponto cego sem alterar o threshold biomecânico (30°).
  - O tipo de exercício é conhecido por construção (não precisa de professor).
"""

import csv
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import ExerciseType, MovementPhase, RiskLevel  # noqa: E402
from orientation_detector import detect_orientation  # noqa: E402
from angle_calculator import calculate_joint_angles  # noqa: E402
from models import DetectedError, ErrorType  # noqa: E402
from exercise_analyzer import (  # noqa: E402
    detect_phase, calculate_score, _analyze_squat, _analyze_bench_press,
)
from ai.synthetic_body import build_frame  # noqa: E402
from ai.features import extract_features, FEATURE_NAMES, FORM_FEATURE_NAMES, phase_to_code  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

ORIENTATION_BUCKETS = ["LATERAL", "ANGLED", "FRONTAL"]

SQUAT_ERROR_COLUMNS = [
    "DEPTH_INSUFFICIENT", "KNEE_CAVE_LEFT", "KNEE_CAVE_RIGHT",
    "KNEE_OVER_TOE_LEFT", "KNEE_OVER_TOE_RIGHT", "BACK_NOT_STRAIGHT",
]
DEADLIFT_ERROR_COLUMNS = ["BACK_ROUNDED", "HIPS_TOO_HIGH"]
BENCH_ERROR_COLUMNS = ["ELBOW_FLARE", "ELBOW_INSUFFICIENT_RANGE", "WRIST_BENT"]

FORM_ERROR_COLUMNS = {
    ExerciseType.SQUAT: SQUAT_ERROR_COLUMNS,
    ExerciseType.DEADLIFT: DEADLIFT_ERROR_COLUMNS,
    ExerciseType.BENCH_PRESS: BENCH_ERROR_COLUMNS,
}


def _analyze_deadlift_teacher(lm, angles, phase, frontal_weight=0.0):
    """
    Cópia de exercise_analyzer._analyze_deadlift com o gate de fase do
    BACK_ROUNDED ampliado para != STANDING (ver docstring do módulo).
    HIPS_TOO_HIGH mantém o gate original (STANDING) — está correto, checa
    o lockout final.
    """
    from models import DetectedError, ErrorType
    from exercise_analyzer import DEADLIFT_BACK_ANGLE_MAX, DEADLIFT_HIP_ANGLE_STANDING

    errors = []
    if phase != MovementPhase.STANDING and phase != MovementPhase.UNKNOWN:
        if angles.back_angle is not None and angles.back_angle > DEADLIFT_BACK_ANGLE_MAX:
            risk = RiskLevel.HIGH if angles.back_angle > DEADLIFT_BACK_ANGLE_MAX * 1.5 else RiskLevel.MEDIUM
            errors.append(DetectedError(
                error_type=ErrorType.BACK_ROUNDED, risk_level=risk,
                description=f"Lombar arredondada: {angles.back_angle:.0f}°",
                joint_angle=angles.back_angle, threshold_violated=DEADLIFT_BACK_ANGLE_MAX,
            ))

    if phase == MovementPhase.STANDING:
        hip_angle = angles.left_hip or angles.right_hip
        if hip_angle and hip_angle < DEADLIFT_HIP_ANGLE_STANDING:
            errors.append(DetectedError(
                error_type=ErrorType.HIPS_TOO_HIGH, risk_level=RiskLevel.LOW,
                description=f"Quadril não estendido: {hip_angle:.0f}°",
                joint_angle=hip_angle, threshold_violated=DEADLIFT_HIP_ANGLE_STANDING,
            ))
    return errors


def _analyze_squat_teacher(lm, angles, phase, frontal_weight=0.0):
    """
    Encapsula _analyze_squat() e corrige um gate vazio: o original só
    avalia DEPTH_INSUFFICIENT quando phase==BOTTOM E knee_angle>90, mas
    detect_phase() define BOTTOM exatamente como knee_angle<90 — as duas
    condições são mutuamente exclusivas, então o alerta nunca disparava
    em produção. Aqui o mesmo threshold (90°) é avaliado contra a faixa
    "próximo do fundo" (knee_angle entre 90 e 125°) em vez do gate de fase.
    """
    errors = _analyze_squat(lm, angles, phase, frontal_weight=frontal_weight)
    knee_angle = angles.left_knee or angles.right_knee
    if knee_angle is not None and 90.0 < knee_angle < 125.0:
        errors.append(DetectedError(
            error_type=ErrorType.DEPTH_INSUFFICIENT, risk_level=RiskLevel.LOW,
            description=f"Profundidade insuficiente: joelho a {knee_angle:.0f}° (mín 90°)",
            joint_angle=knee_angle, threshold_violated=90.0,
        ))
    return errors


def _errors_to_row(errors, columns) -> dict:
    row = {c: "NONE" for c in columns}
    for err in errors:
        name = err.error_type.value
        if name in row:
            row[name] = err.risk_level.value
    return row


# ── Amostragem de frames por exercício (cobre todo o espectro bom→ruim) ─────

def _sample_squat() -> dict:
    band = random.choices(
        ["STANDING", "BOTTOM", "MID"], weights=[0.30, 0.35, 0.35]
    )[0]
    knee_angle = {
        "STANDING": random.uniform(163, 180),
        "BOTTOM": random.uniform(55, 89),
        "MID": random.uniform(92, 158),
    }[band]
    # back_angle correlacionado com a fase: de pé com pernas retas e tronco
    # muito inclinado (>20°) não é uma postura real de squat — essa
    # combinação biomecanicamente inválida só confundia o classificador
    # com deadlift/bent-over-row (que de fato ficam parados nessa posição).
    # Na descida/fundo, mantém a faixa cheia (é onde a inclinação real varia).
    if band == "STANDING":
        back_angle = random.uniform(0, 20) if random.random() < 0.85 else random.uniform(20, 75)
    else:
        back_angle = random.uniform(0, 75)
    return dict(
        orientation_bucket=random.choice(ORIENTATION_BUCKETS),
        knee_angle=knee_angle,
        back_angle=back_angle,
        knee_cave_pct_left=random.uniform(-3, 14) if random.random() < 0.5 else random.uniform(-2, 3),
        knee_cave_pct_right=random.uniform(-3, 14) if random.random() < 0.5 else random.uniform(-2, 3),
    knee_over_toe_left=random.uniform(-0.04, 0.10),
        # KNEE_OVER_TOE_RIGHT na regra usa "r_foot.x - r_knee.x" (convenção
        # invertida em relação ao lado esquerdo) — negativa aqui para que o
        # parâmetro amostrado tenha o mesmo sentido de violação dos dois lados.
        knee_over_toe_right=-random.uniform(-0.04, 0.10),
        # Braços não são relevantes para squat, mas variá-los evita que o
        # classificador associe "braço parado a 90°" (default geométrico)
        # como assinatura espúria de squat/deadlift.
        arm_angle_left=random.uniform(60, 170),
        arm_angle_right=random.uniform(60, 170),
        elbow_flare_pct=random.uniform(-10, 15),
    )


def _sample_deadlift() -> dict:
    # Diferente do squat, o deadlift convencional não desce a um ângulo de
    # joelho tão fechado quanto um agachamento — a faixa de trabalho real
    # fica em ~95-145°. Manter essa faixa separada da faixa "BOTTOM" do
    # squat (55-89°) é o que dá ao classificador um sinal claro para não
    # confundir os dois exercícios numa única faixa de joelho ambígua.
    band = random.choices(
        ["STANDING", "WORKING"], weights=[0.40, 0.60]
    )[0]
    knee_angle = {
        "STANDING": random.uniform(163, 180),
        "WORKING": random.uniform(95, 145),
    }[band]
    # Mesmo raciocínio do squat: lockout (STANDING) com tronco muito
    # inclinado é uma postura rara/inválida que só confundia o classificador
    # com bent-over-row. Mantém uma fração pequena para ainda treinar
    # "lockout malfeito" (lombar arredondada mesmo perto do topo).
    if band == "STANDING":
        back_angle = random.uniform(0, 15) if random.random() < 0.80 else random.uniform(15, 70)
    else:
        back_angle = random.uniform(0, 70)
    return dict(
        orientation_bucket=random.choices(ORIENTATION_BUCKETS, weights=[0.45, 0.35, 0.20])[0],
        knee_angle=knee_angle,
        back_angle=back_angle,
        knee_cave_pct_left=random.uniform(-1, 1),
        knee_cave_pct_right=random.uniform(-1, 1),
        knee_over_toe_left=random.uniform(-0.01, 0.01),
        knee_over_toe_right=random.uniform(-0.01, 0.01),
        # No deadlift convencional o cotovelo fica quase totalmente
        # estendido (segurando a barra) — diferente do bent-over-row, que
        # ativamente flexiona o cotovelo na puxada (50-170°). Manter essa
        # faixa estreita reduz a sobreposição entre os dois exercícios.
        arm_angle_left=random.uniform(150, 180),
        arm_angle_right=random.uniform(150, 180),
        elbow_flare_pct=random.uniform(-10, 15),
    )


def _sample_bench() -> dict:
    band = random.choices(["BOTTOM", "MID"], weights=[0.45, 0.55])[0]
    knee_angle = random.uniform(70, 89) if band == "BOTTOM" else random.uniform(91, 158)
    return dict(
        orientation_bucket=random.choices(ORIENTATION_BUCKETS, weights=[0.45, 0.35, 0.20])[0],
        knee_angle=knee_angle,
        # No supino a pessoa está deitada (tronco horizontal) — em vez de
        # modelar uma cinemática 3D distinta para essa postura, usamos o
        # próprio significado da fórmula de back_angle (inclinação do
        # tronco em relação à vertical): deitado ≈ inclinação máxima.
        # Isso também evita ambiguidade com squat/deadlift (que ficam
        # tipicamente <75°) no dataset de classificação.
        back_angle=random.uniform(72, 85),
        elbow_flare_pct=random.uniform(-10, 45),
        elbow_flare_angle_lateral=random.uniform(0, 85),
        arm_angle_left=random.uniform(40, 175),
        arm_angle_right=random.uniform(40, 175),
        wrist_extra_dev_left=random.uniform(-0.02, 0.10),
        wrist_extra_dev_right=random.uniform(-0.02, 0.10),
    )


def _sample_lunge() -> dict:
    front_bent = random.uniform(75, 110)
    back_straight = random.uniform(140, 178)
    if random.random() < 0.5:
        kl, kr = front_bent, back_straight
    else:
        kl, kr = back_straight, front_bent
    return dict(
        orientation_bucket=random.choice(ORIENTATION_BUCKETS),
        knee_angle=front_bent,
        knee_angle_left=kl,
        knee_angle_right=kr,
        back_angle=random.uniform(0, 40),
        stance_offset_right=random.uniform(0.15, 0.32) * random.choice([-1, 1]),
    )


def _sample_bent_over_row() -> dict:
    return dict(
        orientation_bucket=random.choices(ORIENTATION_BUCKETS, weights=[0.45, 0.35, 0.20])[0],
        knee_angle=random.uniform(150, 178),
        back_angle=random.uniform(35, 85),
        arm_angle_left=random.uniform(50, 170),
        arm_angle_right=random.uniform(50, 170),
    )


_SAMPLERS = {
    ExerciseType.SQUAT: _sample_squat,
    ExerciseType.DEADLIFT: _sample_deadlift,
    ExerciseType.BENCH_PRESS: _sample_bench,
    ExerciseType.LUNGE: _sample_lunge,
    ExerciseType.BENT_OVER_ROW: _sample_bent_over_row,
}


def generate_classification_dataset(n_per_class: int = 4000, seed: int = 42) -> str:
    """Gera dataset para o classificador de tipo de exercício (5 classes)."""
    random.seed(seed)
    path = os.path.join(DATA_DIR, "exercise_classification.csv")
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FEATURE_NAMES + ["exercise_type"])
        for ex_type, sampler in _SAMPLERS.items():
            for _ in range(n_per_class):
                params = sampler()
                landmarks = build_frame(**params, noise_sigma=random.uniform(0.005, 0.02))
                orientation = detect_orientation(landmarks)
                vector, _, _, _, _ = extract_features(landmarks, orientation)
                writer.writerow(vector + [ex_type.value])
    return path


def generate_form_dataset(exercise_type: ExerciseType, n: int = 9000, seed: int = 43) -> str:
    """Gera dataset de erros/score para um exercício com modelo de forma."""
    random.seed(seed + hash(exercise_type.value) % 1000)
    sampler = _SAMPLERS[exercise_type]
    columns = FORM_ERROR_COLUMNS[exercise_type]
    path = os.path.join(DATA_DIR, f"form_{exercise_type.value.lower()}.csv")

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FORM_FEATURE_NAMES + columns + ["score"])
        for _ in range(n):
            params = sampler()
            landmarks = build_frame(**params, noise_sigma=random.uniform(0.005, 0.02))
            lm_map = {lm.landmark_type: lm for lm in landmarks}
            orientation = detect_orientation(landmarks)
            angles = calculate_joint_angles(landmarks, orientation)
            knee_angle = angles.left_knee or angles.right_knee
            phase = detect_phase(knee_angle)
            fw = orientation.frontal_weight

            if exercise_type == ExerciseType.SQUAT:
                errors = _analyze_squat_teacher(lm_map, angles, phase, frontal_weight=fw)
            elif exercise_type == ExerciseType.DEADLIFT:
                errors = _analyze_deadlift_teacher(lm_map, angles, phase, frontal_weight=fw)
            elif exercise_type == ExerciseType.BENCH_PRESS:
                errors = _analyze_bench_press(lm_map, angles, phase, frontal_weight=fw)
            else:
                raise ValueError(f"Sem modelo de forma para {exercise_type}")

            score = calculate_score(errors, phase)
            vector, _, _, _, _ = extract_features(landmarks, orientation)
            vector = vector + [phase_to_code(phase.value)]
            err_row = _errors_to_row(errors, columns)
            writer.writerow(vector + [err_row[c] for c in columns] + [score])

    return path


if __name__ == "__main__":
    print("Gerando dataset de classificação de exercício...")
    p = generate_classification_dataset()
    print(f"  -> {p}")

    for ex in (ExerciseType.SQUAT, ExerciseType.DEADLIFT, ExerciseType.BENCH_PRESS):
        print(f"Gerando dataset de forma para {ex.value}...")
        p = generate_form_dataset(ex)
        print(f"  -> {p}")
