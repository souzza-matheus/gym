"""
exercise_analyzer.py — GymVision Exercise Analyzer Service
===========================================================
Porta da lógica central do ExerciseAnalyzer.kt do app Android para Python.

Versão 2 — suporte a múltiplos ângulos de câmera
-------------------------------------------------
As principais mudanças em relação à versão original:

  1. analyze() aceita opcional orientation: OrientationResult.
     Se não informado, detecta automaticamente a partir dos landmarks.

  2. Regras que dependem de perspectiva são ajustadas por orientação:
     - Knee cave: só confiável na câmera FRONTAL (desvio medial é visível).
       Na câmera LATERAL, o deslocamento X do joelho em relação ao tornozelo
       não representa varo/valgo, mas sim profundidade — a regra é desabilitada.
     - Knee over toe: só confiável na câmera LATERAL (profundidade sagital).
       Na câmera FRONTAL, o eixo X não codifica "frente/trás" — desabilitado.
     - Back angle e profundidade: funcionam em todos os ângulos (usa os valores
       já corrigidos pelo angle_calculator por orientação).

  3. O endpoint POST /api/v1/pose/analyze e todos os schemas permanecem inalterados.
  4. Os 30 testes de run_all_tests.py continuam passando (retrocompatibilidade).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from models import (
    LandmarkInput, JointAngles,
    DetectedError, ErrorType, ExerciseType, MovementPhase, RiskLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Resultado interno da análise — não exposto diretamente como schema HTTP."""
    session_id:    str
    student_id:    str
    exercise_type: ExerciseType
    frame_seq:     int
    phase:         MovementPhase
    score:         float
    joint_angles:  JointAngles
    errors:        list = field(default_factory=list)
    has_alert:     bool = False
    landmark_count: int = 0
    analysis_ms:   float = 0.0
    # Orientação detectada (informativo — não quebra contrato da API)
    camera_orientation: str = "UNKNOWN"


from angle_calculator import (
    calculate_joint_angles,
    _get,
    LEFT_HIP,  RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_HEEL, RIGHT_HEEL,
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX,
)


# ── Thresholds (defaults do app Android) ─────────────────────────────────────
# Squat
SQUAT_DEPTH_ANGLE_MIN: float    = 90.0
SQUAT_KNEE_CAVE_THRESHOLD: float = 15.0
SQUAT_BACK_ANGLE_MAX: float     = 45.0
SQUAT_KNEE_OVER_TOE_MAX: float  = 0.05

# Deadlift
DEADLIFT_BACK_ANGLE_MAX: float    = 30.0
DEADLIFT_HIP_ANGLE_STANDING: float = 160.0

# Lunge
LUNGE_KNEE_ANGLE_FRONT_MIN: float = 85.0
LUNGE_KNEE_ANGLE_FRONT_MAX: float = 100.0
LUNGE_BACK_ANGLE_MAX: float       = 40.0

# Thresholds de orientação para desabilitar regras perspectiva-dependentes
# (frontal_weight abaixo deste valor → câmera lateral → disable knee cave)
_FRONTAL_WEIGHT_FOR_KNEE_CAVE      = 0.40   # mínimo fw para confiar no knee cave
# (frontal_weight acima deste → câmera frontal → disable knee over toe)
_LATERAL_WEIGHT_FOR_KNEE_OVER_TOE  = 0.60   # máximo fw para confiar no knee over toe


# ── Detecção de fase ──────────────────────────────────────────────────────────

def detect_phase(
    knee_angle: Optional[float],
    prev_angle: Optional[float] = None,
) -> MovementPhase:
    """
    Determina a fase do movimento a partir do ângulo do joelho.
    Porta de ExerciseAnalyzer.detectPhase(). Inalterado.
    """
    if knee_angle is None:
        return MovementPhase.UNKNOWN

    if knee_angle > 160.0:
        return MovementPhase.STANDING
    elif knee_angle < 90.0:
        return MovementPhase.BOTTOM
    else:
        if prev_angle is None:
            return MovementPhase.DESCENDING
        return MovementPhase.ASCENDING if knee_angle > prev_angle else MovementPhase.DESCENDING


# ── Análise de Squat ──────────────────────────────────────────────────────────

def _analyze_squat(
    lm: dict,
    angles: JointAngles,
    phase: MovementPhase,
    thresholds: Optional[dict] = None,
    frontal_weight: float = 0.0,
) -> list[DetectedError]:
    """
    Porta de ExerciseAnalyzer.analyzeSquat().
    Verifica: profundidade, knee cave, joelho além do pé, inclinação do tronco.

    Ajustes por orientação:
      - Knee cave:    só ativo se fw ≥ _FRONTAL_WEIGHT_FOR_KNEE_CAVE (câmera frontal/angled)
      - Knee over toe: só ativo se fw ≤ _LATERAL_WEIGHT_FOR_KNEE_OVER_TOE (câmera lateral/angled)
      - Profundidade e back_angle: ativos em qualquer orientação
    """
    errors: list[DetectedError] = []
    th = thresholds or {}

    depth_angle_min  = th.get("squat_depth_angle_min",    SQUAT_DEPTH_ANGLE_MIN)
    knee_cave_th     = th.get("squat_knee_cave_threshold", SQUAT_KNEE_CAVE_THRESHOLD)
    back_angle_max   = th.get("squat_back_angle_max",      SQUAT_BACK_ANGLE_MAX)
    knee_over_toe_max = th.get("squat_knee_over_toe_max",  SQUAT_KNEE_OVER_TOE_MAX)

    # ── 1. Profundidade insuficiente (verifica só no BOTTOM) ──────────────
    if phase == MovementPhase.BOTTOM:
        knee_angle = angles.left_knee or angles.right_knee
        if knee_angle and knee_angle > depth_angle_min:
            errors.append(DetectedError(
                error_type=ErrorType.DEPTH_INSUFFICIENT,
                risk_level=RiskLevel.LOW,
                description=(
                    f"Profundidade insuficiente: joelho a {knee_angle:.0f}° "
                    f"(mín {depth_angle_min:.0f}°)"
                ),
                joint_angle=knee_angle,
                threshold_violated=depth_angle_min,
            ))

    # ── 2. Knee cave ───────────────────────────────────────────────────────
    # Confiável apenas com câmera frontal ou em ângulo (desvio medial visível).
    # Na câmera lateral, o eixo X representa profundidade sagital, não largura.
    if frontal_weight >= _FRONTAL_WEIGHT_FOR_KNEE_CAVE:
        l_knee  = lm.get(LEFT_KNEE)
        l_ankle = lm.get(LEFT_ANKLE)
        r_knee  = lm.get(RIGHT_KNEE)
        r_ankle = lm.get(RIGHT_ANKLE)

        if l_knee and l_ankle:
            knee_ankle_diff_pct = (l_knee.x - l_ankle.x) * 100
            if knee_ankle_diff_pct > knee_cave_th:
                errors.append(DetectedError(
                    error_type=ErrorType.KNEE_CAVE_LEFT,
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Joelho esquerdo colapsando para dentro "
                        f"({knee_ankle_diff_pct:.1f}% de desvio)"
                    ),
                    threshold_violated=knee_cave_th,
                ))

        if r_knee and r_ankle:
            knee_ankle_diff_pct = (r_ankle.x - r_knee.x) * 100
            if knee_ankle_diff_pct > knee_cave_th:
                errors.append(DetectedError(
                    error_type=ErrorType.KNEE_CAVE_RIGHT,
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Joelho direito colapsando para dentro "
                        f"({knee_ankle_diff_pct:.1f}% de desvio)"
                    ),
                    threshold_violated=knee_cave_th,
                ))
    # Câmera lateral: eixo X representa profundidade sagital, não largura frontal.
    # Knee cave (valgus) não é detectável nesta orientação — regra desabilitada.

    # ── 3. Joelho muito à frente do pé ────────────────────────────────────
    # Confiável apenas com câmera lateral (profundidade sagital em X).
    # Na câmera frontal, X é largura, não profundidade — regra desabilitada.
    if frontal_weight <= _LATERAL_WEIGHT_FOR_KNEE_OVER_TOE:
        l_knee = lm.get(LEFT_KNEE)
        l_foot = lm.get(LEFT_FOOT_INDEX)
        r_knee = lm.get(RIGHT_KNEE)
        r_foot = lm.get(RIGHT_FOOT_INDEX)

        if l_knee and l_foot:
            overshoot = l_knee.x - l_foot.x
            if overshoot > knee_over_toe_max:
                errors.append(DetectedError(
                    error_type=ErrorType.KNEE_OVER_TOE_LEFT,
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Joelho esquerdo ultrapassando o pé "
                        f"({overshoot:.3f} normalizado)"
                    ),
                    threshold_violated=knee_over_toe_max,
                ))

        if r_knee and r_foot:
            overshoot = r_foot.x - r_knee.x
            if overshoot > knee_over_toe_max:
                errors.append(DetectedError(
                    error_type=ErrorType.KNEE_OVER_TOE_RIGHT,
                    risk_level=RiskLevel.MEDIUM,
                    description=(
                        f"Joelho direito ultrapassando o pé "
                        f"({overshoot:.3f} normalizado)"
                    ),
                    threshold_violated=knee_over_toe_max,
                ))

    # ── 4. Inclinação excessiva do tronco ─────────────────────────────────
    if angles.back_angle is not None and angles.back_angle > back_angle_max:
        risk = (
            RiskLevel.HIGH
            if angles.back_angle > back_angle_max * 1.4
            else RiskLevel.MEDIUM
        )
        errors.append(DetectedError(
            error_type=ErrorType.BACK_NOT_STRAIGHT,
            risk_level=risk,
            description=(
                f"Tronco muito inclinado: {angles.back_angle:.0f}° "
                f"(máx {back_angle_max:.0f}°)"
            ),
            joint_angle=angles.back_angle,
            threshold_violated=back_angle_max,
        ))

    return errors


# ── Análise de Deadlift ───────────────────────────────────────────────────────

def _analyze_deadlift(
    lm: dict,
    angles: JointAngles,
    phase: MovementPhase,
    thresholds: Optional[dict] = None,
    frontal_weight: float = 0.0,
) -> list[DetectedError]:
    """
    Porta de ExerciseAnalyzer.analyzeDeadlift().
    Verifica: lombar arredondada, quadril não estendido.
    Back angle funciona em qualquer orientação (calculado por angle_calculator).
    """
    errors: list[DetectedError] = []
    th = thresholds or {}

    back_angle_max  = th.get("deadlift_back_angle_max",      DEADLIFT_BACK_ANGLE_MAX)
    hip_standing_th = th.get("deadlift_hip_angle_standing",  DEADLIFT_HIP_ANGLE_STANDING)

    # 1. Lombar arredondada
    if phase in (MovementPhase.ASCENDING, MovementPhase.BOTTOM):
        if angles.back_angle is not None and angles.back_angle > back_angle_max:
            risk = RiskLevel.HIGH if angles.back_angle > back_angle_max * 1.5 else RiskLevel.MEDIUM
            errors.append(DetectedError(
                error_type=ErrorType.BACK_ROUNDED,
                risk_level=risk,
                description=(
                    f"Lombar arredondada: tronco a {angles.back_angle:.0f}° "
                    f"(máx {back_angle_max:.0f}°)"
                ),
                joint_angle=angles.back_angle,
                threshold_violated=back_angle_max,
            ))

    # 2. Quadril não estendido no topo
    if phase == MovementPhase.STANDING:
        hip_angle = angles.left_hip or angles.right_hip
        if hip_angle and hip_angle < hip_standing_th:
            errors.append(DetectedError(
                error_type=ErrorType.HIPS_TOO_HIGH,
                risk_level=RiskLevel.LOW,
                description=(
                    f"Quadril não totalmente estendido no topo: {hip_angle:.0f}° "
                    f"(esperado > {hip_standing_th:.0f}°)"
                ),
                joint_angle=hip_angle,
                threshold_violated=hip_standing_th,
            ))

    return errors


# ── Análise de Lunge ──────────────────────────────────────────────────────────

def _analyze_lunge(
    lm: dict,
    angles: JointAngles,
    phase: MovementPhase,
    thresholds: Optional[dict] = None,
    frontal_weight: float = 0.0,
) -> list[DetectedError]:
    """Porta de ExerciseAnalyzer.analyzeLunge()."""
    errors: list[DetectedError] = []
    th = thresholds or {}

    knee_min      = th.get("lunge_knee_angle_front_min", LUNGE_KNEE_ANGLE_FRONT_MIN)
    knee_max      = th.get("lunge_knee_angle_front_max", LUNGE_KNEE_ANGLE_FRONT_MAX)
    back_angle_max = th.get("lunge_back_angle_max",      LUNGE_BACK_ANGLE_MAX)

    if phase == MovementPhase.BOTTOM:
        front_knee_angle = angles.left_knee or angles.right_knee
        if front_knee_angle:
            if front_knee_angle < knee_min or front_knee_angle > knee_max:
                errors.append(DetectedError(
                    error_type=ErrorType.DEPTH_INSUFFICIENT,
                    risk_level=RiskLevel.LOW,
                    description=(
                        f"Ângulo do joelho frontal fora do ideal: {front_knee_angle:.0f}° "
                        f"(esperado {knee_min:.0f}°–{knee_max:.0f}°)"
                    ),
                    joint_angle=front_knee_angle,
                ))

    if angles.back_angle and angles.back_angle > back_angle_max:
        errors.append(DetectedError(
            error_type=ErrorType.BACK_NOT_STRAIGHT,
            risk_level=RiskLevel.MEDIUM,
            description=(
                f"Tronco muito inclinado no lunge: {angles.back_angle:.0f}° "
                f"(máx {back_angle_max:.0f}°)"
            ),
            joint_angle=angles.back_angle,
            threshold_violated=back_angle_max,
        ))

    return errors


# ── Score ─────────────────────────────────────────────────────────────────────

def calculate_score(errors: list[DetectedError], phase: MovementPhase) -> float:
    """
    Porta de ExerciseAnalyzer.calculateScore(). Inalterado.

    Score base 100. Penalidades:
      HIGH error   → -25 pts
      MEDIUM error → -15 pts
      LOW error    → -5 pts
    Score mínimo: 0.
    """
    if phase == MovementPhase.UNKNOWN:
        return 0.0

    score = 100.0
    for err in errors:
        if err.risk_level == RiskLevel.HIGH:
            score -= 25.0
        elif err.risk_level == RiskLevel.MEDIUM:
            score -= 15.0
        else:
            score -= 5.0

    return max(0.0, round(score, 1))


# ── Analisador principal ──────────────────────────────────────────────────────

class ExerciseAnalyzer:
    """
    Orquestra a análise completa de um frame.
    Porta de ExerciseAnalyzer.kt — com suporte a múltiplos ângulos de câmera.
    """

    def __init__(self, custom_thresholds: Optional[dict] = None):
        self.thresholds = custom_thresholds or {}

    def analyze(self, request, orientation=None) -> AnalysisResult:
        """
        Analisa um frame e retorna AnalysisResult completo.
        Chamado pelo endpoint POST /api/v1/pose/analyze.

        Args:
            request:     objeto com session_id, student_id, exercise_type,
                         frame_seq e landmarks (list[LandmarkInput]).
            orientation: OrientationResult opcional. Se None, detecta
                         automaticamente a partir dos landmarks.
        """
        t0 = time.perf_counter()

        lm_list = request.landmarks
        lm_map: dict[int, LandmarkInput] = {lm.landmark_type: lm for lm in lm_list}

        # ── Detecta orientação se não fornecida ────────────────────────────
        if orientation is None and lm_list:
            try:
                from orientation_detector import detect_orientation
                orientation = detect_orientation(lm_list)
            except ImportError:
                orientation = None

        frontal_weight: float = (
            getattr(orientation, 'frontal_weight', 0.0) if orientation else 0.0
        )
        cam_orientation: str = (
            getattr(getattr(orientation, 'orientation', None), 'value', 'UNKNOWN')
            if orientation else 'UNKNOWN'
        )

        # ── Verifica landmarks mínimos ─────────────────────────────────────
        key_joints_left  = [k for k in [LEFT_HIP, LEFT_KNEE, LEFT_ANKLE] if k in lm_map]
        key_joints_right = [k for k in [RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE] if k in lm_map]
        total_key        = len(key_joints_left) + len(key_joints_right)

        if total_key < 2:
            elapsed = (time.perf_counter() - t0) * 1000
            return AnalysisResult(
                session_id=request.session_id,
                student_id=request.student_id,
                exercise_type=request.exercise_type,
                frame_seq=request.frame_seq,
                phase=MovementPhase.UNKNOWN,
                score=0.0,
                joint_angles=JointAngles(),
                errors=[DetectedError(
                    error_type=ErrorType.LANDMARK_MISSING,
                    risk_level=RiskLevel.LOW,
                    description=(
                        f"Landmarks insuficientes ({len(lm_list)} detectados, "
                        f"{total_key} joints-chave). "
                        "Use foto lateral com corpo inteiro visível."
                    ),
                )],
                has_alert=False,
                landmark_count=len(lm_list),
                analysis_ms=round(elapsed, 2),
                camera_orientation=cam_orientation,
            )

        # ── Calcula ângulos (orientação-aware) ─────────────────────────────
        angles = calculate_joint_angles(lm_list, orientation)

        # ── Detecta fase ───────────────────────────────────────────────────
        knee_angle = angles.left_knee or angles.right_knee
        phase      = detect_phase(knee_angle)

        # ── Seleciona analisador por tipo de exercício ─────────────────────
        th = self.thresholds.get(request.exercise_type.value, {})

        if request.exercise_type == ExerciseType.SQUAT:
            errors = _analyze_squat(lm_map, angles, phase, th, frontal_weight)
        elif request.exercise_type == ExerciseType.DEADLIFT:
            errors = _analyze_deadlift(lm_map, angles, phase, th, frontal_weight)
        elif request.exercise_type == ExerciseType.LUNGE:
            errors = _analyze_lunge(lm_map, angles, phase, th, frontal_weight)
        else:
            errors = []

        score = calculate_score(errors, phase)

        has_alert = any(
            e.risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH) for e in errors
        )

        elapsed = (time.perf_counter() - t0) * 1000

        if orientation:
            logger.debug(
                f"Análise [{request.exercise_type.value}] | "
                f"câmera: {cam_orientation} (fw={frontal_weight:.2f}) | "
                f"fase: {phase.value} | score: {score} | erros: {len(errors)}"
            )

        return AnalysisResult(
            session_id=request.session_id,
            student_id=request.student_id,
            exercise_type=request.exercise_type,
            frame_seq=request.frame_seq,
            phase=phase,
            score=score,
            joint_angles=angles,
            errors=errors,
            has_alert=has_alert,
            landmark_count=len(lm_list),
            analysis_ms=round(elapsed, 2),
            camera_orientation=cam_orientation,
        )


# Singleton compartilhado (thresholds podem ser recarregados do DB)
analyzer = ExerciseAnalyzer()
