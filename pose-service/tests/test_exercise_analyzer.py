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
    ExerciseType, MovementPhase, RiskLevel, ErrorType, LandmarkInput, AlertSeverity,
)
from exercise_analyzer import (
    ExerciseAnalyzer, detect_phase, calculate_score, _alert_severity,
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


# ── Bug 1: fase do movimento (ASCENDING/DESCENDING) através de frames ────────
# Regressão: analyze() nunca repassava o ângulo do joelho do frame anterior
# para detect_phase(), então todo frame intermediário (90°-160°) caía no ramo
# "sem histórico" e era sempre classificado como DESCENDING — ASCENDING nunca
# era produzido em produção, mesmo com o atleta subindo.

class TestPhaseTracksAcrossSessionFrames:
    def _frame(self, knee_x_offset: float) -> list:
        """Quanto maior o offset, mais dobrado o joelho (ângulo menor)."""
        return [
            lm(LEFT_SHOULDER, 0.5, 0.1),
            lm(LEFT_HIP,      0.5, 0.4),
            lm(LEFT_KNEE,     0.5 + knee_x_offset, 0.7),
            lm(LEFT_ANKLE,    0.5, 0.9),
        ]

    def _request(self, landmarks, seq=1, session_id="sess-phase"):
        return SimpleNamespace(
            session_id=session_id, student_id="s", frame_seq=seq,
            exercise_type=ExerciseType.SQUAT, landmarks=landmarks,
        )

    def test_ascending_detected_when_knee_angle_increases_across_frames(self):
        analyzer = ExerciseAnalyzer()
        analyzer.analyze(self._request(self._frame(0.15), seq=1))  # mais dobrado
        result = analyzer.analyze(self._request(self._frame(0.05), seq=2))  # estendendo
        assert result.phase == MovementPhase.ASCENDING

    def test_descending_detected_when_knee_angle_decreases_across_frames(self):
        analyzer = ExerciseAnalyzer()
        analyzer.analyze(self._request(self._frame(0.05), seq=1))  # mais estendido
        result = analyzer.analyze(self._request(self._frame(0.15), seq=2))  # dobrando
        assert result.phase == MovementPhase.DESCENDING

    def test_phase_tracking_is_isolated_per_session(self):
        analyzer = ExerciseAnalyzer()
        analyzer.analyze(self._request(self._frame(0.15), seq=1, session_id="a"))
        # Primeiro frame de uma sessão nova não deve herdar o histórico da sessão "a"
        result = analyzer.analyze(self._request(self._frame(0.05), seq=1, session_id="b"))
        assert result.phase == MovementPhase.DESCENDING


# ── Bug 2: persistência do alarme de knee cave sob ruído de frame a frame ────
# Regressão: o desvio percentual (knee-ankle) era comparado ao threshold sem
# nenhuma suavização — jitter típico de pose estimation fazia o valor cruzar
# o threshold pra cima e pra baixo a cada frame, "piscando" o alarme mesmo com
# a posição real do joelho estável e colapsada.

class TestKneeCavePersistsAcrossNoisyFrames:
    def _lm_map(self, knee_x_offset: float) -> dict:
        return {
            LEFT_KNEE:  lm(LEFT_KNEE,  0.5 + knee_x_offset, 0.7),
            LEFT_ANKLE: lm(LEFT_ANKLE, 0.5, 0.9),
        }

    def test_flickers_without_smoothing_state(self):
        """Comportamento antigo (referência): sem estado de suavização, o
        alarme some em frames cujo ruído cai abaixo do threshold."""
        angles = JointAngles()
        detected = []
        for offset in (0.030, 0.015, 0.032, 0.018):  # alterna acima/abaixo de 2%
            errors = _analyze_squat(
                self._lm_map(offset), angles, MovementPhase.BOTTOM,
                frontal_weight=0.8,
            )
            detected.append(any(e.error_type == ErrorType.KNEE_CAVE_LEFT for e in errors))
        assert detected == [True, False, True, False]

    def test_persists_across_noisy_frames_with_smoothing_state(self):
        """Corrigido: com o estado de suavização por sessão, o alarme
        permanece ativo enquanto o desvio (suavizado) superar o threshold,
        mesmo que frames individuais oscilem por ruído."""
        angles = JointAngles()
        smoothing_state: dict = {}
        detected = []
        for offset in (0.030, 0.015, 0.032, 0.018, 0.031, 0.016):
            errors = _analyze_squat(
                self._lm_map(offset), angles, MovementPhase.BOTTOM,
                frontal_weight=0.8, smoothing_state=smoothing_state,
            )
            detected.append(any(e.error_type == ErrorType.KNEE_CAVE_LEFT for e in errors))
        assert all(detected), f"esperado alarme persistente em todos os frames, obtido {detected}"

    def test_clears_once_deviation_genuinely_drops(self):
        """O alarme ainda deve desaparecer quando a posição real do joelho
        volta a ficar correta de forma sustentada (não apenas ruído de 1 frame)."""
        angles = JointAngles()
        smoothing_state: dict = {}
        for offset in (0.035, 0.032, 0.034):  # joelho colapsado, sustentado
            _analyze_squat(
                self._lm_map(offset), angles, MovementPhase.BOTTOM,
                frontal_weight=0.8, smoothing_state=smoothing_state,
            )
        for offset in (0.0, 0.0, 0.0, 0.0, 0.0, 0.0):  # corrige e sustenta
            errors = _analyze_squat(
                self._lm_map(offset), angles, MovementPhase.BOTTOM,
                frontal_weight=0.8, smoothing_state=smoothing_state,
            )
        assert not any(e.error_type == ErrorType.KNEE_CAVE_LEFT for e in errors)


# ── Bug 3: verificação de postura do tronco não pode ser silenciada por ─────
# oclusão momentânea de landmark
# Regressão: quando o landmark do ombro fica indisponível por 1-2 frames
# (ex.: barra cobrindo o ombro no fundo do agachamento), back_angle vira None
# e a verificação de BACK_NOT_STRAIGHT é silenciosamente pulada — o sistema
# reporta "postura correta" mesmo com o tronco visivelmente caído.

class TestPostureCheckSurvivesMomentaryOcclusion:
    def _good_frame(self) -> list:
        """Tronco bem inclinado (back_angle > 45°) com todos os landmarks visíveis."""
        return [
            lm(LEFT_SHOULDER, 0.75, 0.30),
            lm(LEFT_HIP,      0.35, 0.55),
            lm(LEFT_KNEE,     0.55, 0.70),
            lm(LEFT_ANKLE,    0.45, 0.95),
        ]

    def _occluded_frame(self) -> list:
        """Mesmo agachamento, mas sem o landmark do ombro neste frame."""
        return [
            lm(LEFT_HIP,   0.35, 0.55),
            lm(LEFT_KNEE,  0.55, 0.70),
            lm(LEFT_ANKLE, 0.45, 0.95),
        ]

    def _request(self, landmarks, seq):
        return SimpleNamespace(
            session_id="sess-posture", student_id="s", frame_seq=seq,
            exercise_type=ExerciseType.SQUAT, landmarks=landmarks,
        )

    def test_back_not_straight_persists_through_one_frame_of_occlusion(self):
        analyzer = ExerciseAnalyzer()
        r1 = analyzer.analyze(self._request(self._good_frame(), seq=1))
        assert any(e.error_type == ErrorType.BACK_NOT_STRAIGHT for e in r1.errors)

        r2 = analyzer.analyze(self._request(self._occluded_frame(), seq=2))
        assert r2.joint_angles.back_angle is not None
        assert any(e.error_type == ErrorType.BACK_NOT_STRAIGHT for e in r2.errors)
        assert r2.score < 100.0

    def test_interpolation_expires_after_prolonged_occlusion(self):
        """Interpolação não deve mascarar indefinidamente uma oclusão real e
        prolongada (ex.: pessoa saiu de quadro) — deve expirar após N frames."""
        analyzer = ExerciseAnalyzer()
        analyzer.analyze(self._request(self._good_frame(), seq=1))

        last_back_angle = None
        for seq in range(2, 8):
            r = analyzer.analyze(self._request(self._occluded_frame(), seq=seq))
            last_back_angle = r.joint_angles.back_angle

        assert last_back_angle is None


# ── UX: severidade de alerta (Aviso/Grave) e descrições sem métricas ────────
# Pedido do usuário: nenhum valor numérico de desvio (%/graus) deve aparecer
# na mensagem do alerta — isso é dado interno só para a lógica de threshold.
# Severidade exibida na UI tem 2 níveis: WARNING (aviso) e CRITICAL (grave).
# Tipos de erro com risco de lesão (joelho colapsando, lombar arredondada/
# tronco caído, joelho passando do pé) são sempre CRITICAL ao disparar,
# independente do percentual; os demais escalam para CRITICAL só quando o
# desvio supera 2x o threshold mínimo de detecção.

class TestAlertSeverityClassification:
    def test_always_critical_error_types_ignore_magnitude(self):
        """Knee cave/knee-over-toe/back: críticos mesmo com desvio mínimo
        (ratio≈1), porque o tipo de erro já é risco de lesão por definição."""
        assert _alert_severity(ErrorType.KNEE_CAVE_LEFT, RiskLevel.MEDIUM, ratio=1.01) == AlertSeverity.CRITICAL
        assert _alert_severity(ErrorType.KNEE_CAVE_RIGHT, RiskLevel.MEDIUM, ratio=1.01) == AlertSeverity.CRITICAL
        assert _alert_severity(ErrorType.KNEE_OVER_TOE_LEFT, RiskLevel.MEDIUM, ratio=1.01) == AlertSeverity.CRITICAL
        assert _alert_severity(ErrorType.BACK_NOT_STRAIGHT, RiskLevel.MEDIUM, ratio=1.01) == AlertSeverity.CRITICAL
        assert _alert_severity(ErrorType.BACK_ROUNDED, RiskLevel.MEDIUM, ratio=1.01) == AlertSeverity.CRITICAL

    def test_high_risk_level_is_always_critical(self):
        assert _alert_severity(ErrorType.ELBOW_FLARE, RiskLevel.HIGH) == AlertSeverity.CRITICAL

    def test_mild_deviation_on_non_injury_type_is_warning(self):
        """Erros que não são de risco de lesão (ex.: amplitude/profundidade)
        ficam como aviso enquanto o desvio não passar do dobro do threshold."""
        assert _alert_severity(ErrorType.DEPTH_INSUFFICIENT, RiskLevel.LOW, ratio=1.1) == AlertSeverity.WARNING
        assert _alert_severity(ErrorType.ELBOW_INSUFFICIENT_RANGE, RiskLevel.MEDIUM, ratio=1.5) == AlertSeverity.WARNING
        assert _alert_severity(ErrorType.ROW_INCOMPLETE, RiskLevel.MEDIUM, ratio=1.9) == AlertSeverity.WARNING

    def test_deviation_over_double_threshold_escalates_to_critical(self):
        assert _alert_severity(ErrorType.WRIST_BENT, RiskLevel.MEDIUM, ratio=1.9) == AlertSeverity.WARNING
        assert _alert_severity(ErrorType.WRIST_BENT, RiskLevel.MEDIUM, ratio=2.0) == AlertSeverity.CRITICAL
        assert _alert_severity(ErrorType.WRIST_BENT, RiskLevel.MEDIUM, ratio=3.0) == AlertSeverity.CRITICAL

    def test_no_ratio_and_not_high_defaults_to_warning(self):
        assert _alert_severity(ErrorType.HIPS_TOO_HIGH, RiskLevel.LOW) == AlertSeverity.WARNING


class TestErrorDescriptionsHaveNoEmbeddedMetrics:
    """Nenhuma descrição de erro deve conter dígitos — desvios percentuais/
    graus são dados internos (joint_angle/threshold_violated), não texto."""

    def _assert_clean(self, errors):
        import re
        for err in errors:
            assert not re.search(r"\d", err.description), (
                f"{err.error_type}: descrição contém número: {err.description!r}"
            )
            assert err.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL)

    def test_squat_descriptions_clean(self):
        lms = lm_map(
            lm(LEFT_KNEE, 0.53, 0.7), lm(LEFT_ANKLE, 0.5, 0.9),
        )
        angles = JointAngles(left_knee=100.0, back_angle=70.0)
        errors = _analyze_squat(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.8)
        assert len(errors) >= 2
        self._assert_clean(errors)

    def test_deadlift_descriptions_clean(self):
        errors = _analyze_deadlift({}, JointAngles(back_angle=50.0), MovementPhase.BOTTOM)
        errors += _analyze_deadlift({}, JointAngles(left_hip=140.0), MovementPhase.STANDING)
        assert len(errors) == 2
        self._assert_clean(errors)

    def test_lunge_descriptions_clean(self):
        errors = _analyze_lunge({}, JointAngles(left_knee=60.0, back_angle=50.0), MovementPhase.BOTTOM)
        assert len(errors) == 2
        self._assert_clean(errors)

    def test_bench_press_descriptions_clean(self):
        lms = lm_map(
            lm(LEFT_SHOULDER, 0.35, 0.5), lm(RIGHT_SHOULDER, 0.65, 0.5),
            lm(LEFT_ELBOW, 0.15, 0.7), lm(RIGHT_ELBOW, 0.85, 0.7),
            lm(LEFT_WRIST, 0.50, 0.9),
        )
        errors = _analyze_bench_press(lms, JointAngles(), MovementPhase.BOTTOM, frontal_weight=0.8)
        assert len(errors) >= 2
        self._assert_clean(errors)

    def test_bent_over_row_descriptions_clean(self):
        lms = lm_map(
            lm(LEFT_SHOULDER, 0.4, 0.2), lm(LEFT_ELBOW, 0.3, 0.4), lm(LEFT_WRIST, 0.3, 0.3),
        )
        errors = _analyze_bent_over_row(lms, JointAngles(back_angle=60.0), MovementPhase.BOTTOM)
        assert len(errors) == 2
        self._assert_clean(errors)

    def test_knee_cave_and_back_errors_are_always_critical_severity(self):
        lms = lm_map(
            lm(LEFT_KNEE, 0.53, 0.7), lm(LEFT_ANKLE, 0.5, 0.9),
        )
        angles = JointAngles(back_angle=46.0)  # apenas 1° acima do threshold (45°)
        errors = _analyze_squat(lms, angles, MovementPhase.BOTTOM, frontal_weight=0.8)
        knee_cave = [e for e in errors if e.error_type == ErrorType.KNEE_CAVE_LEFT]
        back = [e for e in errors if e.error_type == ErrorType.BACK_NOT_STRAIGHT]
        assert knee_cave and knee_cave[0].severity == AlertSeverity.CRITICAL
        assert back and back[0].severity == AlertSeverity.CRITICAL
