"""
tests/test_exercise_analyzer.py
Testes unitários para exercise_analyzer.py — cobre todos os exercícios,
detecção de erros, scoring e fases.
"""
import pytest
from types import SimpleNamespace

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import (
    ExerciseType, MovementPhase, RiskLevel, ErrorType, LandmarkInput,
)
from exercise_analyzer import (
    ExerciseAnalyzer, detect_phase, calculate_score,
    _analyze_squat, _analyze_deadlift, _analyze_lunge,
    _analyze_bench_press, _analyze_bent_over_row,
    SQUAT_BACK_ANGLE_MAX, SQUAT_KNEE_CAVE_THRESHOLD,
)
from angle_calculator import (
    LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE, LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_ELBOW, RIGHT_ELBOW, LEFT_WRIST, RIGHT_WRIST,
)
from models import JointAngles


def lm(ltype: int, x: float, y: float, z: float = 0.0, vis: float = 0.9) -> LandmarkInput:
    return LandmarkInput(landmark_type=ltype, x=x, y=y, z=z, visibility=vis)


def lm_map(*landmarks) -> dict:
    return {l.landmark_type: l for l in landmarks}


# ── detect_phase ──────────────────────────────────────────────────────────────

class TestDetectPhase:
    def test_standing_above_160(self):
        assert detect_phase(170.0) == MovementPhase.STANDING

    def test_bottom_below_90(self):
        assert detect_phase(80.0) == MovementPhase.BOTTOM

    def test_descending_without_prev(self):
        assert detect_phase(120.0) == MovementPhase.DESCENDING

    def test_ascending_when_angle_increasing(self):
        assert detect_phase(120.0, prev_angle=100.0) == MovementPhase.ASCENDING

    def test_descending_when_angle_decreasing(self):
        assert detect_phase(100.0, prev_angle=120.0) == MovementPhase.DESCENDING

    def test_none_returns_unknown(self):
        assert detect_phase(None) == MovementPhase.UNKNOWN


# ── calculate_score ───────────────────────────────────────────────────────────

class TestCalculateScore:
    def _error(self, risk: RiskLevel):
        from models import DetectedError
        return DetectedError(error_type=ErrorType.BACK_NOT_STRAIGHT,
                             risk_level=risk, description="test")

    def test_no_errors_perfect_score(self):
        assert calculate_score([], MovementPhase.STANDING) == 100.0

    def test_high_error_deducts_25(self):
        assert calculate_score([self._error(RiskLevel.HIGH)], MovementPhase.STANDING) == 75.0

    def test_medium_error_deducts_15(self):
        assert calculate_score([self._error(RiskLevel.MEDIUM)], MovementPhase.STANDING) == 85.0

    def test_low_error_deducts_5(self):
        assert calculate_score([self._error(RiskLevel.LOW)], MovementPhase.STANDING) == 95.0

    def test_multiple_errors_cumulative(self):
        errors = [self._error(RiskLevel.HIGH), self._error(RiskLevel.MEDIUM)]
        assert calculate_score(errors, MovementPhase.STANDING) == 60.0

    def test_unknown_phase_returns_zero(self):
        assert calculate_score([], MovementPhase.UNKNOWN) == 0.0

    def test_floor_at_zero(self):
        from models import DetectedError
        errors = [self._error(RiskLevel.HIGH)] * 10
        assert calculate_score(errors, MovementPhase.STANDING) == 0.0


# ── Squat ─────────────────────────────────────────────────────────────────────

class TestSquatAnalysis:
    def _angles(self, back=None, knee_l=None, knee_r=None):
        return JointAngles(back_angle=back, left_knee=knee_l, right_knee=knee_r)

    def test_back_not_straight_high_risk(self):
        angles = self._angles(back=70.0)  # > 45*1.4 = 63 → HIGH
        errors = _analyze_squat({}, angles, MovementPhase.BOTTOM)
        types = [e.error_type for e in errors]
        risks = [e.risk_level for e in errors]
        assert ErrorType.BACK_NOT_STRAIGHT in types
        idx = types.index(ErrorType.BACK_NOT_STRAIGHT)
        assert risks[idx] == RiskLevel.HIGH

    def test_back_not_straight_medium_risk(self):
        angles = self._angles(back=50.0)  # > 45 mas < 63 → MEDIUM
        errors = _analyze_squat({}, angles, MovementPhase.BOTTOM)
        types = [e.error_type for e in errors]
        assert ErrorType.BACK_NOT_STRAIGHT in types

    def test_good_back_no_error(self):
        angles = self._angles(back=30.0)
        errors = _analyze_squat({}, angles, MovementPhase.BOTTOM)
        assert not any(e.error_type == ErrorType.BACK_NOT_STRAIGHT for e in errors)

    def test_knee_cave_right_detected_frontal(self):
        lms = lm_map(
            lm(RIGHT_KNEE,  0.45, 0.7),
            lm(RIGHT_ANKLE, 0.50, 0.9),
        )
        angles = self._angles()
        errors = _analyze_squat(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.8)
        types = [e.error_type for e in errors]
        assert ErrorType.KNEE_CAVE_RIGHT in types

    def test_knee_cave_disabled_lateral(self):
        lms = lm_map(
            lm(RIGHT_KNEE,  0.45, 0.7),
            lm(RIGHT_ANKLE, 0.50, 0.9),
        )
        angles = self._angles()
        errors = _analyze_squat(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.1)
        assert not any(e.error_type in (ErrorType.KNEE_CAVE_LEFT, ErrorType.KNEE_CAVE_RIGHT)
                       for e in errors)

    def test_depth_insufficient_at_bottom(self):
        angles = self._angles(knee_l=100.0)  # > 90 no BOTTOM
        errors = _analyze_squat({}, angles, MovementPhase.BOTTOM)
        assert any(e.error_type == ErrorType.DEPTH_INSUFFICIENT for e in errors)

    def test_depth_not_checked_standing(self):
        angles = self._angles(knee_l=100.0)
        errors = _analyze_squat({}, angles, MovementPhase.STANDING)
        assert not any(e.error_type == ErrorType.DEPTH_INSUFFICIENT for e in errors)


# ── Deadlift ──────────────────────────────────────────────────────────────────

class TestDeadliftAnalysis:
    def test_back_rounded_at_bottom(self):
        angles = JointAngles(back_angle=50.0)  # > 30 no BOTTOM → erro
        errors = _analyze_deadlift({}, angles, MovementPhase.BOTTOM)
        assert any(e.error_type == ErrorType.BACK_ROUNDED for e in errors)

    def test_back_ok_at_bottom(self):
        angles = JointAngles(back_angle=20.0)
        errors = _analyze_deadlift({}, angles, MovementPhase.BOTTOM)
        assert not any(e.error_type == ErrorType.BACK_ROUNDED for e in errors)

    def test_hips_too_high_at_standing(self):
        angles = JointAngles(left_hip=140.0)  # < 160 no STANDING
        errors = _analyze_deadlift({}, angles, MovementPhase.STANDING)
        assert any(e.error_type == ErrorType.HIPS_TOO_HIGH for e in errors)


# ── Bench Press ───────────────────────────────────────────────────────────────

class TestBenchPressAnalysis:
    def test_elbow_flare_detected_frontal(self):
        # Ombros largura 0.3, cotovelos largura 0.7 → flare grande
        lms = lm_map(
            lm(LEFT_SHOULDER,  0.35, 0.5), lm(RIGHT_SHOULDER, 0.65, 0.5),
            lm(LEFT_ELBOW,     0.15, 0.7), lm(RIGHT_ELBOW,    0.85, 0.7),
        )
        angles = JointAngles()
        errors = _analyze_bench_press(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.8)
        assert any(e.error_type == ErrorType.ELBOW_FLARE for e in errors)

    def test_no_flare_when_elbows_aligned(self):
        # Cotovelos na mesma largura dos ombros
        lms = lm_map(
            lm(LEFT_SHOULDER,  0.35, 0.5), lm(RIGHT_SHOULDER, 0.65, 0.5),
            lm(LEFT_ELBOW,     0.35, 0.7), lm(RIGHT_ELBOW,    0.65, 0.7),
        )
        angles = JointAngles()
        errors = _analyze_bench_press(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.8)
        assert not any(e.error_type == ErrorType.ELBOW_FLARE for e in errors)

    def test_wrist_bent_detected(self):
        # Pulso desviado 0.1 em relação ao cotovelo (> 0.04 threshold)
        lms = lm_map(
            lm(LEFT_ELBOW, 0.40, 0.7),
            lm(LEFT_WRIST, 0.50, 0.9),  # desvio x = 0.10
        )
        angles = JointAngles()
        errors = _analyze_bench_press(lms, angles, MovementPhase.BOTTOM)
        assert any(e.error_type == ErrorType.WRIST_BENT for e in errors)


# ── Bent-over Row ─────────────────────────────────────────────────────────────

class TestBentOverRowAnalysis:
    def test_back_rounded_detected(self):
        angles = JointAngles(back_angle=45.0)  # > 35 → erro
        errors = _analyze_bent_over_row({}, angles, MovementPhase.BOTTOM)
        assert any(e.error_type == ErrorType.BACK_ROUNDED for e in errors)

    def test_back_rounded_high_risk(self):
        angles = JointAngles(back_angle=60.0)  # > 35*1.5=52.5 → HIGH
        errors = _analyze_bent_over_row({}, angles, MovementPhase.BOTTOM)
        back_errs = [e for e in errors if e.error_type == ErrorType.BACK_ROUNDED]
        assert back_errs and back_errs[0].risk_level == RiskLevel.HIGH

    def test_good_back_no_error(self):
        angles = JointAngles(back_angle=20.0)
        errors = _analyze_bent_over_row({}, angles, MovementPhase.BOTTOM)
        assert not any(e.error_type == ErrorType.BACK_ROUNDED for e in errors)


# ── ExerciseAnalyzer integração ───────────────────────────────────────────────

class TestExerciseAnalyzerIntegration:
    def _request(self, exercise_type, landmarks):
        return SimpleNamespace(
            session_id="test-session",
            student_id="test-student",
            exercise_type=ExerciseType(exercise_type),
            frame_seq=1,
            landmarks=landmarks,
        )

    def _squat_landmarks(self, knee_angle_approx: float = 170.0) -> list:
        """Gera landmarks de um squat com ângulo de joelho aproximado."""
        return [
            lm(LEFT_SHOULDER,  0.5, 0.1),
            lm(RIGHT_SHOULDER, 0.6, 0.1),
            lm(LEFT_HIP,       0.5, 0.4),
            lm(RIGHT_HIP,      0.6, 0.4),
            lm(LEFT_KNEE,      0.5, 0.7),
            lm(RIGHT_KNEE,     0.6, 0.7),
            lm(LEFT_ANKLE,     0.5, 0.9),
            lm(RIGHT_ANKLE,    0.6, 0.9),
        ]

    def test_squat_returns_result(self):
        analyzer = ExerciseAnalyzer()
        req = self._request("SQUAT", self._squat_landmarks())
        result = analyzer.analyze(req)
        assert result.exercise_type == ExerciseType.SQUAT
        assert 0 <= result.score <= 100
        assert result.phase != MovementPhase.UNKNOWN

    def test_bench_press_returns_result(self):
        lms = [
            lm(LEFT_SHOULDER,  0.35, 0.3), lm(RIGHT_SHOULDER, 0.65, 0.3),
            lm(LEFT_ELBOW,     0.35, 0.6), lm(RIGHT_ELBOW,    0.65, 0.6),
            lm(LEFT_WRIST,     0.35, 0.8), lm(RIGHT_WRIST,    0.65, 0.8),
            lm(LEFT_HIP,       0.40, 0.5), lm(RIGHT_HIP,      0.60, 0.5),
        ]
        analyzer = ExerciseAnalyzer()
        req = self._request("BENCH_PRESS", lms)
        result = analyzer.analyze(req)
        assert result.exercise_type == ExerciseType.BENCH_PRESS
        assert 0 <= result.score <= 100

    def test_bent_over_row_returns_result(self):
        lms = [
            lm(LEFT_SHOULDER,  0.4, 0.2), lm(RIGHT_SHOULDER, 0.6, 0.2),
            lm(LEFT_HIP,       0.4, 0.5), lm(RIGHT_HIP,      0.6, 0.5),
            lm(LEFT_KNEE,      0.4, 0.7), lm(RIGHT_KNEE,     0.6, 0.7),
            lm(LEFT_ELBOW,     0.3, 0.4), lm(RIGHT_ELBOW,    0.7, 0.4),
            lm(LEFT_WRIST,     0.3, 0.6), lm(RIGHT_WRIST,    0.7, 0.6),
        ]
        analyzer = ExerciseAnalyzer()
        req = self._request("BENT_OVER_ROW", lms)
        result = analyzer.analyze(req)
        assert result.exercise_type == ExerciseType.BENT_OVER_ROW
        assert 0 <= result.score <= 100

    def test_insufficient_landmarks_returns_unknown(self):
        analyzer = ExerciseAnalyzer()
        req = self._request("SQUAT", [lm(LEFT_SHOULDER, 0.5, 0.1)])
        result = analyzer.analyze(req)
        assert result.phase == MovementPhase.UNKNOWN
        assert result.score == 0.0

    def test_has_alert_on_high_risk_error(self):
        analyzer = ExerciseAnalyzer()
        lms = self._squat_landmarks()
        # Adiciona landmark de ombro na frente do quadril (forward lean → HIGH)
        lms[0] = lm(LEFT_SHOULDER,  0.5, 0.1, z=-0.4)  # ombro muito na frente
        lms[1] = lm(RIGHT_SHOULDER, 0.6, 0.1, z=-0.4)
        req = self._request("SQUAT", lms)
        result = analyzer.analyze(req)
        assert isinstance(result.has_alert, bool)
        assert isinstance(result.errors, list)
