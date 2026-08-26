"""
tests/test_exercise_analyzer_extended.py
Testes gerados para cobrir gaps identificados em relação a
tests/test_exercise_analyzer.py: LUNGE (sem testes dedicados), condições de
contorno de threshold, câmera lateral vs frontal, visibilidade baixa de
landmarks e extremos de score.

Todos os cenários foram verificados contra o comportamento REAL de
exercise_analyzer.py (não contra o comportamento assumido em documentação
externa) — ver pose-service/RELATORIO_CALCULOS_BIOMEDICOS.md para as
divergências encontradas entre a especificação original e o código.
"""
import pytest
from types import SimpleNamespace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import (
    ExerciseType, MovementPhase, RiskLevel, ErrorType, LandmarkInput, JointAngles,
)
from exercise_analyzer import (
    ExerciseAnalyzer, _analyze_squat, _analyze_deadlift, _analyze_lunge,
    calculate_score,
)
from angle_calculator import (
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_FOOT_INDEX, RIGHT_FOOT_INDEX,
)


def make_landmark(ltype: int, x: float, y: float, z: float = 0.0, visibility: float = 0.9) -> LandmarkInput:
    """Helper para criar landmark sintético (mesmo padrão de test_exercise_analyzer.py::lm)."""
    return LandmarkInput(landmark_type=ltype, x=x, y=y, z=z, visibility=visibility)


def lm_map(*landmarks) -> dict:
    return {l.landmark_type: l for l in landmarks}


# ── P1: LUNGE — sem testes dedicados no arquivo original ─────────────────────
# (test_exercise_analyzer.py só referencia _analyze_lunge incidentalmente em
#  TestErrorDescriptionsHaveNoEmbeddedMetrics::test_lunge_descriptions_clean)

class TestLungeAnalysis:
    def test_lunge_correct_form(self):
        """Joelho frontal dentro de [85°,100°] e tronco <=40° -> sem erros."""
        angles = JointAngles(left_knee=92.0, back_angle=20.0)
        errors = _analyze_lunge({}, angles, MovementPhase.BOTTOM)
        assert errors == []

    def test_lunge_depth_out_of_range_low(self):
        """Ângulo do joelho frontal abaixo de LUNGE_KNEE_ANGLE_FRONT_MIN (85°)
        -> DEPTH_INSUFFICIENT com risco LOW (não há KNEE_CAVE nem
        FRONT_KNEE_FORWARD implementados para LUNGE no código atual)."""
        angles = JointAngles(left_knee=60.0, back_angle=20.0)
        errors = _analyze_lunge({}, angles, MovementPhase.BOTTOM)
        assert any(
            e.error_type == ErrorType.DEPTH_INSUFFICIENT and e.risk_level == RiskLevel.LOW
            for e in errors
        )

    def test_lunge_back_not_straight_medium(self):
        """Tronco > LUNGE_BACK_ANGLE_MAX (40°) -> BACK_NOT_STRAIGHT MEDIUM.
        Nota: _analyze_lunge não escala para HIGH (diferente de squat/deadlift/row);
        risk_level é sempre MEDIUM para este erro em LUNGE."""
        angles = JointAngles(left_knee=92.0, back_angle=50.0)
        errors = _analyze_lunge({}, angles, MovementPhase.BOTTOM)
        back_errs = [e for e in errors if e.error_type == ErrorType.BACK_NOT_STRAIGHT]
        assert back_errs and back_errs[0].risk_level == RiskLevel.MEDIUM


# ── P2: condições de contorno (boundary conditions) ──────────────────────────

class TestBoundaryConditions:
    def test_squat_knee_cave_just_below_threshold_no_error(self):
        """Desvio (x_joelho - x_tornozelo)*100 abaixo de 2.0 não deve disparar
        KNEE_CAVE_LEFT (operador é '>', estrito)."""
        lms = lm_map(
            make_landmark(LEFT_KNEE, 0.519, 0.7),
            make_landmark(LEFT_ANKLE, 0.50, 0.9),
        )
        errors = _analyze_squat(lms, JointAngles(), MovementPhase.BOTTOM, frontal_weight=0.8)
        assert not any(e.error_type == ErrorType.KNEE_CAVE_LEFT for e in errors)

    def test_squat_knee_cave_just_above_threshold_triggers(self):
        """Ponto imediatamente acima do threshold de 2.0 (SQUAT_KNEE_CAVE_THRESHOLD)
        já dispara o erro -- confirma que o operador de comparação é '>' e não '>='."""
        lms = lm_map(
            make_landmark(LEFT_KNEE, 0.521, 0.7),
            make_landmark(LEFT_ANKLE, 0.50, 0.9),
        )
        errors = _analyze_squat(lms, JointAngles(), MovementPhase.BOTTOM, frontal_weight=0.8)
        assert any(e.error_type == ErrorType.KNEE_CAVE_LEFT for e in errors)

    def test_squat_back_angle_boundary_medium_high(self):
        """back_angle=63.0 (nominalmente igual a SQUAT_BACK_ANGLE_MAX*1.4=45*1.4)
        já classifica como HIGH, não MEDIUM -- por imprecisão de ponto flutuante,
        45.0*1.4 == 62.99999999999999 em Python, então 63.0 > 62.99999999999999.
        Um praticante no threshold "nominal" de 63° já cai no lado HIGH."""
        errors = _analyze_squat({}, JointAngles(back_angle=63.0), MovementPhase.BOTTOM)
        back_errs = [e for e in errors if e.error_type == ErrorType.BACK_NOT_STRAIGHT]
        assert back_errs and back_errs[0].risk_level == RiskLevel.HIGH

    def test_squat_back_angle_just_below_high_threshold_is_medium(self):
        errors = _analyze_squat({}, JointAngles(back_angle=62.9), MovementPhase.BOTTOM)
        back_errs = [e for e in errors if e.error_type == ErrorType.BACK_NOT_STRAIGHT]
        assert back_errs and back_errs[0].risk_level == RiskLevel.MEDIUM

    def test_deadlift_back_curved_exactly_30_degrees_no_error(self):
        """back_angle exatamente igual a DEADLIFT_BACK_ANGLE_MAX (30°) não
        dispara erro -- comparação é estritamente '>'."""
        errors = _analyze_deadlift({}, JointAngles(back_angle=30.0), MovementPhase.BOTTOM)
        assert errors == []

    def test_deadlift_back_curved_just_above_30_degrees_triggers(self):
        errors = _analyze_deadlift({}, JointAngles(back_angle=30.01), MovementPhase.BOTTOM)
        assert any(e.error_type == ErrorType.BACK_ROUNDED for e in errors)


# ── P3: câmera lateral vs frontal (frontal_weight) ────────────────────────────

class TestCameraOrientationRules:
    def test_squat_lateral_camera_disables_knee_cave_rule(self):
        """Com frontal_weight abaixo de _FRONTAL_WEIGHT_FOR_KNEE_CAVE (0.40),
        mesmo um joelho claramente desviado não deve reportar KNEE_CAVE."""
        lms = lm_map(
            make_landmark(LEFT_KNEE, 0.60, 0.7),   # desvio bem acima do threshold
            make_landmark(LEFT_ANKLE, 0.50, 0.9),
        )
        errors = _analyze_squat(lms, JointAngles(), MovementPhase.BOTTOM, frontal_weight=0.2)
        assert not any(
            e.error_type in (ErrorType.KNEE_CAVE_LEFT, ErrorType.KNEE_CAVE_RIGHT)
            for e in errors
        )

    def test_squat_lateral_camera_enables_back_rule(self):
        """back_angle (BACK_NOT_STRAIGHT) não depende de frontal_weight --
        deve disparar mesmo com câmera lateral pura (frontal_weight baixo)."""
        errors = _analyze_squat({}, JointAngles(back_angle=70.0), MovementPhase.BOTTOM, frontal_weight=0.1)
        assert any(e.error_type == ErrorType.BACK_NOT_STRAIGHT for e in errors)


# ── P4: landmarks com visibilidade insuficiente ───────────────────────────────

class TestLowVisibilityLandmarks:
    def test_analyzer_handles_low_visibility_without_exception(self):
        """Todos os landmarks com visibility=0.1 (abaixo de MIN_VISIBILITY=0.2
        em angle_calculator.py) -- o sistema não deve lançar exceção. Os
        ângulos ficam None (filtrados por _get), a fase cai em UNKNOWN e o
        score é 0.0. Nota: a suposição original de visibility=0.3 no prompt
        de origem não filtraria nada, pois 0.3 > MIN_VISIBILITY (0.2); este
        teste usa 0.1, que de fato está abaixo do threshold real do código."""
        lms = [
            make_landmark(LEFT_SHOULDER, 0.5, 0.1, visibility=0.1),
            make_landmark(RIGHT_SHOULDER, 0.6, 0.1, visibility=0.1),
            make_landmark(LEFT_HIP, 0.5, 0.4, visibility=0.1),
            make_landmark(RIGHT_HIP, 0.6, 0.4, visibility=0.1),
            make_landmark(LEFT_KNEE, 0.5, 0.7, visibility=0.1),
            make_landmark(RIGHT_KNEE, 0.6, 0.7, visibility=0.1),
            make_landmark(LEFT_ANKLE, 0.5, 0.9, visibility=0.1),
            make_landmark(RIGHT_ANKLE, 0.6, 0.9, visibility=0.1),
        ]
        req = SimpleNamespace(
            session_id="low-vis-session", student_id="s", frame_seq=1,
            exercise_type=ExerciseType.SQUAT, landmarks=lms,
        )
        analyzer = ExerciseAnalyzer()
        result = analyzer.analyze(req)  # não deve lançar
        assert result.phase == MovementPhase.UNKNOWN
        assert result.score == 0.0
        assert result.errors == []


# ── P5: score em casos extremos ───────────────────────────────────────────────

class TestScoreExtremes:
    def test_max_simultaneous_squat_errors_do_not_reach_zero(self):
        """Descoberta ao gerar este teste: com frontal_weight=0.5 (habilita
        knee_cave E knee_over_toe simultaneamente), o SQUAT pode disparar no
        máximo 6 erros num único frame (DEPTH_INSUFFICIENT LOW, KNEE_CAVE_LEFT/
        RIGHT MEDIUM, KNEE_OVER_TOE_LEFT/RIGHT MEDIUM, BACK_NOT_STRAIGHT HIGH),
        totalizando -90 pontos -> score mínimo realista de um único frame de
        SQUAT é 10.0, não 0.0. O piso de 0.0 em calculate_score() só é
        alcançável agregando mais erros do que um único frame de SQUAT pode
        produzir (validado isoladamente em
        TestCalculateScore::test_floor_at_zero, com lista de erros sintética)."""
        lms = lm_map(
            make_landmark(LEFT_KNEE, 0.60, 0.7),
            make_landmark(LEFT_ANKLE, 0.50, 0.9),
            make_landmark(RIGHT_KNEE, 0.40, 0.7),
            make_landmark(RIGHT_ANKLE, 0.50, 0.9),
            make_landmark(LEFT_FOOT_INDEX, 0.45, 0.95),
            make_landmark(RIGHT_FOOT_INDEX, 0.55, 0.95),
        )
        angles = JointAngles(back_angle=90.0, left_knee=100.0, right_knee=100.0)
        errors = _analyze_squat(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.5)
        assert len(errors) == 6
        score = calculate_score(errors, MovementPhase.BOTTOM)
        assert score == 10.0

    def test_score_floor_saturates_at_zero_when_penalties_exceed_100(self):
        """calculate_score() nunca retorna negativo, independente de quantos
        erros reais forem acumulados (aqui: dobro dos erros do teste acima,
        simulando dois frames agregados) -- exercita o piso de 0.0 com uma
        lista de erros de tamanho realista, não apenas o array sintético
        homogêneo do teste original (TestCalculateScore::test_floor_at_zero)."""
        lms = lm_map(
            make_landmark(LEFT_KNEE, 0.60, 0.7),
            make_landmark(LEFT_ANKLE, 0.50, 0.9),
            make_landmark(RIGHT_KNEE, 0.40, 0.7),
            make_landmark(RIGHT_ANKLE, 0.50, 0.9),
            make_landmark(LEFT_FOOT_INDEX, 0.45, 0.95),
            make_landmark(RIGHT_FOOT_INDEX, 0.55, 0.95),
        )
        angles = JointAngles(back_angle=90.0, left_knee=100.0, right_knee=100.0)
        errors = _analyze_squat(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.5)
        doubled_errors = errors + errors
        score = calculate_score(doubled_errors, MovementPhase.BOTTOM)
        assert score == 0.0

    def test_score_is_100_for_perfect_form_end_to_end(self):
        """Squat em pé, todos os ângulos dentro do esperado -- score 100 via
        ExerciseAnalyzer.analyze() completo (não apenas calculate_score isolado)."""
        lms = [
            make_landmark(LEFT_SHOULDER, 0.5, 0.1), make_landmark(RIGHT_SHOULDER, 0.6, 0.1),
            make_landmark(LEFT_HIP, 0.5, 0.4), make_landmark(RIGHT_HIP, 0.6, 0.4),
            make_landmark(LEFT_KNEE, 0.5, 0.7), make_landmark(RIGHT_KNEE, 0.6, 0.7),
            make_landmark(LEFT_ANKLE, 0.5, 0.9), make_landmark(RIGHT_ANKLE, 0.6, 0.9),
        ]
        req = SimpleNamespace(
            session_id="perfect-form", student_id="s", frame_seq=1,
            exercise_type=ExerciseType.SQUAT, landmarks=lms,
        )
        result = ExerciseAnalyzer().analyze(req)
        assert result.score == 100.0
        assert result.errors == []
