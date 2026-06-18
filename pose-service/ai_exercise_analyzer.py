"""
ai_exercise_analyzer.py — GymVision Exercise Analyzer (IA)
===============================================================
Substitui o motor de regras hardcoded de exercise_analyzer.py por modelos
de Machine Learning (RandomForest) treinados em ai/train_form_analyzer.py
sobre dataset sintético — um classificador multi-rótulo de erros
(NONE/LOW/MEDIUM/HIGH por tipo de erro) + um regressor de score (0-100).

Cobertura atual: SQUAT, DEADLIFT, BENCH_PRESS (os 3 exercícios mais
críticos, conforme priorizado). LUNGE e BENT_OVER_ROW ainda não têm
dataset/modelo treinado — usam o motor de regras legado de
exercise_analyzer.py como fallback explícito até que sejam priorizados
(ver ai/dataset_generator.py para estender a cobertura).

API idêntica à do ExerciseAnalyzer antigo (analyze() devolve AnalysisResult)
para ser um drop-in replacement em main.py.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import joblib
import numpy as np

from models import (
    LandmarkInput, JointAngles,
    DetectedError, ErrorType, ExerciseType, MovementPhase, RiskLevel,
)
from angle_calculator import (
    LEFT_HIP, RIGHT_HIP, LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
)
from ai.features import extract_features, phase_to_code
from exercise_analyzer import (
    detect_phase, calculate_score, _analyze_lunge, _analyze_bent_over_row,
)

logger = logging.getLogger(__name__)

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "ai", "models_ai")
_TRAINED_EXERCISES = {ExerciseType.SQUAT, ExerciseType.DEADLIFT, ExerciseType.BENCH_PRESS}
_form_models: dict[ExerciseType, dict] = {}


def _load_form_model(exercise_type: ExerciseType) -> Optional[dict]:
    if exercise_type in _form_models:
        return _form_models[exercise_type]
    path = os.path.join(_MODELS_DIR, f"form_{exercise_type.value.lower()}.joblib")
    if not os.path.exists(path):
        return None
    model = joblib.load(path)
    _form_models[exercise_type] = model
    logger.info("Modelo de forma carregado: %s", path)
    return model


def _fmt(v) -> str:
    return f"{v:.1f}" if v == v else "?"  # v==v é False para NaN


_DESCRIPTION_BUILDERS = {
    ErrorType.DEPTH_INSUFFICIENT: lambda f: f"Profundidade insuficiente: joelho a {_fmt(f['knee_angle_avg'])}° (mín 90°)",
    ErrorType.KNEE_CAVE_LEFT: lambda f: f"Joelho esquerdo colapsando para dentro ({_fmt(f['knee_cave_pct_left'])}% de desvio)",
    ErrorType.KNEE_CAVE_RIGHT: lambda f: f"Joelho direito colapsando para dentro ({_fmt(f['knee_cave_pct_right'])}% de desvio)",
    ErrorType.KNEE_OVER_TOE_LEFT: lambda f: f"Joelho esquerdo ultrapassando o pé ({_fmt(f['knee_over_toe_left'])} normalizado)",
    ErrorType.KNEE_OVER_TOE_RIGHT: lambda f: f"Joelho direito ultrapassando o pé ({_fmt(f['knee_over_toe_right'])} normalizado)",
    ErrorType.BACK_NOT_STRAIGHT: lambda f: f"Tronco muito inclinado: {_fmt(f['back_angle'])}°",
    ErrorType.BACK_ROUNDED: lambda f: f"Lombar arredondada: tronco a {_fmt(f['back_angle'])}° — risco de lesão",
    ErrorType.HIPS_TOO_HIGH: lambda f: f"Quadril não totalmente estendido no topo: {_fmt(f['hip_angle_left'] or f['hip_angle_right'])}°",
    ErrorType.ELBOW_FLARE: lambda f: f"Cotovelos muito abertos ({_fmt(f['elbow_flare_pct'])}% além dos ombros) — risco para ombro",
    ErrorType.ELBOW_INSUFFICIENT_RANGE: lambda f: f"Amplitude insuficiente: cotovelo a {_fmt(f['arm_angle_left'])}° (desça mais a barra)",
    ErrorType.WRIST_BENT: lambda f: f"Pulso dobrado lateralmente ({_fmt(f['wrist_dev_left'])}) — mantenha pulso neutro",
}


@dataclass
class AnalysisResult:
    """Resultado interno da análise — não exposto diretamente como schema HTTP."""
    session_id: str
    student_id: str
    exercise_type: ExerciseType
    frame_seq: int
    phase: MovementPhase
    score: float
    joint_angles: JointAngles
    errors: list = field(default_factory=list)
    has_alert: bool = False
    landmark_count: int = 0
    analysis_ms: float = 0.0
    camera_orientation: str = "UNKNOWN"


class ExerciseAnalyzer:
    """
    Orquestra a análise completa de um frame via modelos de IA (com
    fallback ao motor de regras legado para exercícios ainda não
    cobertos pelo treino). Mesma interface pública do ExerciseAnalyzer
    original — drop-in replacement.
    """

    def __init__(self, custom_thresholds: Optional[dict] = None):
        # Mantido por compatibilidade com o endpoint PUT /rules/* do main.py
        # — só tem efeito sobre o fallback de regras (LUNGE/BENT_OVER_ROW).
        self.thresholds = custom_thresholds or {}

    def analyze(self, request, orientation=None) -> AnalysisResult:
        t0 = time.perf_counter()

        lm_list = request.landmarks
        lm_map: dict[int, LandmarkInput] = {lm.landmark_type: lm for lm in lm_list}

        if orientation is None and lm_list:
            try:
                from orientation_detector import detect_orientation
                orientation = detect_orientation(lm_list)
            except ImportError:
                orientation = None

        frontal_weight: float = (
            getattr(orientation, "frontal_weight", 0.0) if orientation else 0.0
        )
        cam_orientation: str = (
            getattr(getattr(orientation, "orientation", None), "value", "UNKNOWN")
            if orientation else "UNKNOWN"
        )

        key_joints_left = [k for k in [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE] if k in lm_map]
        key_joints_right = [k for k in [RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE] if k in lm_map]
        total_key = len(key_joints_left) + len(key_joints_right)

        if total_key < 2:
            elapsed = (time.perf_counter() - t0) * 1000
            return AnalysisResult(
                session_id=request.session_id, student_id=request.student_id,
                exercise_type=request.exercise_type, frame_seq=request.frame_seq,
                phase=MovementPhase.UNKNOWN, score=0.0, joint_angles=JointAngles(),
                errors=[DetectedError(
                    error_type=ErrorType.LANDMARK_MISSING, risk_level=RiskLevel.LOW,
                    description=(
                        f"Landmarks insuficientes ({len(lm_list)} detectados, "
                        f"{total_key} joints-chave). Use foto lateral com corpo inteiro visível."
                    ),
                )],
                has_alert=False, landmark_count=len(lm_list),
                analysis_ms=round(elapsed, 2), camera_orientation=cam_orientation,
            )

        vector, feats, angles, fw, _ = extract_features(lm_list, orientation)
        knee_angle = angles.left_knee or angles.right_knee
        phase = detect_phase(knee_angle)

        ex_type = request.exercise_type
        if ex_type in _TRAINED_EXERCISES:
            errors, score = self._predict_ml(ex_type, vector, feats, phase)
        else:
            errors, score = self._predict_rule_fallback(ex_type, lm_map, angles, phase, frontal_weight)

        has_alert = any(e.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH) for e in errors)
        elapsed = (time.perf_counter() - t0) * 1000

        logger.debug(
            "Análise IA [%s] | câmera: %s (fw=%.2f) | fase: %s | score: %s | erros: %d",
            ex_type.value, cam_orientation, fw, phase.value, score, len(errors),
        )

        return AnalysisResult(
            session_id=request.session_id, student_id=request.student_id,
            exercise_type=ex_type, frame_seq=request.frame_seq,
            phase=phase, score=score, joint_angles=angles, errors=errors,
            has_alert=has_alert, landmark_count=len(lm_list),
            analysis_ms=round(elapsed, 2), camera_orientation=cam_orientation,
        )

    def _predict_ml(self, ex_type: ExerciseType, vector: list, feats: dict, phase: MovementPhase):
        model = _load_form_model(ex_type)
        if model is None:
            logger.warning("Modelo de forma não encontrado para %s — score zerado.", ex_type.value)
            return [], 0.0

        X = np.array([vector + [phase_to_code(phase.value)]], dtype=float)
        X_imp = model["imputer"].transform(X)

        pred_labels = model["error_classifier"].predict(X_imp)[0]
        raw_score = float(model["score_regressor"].predict(X_imp)[0])
        score = 0.0 if phase == MovementPhase.UNKNOWN else max(0.0, min(100.0, round(raw_score, 1)))

        errors: list[DetectedError] = []
        for col, label in zip(model["error_columns"], pred_labels):
            if label == "NONE":
                continue
            error_type = ErrorType(col)
            risk = RiskLevel(label)
            builder = _DESCRIPTION_BUILDERS.get(error_type)
            description = builder(feats) if builder else f"{col} detectado pelo modelo de IA"
            errors.append(DetectedError(error_type=error_type, risk_level=risk, description=description))

        return errors, score

    def _predict_rule_fallback(self, ex_type, lm_map, angles, phase, frontal_weight):
        """LUNGE / BENT_OVER_ROW — ainda sem dataset/modelo treinado."""
        th = self.thresholds.get(ex_type.value, {})
        if ex_type == ExerciseType.LUNGE:
            errors = _analyze_lunge(lm_map, angles, phase, th, frontal_weight)
        elif ex_type == ExerciseType.BENT_OVER_ROW:
            errors = _analyze_bent_over_row(lm_map, angles, phase, th, frontal_weight)
        else:
            errors = []
        return errors, calculate_score(errors, phase)


# Singleton compartilhado
analyzer = ExerciseAnalyzer()
