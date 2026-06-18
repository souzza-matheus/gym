"""
tests/test_ai_exercise_engine.py
Testes de regressão para o motor de IA (ai_exercise_classifier.py +
ai_exercise_analyzer.py) que substituiu o motor de regras hardcoded.

Usa ai/synthetic_body.py (mesmo gerador usado para treinar os modelos)
para construir landmarks com alvos biomecânicos conhecidos e verifica que
os modelos treinados reagem de forma sã — boa forma marcada como boa,
forma claramente ruim sinalizada com o erro certo e risco coerente.
"""
import sys
import os
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import ExerciseType, MovementPhase, RiskLevel, ErrorType  # noqa: E402
from ai.synthetic_body import build_frame  # noqa: E402
import ai_exercise_classifier as ai_classifier  # noqa: E402
import ai_exercise_analyzer as ai_analyzer  # noqa: E402


def _request(exercise_type, landmarks):
    return SimpleNamespace(
        session_id="test-session", student_id="test-student",
        exercise_type=ExerciseType(exercise_type), frame_seq=1, landmarks=landmarks,
    )


def _errors_by_type(result):
    return {e.error_type: e.risk_level for e in result.errors}


# ── Classificador de exercício ────────────────────────────────────────────

class TestAiExerciseClassifier:
    def test_squat_bottom_classified_as_squat(self):
        lms = build_frame("FRONTAL", knee_angle=70, back_angle=20, noise_sigma=0.003)
        result = ai_classifier.classify_single(lms)
        assert result.exercise_type == ExerciseType.SQUAT
        assert result.confidence > 0.5

    def test_bench_classified_as_bench_press(self):
        # back_angle alto representa o tronco deitado no banco — ver
        # comentário em ai/dataset_generator._sample_bench().
        lms = build_frame(
            "LATERAL", knee_angle=100, back_angle=78,
            arm_angle_left=90, arm_angle_right=90, noise_sigma=0.003,
        )
        result = ai_classifier.classify_single(lms)
        assert result.exercise_type == ExerciseType.BENCH_PRESS

    def test_empty_frames_returns_unknown(self):
        result = ai_classifier.classify_frames([])
        assert result.exercise_type == ExerciseType.UNKNOWN
        assert result.confidence == 0.0


# ── Analisador de forma — Squat ───────────────────────────────────────────

class TestAiSquatAnalysis:
    def test_good_standing_form_high_score_no_errors(self):
        lms = build_frame("LATERAL", knee_angle=175, back_angle=5, noise_sigma=0.003)
        result = ai_analyzer.analyzer.analyze(_request("SQUAT", lms))
        assert result.phase == MovementPhase.STANDING
        assert result.score >= 90.0
        assert not result.errors

    def test_excessive_forward_lean_flagged_high_risk(self):
        lms = build_frame("LATERAL", knee_angle=70, back_angle=70, noise_sigma=0.003)
        result = ai_analyzer.analyzer.analyze(_request("SQUAT", lms))
        errors = _errors_by_type(result)
        assert ErrorType.BACK_NOT_STRAIGHT in errors
        assert errors[ErrorType.BACK_NOT_STRAIGHT] == RiskLevel.HIGH
        assert result.score < 90.0

    def test_knee_cave_detected_frontal_camera(self):
        lms = build_frame(
            "FRONTAL", knee_angle=75, back_angle=10,
            knee_cave_pct_left=12, knee_cave_pct_right=11, noise_sigma=0.003,
        )
        result = ai_analyzer.analyzer.analyze(_request("SQUAT", lms))
        errors = _errors_by_type(result)
        assert ErrorType.KNEE_CAVE_LEFT in errors or ErrorType.KNEE_CAVE_RIGHT in errors

    def test_has_alert_true_when_medium_or_high_error(self):
        lms = build_frame("LATERAL", knee_angle=70, back_angle=70, noise_sigma=0.003)
        result = ai_analyzer.analyzer.analyze(_request("SQUAT", lms))
        assert result.has_alert is True


# ── Analisador de forma — Deadlift (cobre a correção do gate de fase) ─────

class TestAiDeadliftAnalysis:
    def test_rounded_back_detected_during_descent(self):
        """
        Regressão: no motor de regras original, BACK_ROUNDED só disparava em
        ASCENDING/BOTTOM — mas ASCENDING nunca é produzido em produção
        (analyze() nunca passa prev_angle), então lombar arredondada durante
        a DESCIDA nunca era sinalizada. O dataset de treino corrige esse
        gate (ver ai/dataset_generator.py); este teste garante que o
        comportamento corrigido realmente chegou ao modelo treinado.
        """
        lms = build_frame("LATERAL", knee_angle=120, back_angle=55, noise_sigma=0.003)
        result = ai_analyzer.analyzer.analyze(_request("DEADLIFT", lms))
        assert result.phase == MovementPhase.DESCENDING
        errors = _errors_by_type(result)
        assert ErrorType.BACK_ROUNDED in errors

    def test_good_lockout_no_errors(self):
        lms = build_frame("LATERAL", knee_angle=178, back_angle=2, noise_sigma=0.003)
        result = ai_analyzer.analyzer.analyze(_request("DEADLIFT", lms))
        assert result.phase == MovementPhase.STANDING
        assert ErrorType.HIPS_TOO_HIGH not in _errors_by_type(result)


# ── Analisador de forma — Bench Press ──────────────────────────────────────

class TestAiBenchPressAnalysis:
    def test_elbow_flare_detected(self):
        lms = build_frame(
            "FRONTAL", knee_angle=100, back_angle=78,
            elbow_flare_pct=40, arm_angle_left=90, arm_angle_right=90, noise_sigma=0.003,
        )
        result = ai_analyzer.analyzer.analyze(_request("BENCH_PRESS", lms))
        errors = _errors_by_type(result)
        assert ErrorType.ELBOW_FLARE in errors
        assert errors[ErrorType.ELBOW_FLARE] == RiskLevel.HIGH

    def test_good_form_no_flare(self):
        lms = build_frame(
            "FRONTAL", knee_angle=100, back_angle=78,
            elbow_flare_pct=0, arm_angle_left=60, arm_angle_right=60,
            wrist_extra_dev_left=0, wrist_extra_dev_right=0, noise_sigma=0.003,
        )
        result = ai_analyzer.analyzer.analyze(_request("BENCH_PRESS", lms))
        assert ErrorType.ELBOW_FLARE not in _errors_by_type(result)


# ── Fallback legado (LUNGE / BENT_OVER_ROW ainda sem modelo treinado) ─────

class TestRuleFallbackForUntrainedExercises:
    def test_lunge_uses_rule_fallback_and_returns_valid_result(self):
        lms = build_frame(
            "LATERAL", knee_angle=90, knee_angle_left=90, knee_angle_right=160,
            back_angle=10, stance_offset_right=0.25, noise_sigma=0.003,
        )
        result = ai_analyzer.analyzer.analyze(_request("LUNGE", lms))
        assert result.exercise_type == ExerciseType.LUNGE
        assert 0 <= result.score <= 100

    def test_bent_over_row_uses_rule_fallback_and_returns_valid_result(self):
        lms = build_frame("LATERAL", knee_angle=160, back_angle=60, noise_sigma=0.003)
        result = ai_analyzer.analyzer.analyze(_request("BENT_OVER_ROW", lms))
        assert result.exercise_type == ExerciseType.BENT_OVER_ROW
        assert 0 <= result.score <= 100


# ── Landmarks insuficientes ─────────────────────────────────────────────

class TestInsufficientLandmarks:
    def test_insufficient_landmarks_returns_unknown(self):
        from models import LandmarkInput
        lms = [LandmarkInput(landmark_type=11, x=0.5, y=0.1, z=0.0, visibility=0.9)]
        result = ai_analyzer.analyzer.analyze(_request("SQUAT", lms))
        assert result.phase == MovementPhase.UNKNOWN
        assert result.score == 0.0
