"""
video_analyzer.py — GymVision Pose + Analyzer Service

Analisa um arquivo de vídeo (.mp4 / .mov / .avi) simulando o comportamento
do app Android em tempo real:

  1. Extrai frames no intervalo configurável (padrão: 200ms = 5fps de análise)
  2. Executa detecção de pose em cada frame (MoveNet via TF Serving)
  3. Executa análise de exercício (ângulos, fase, erros, score)
  4. Detecta repetições via transições de fase (STANDING→BOTTOM→STANDING)
  5. Aplica throttle de alertas (mesmo 5s do app)
  6. Simula notificação ao professor para erros MEDIUM/HIGH
  7. Retorna relatório completo com timeline, rep scores e alertas disparados

Endpoint: POST /api/v1/pose/analyze-video
"""

import asyncio
import io
import logging
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ai_exercise_analyzer import ExerciseAnalyzer
from models import ExerciseType, MovementPhase, RiskLevel

log = logging.getLogger(__name__)

THROTTLE_S = 5.0
DEFAULT_FRAME_INTERVAL_MS = 200     # analisa 1 frame a cada 200ms (5fps)
MAX_VIDEO_DURATION_S = 300          # 5 minutos max


# ── Estruturas de resultado ───────────────────────────────────────────────────

@dataclass
class FrameResult:
    frame_seq: int
    timestamp_ms: float
    phase: str
    score: float
    landmark_count: int
    errors: list        # list[DetectedError]
    has_alert: bool
    joint_angles: dict  # para o relatório


@dataclass
class RepResult:
    rep_number: int
    start_ms: float
    end_ms: float
    min_knee_angle: Optional[float]
    avg_score: float
    errors_in_rep: list[str]
    risk_level: str     # pior risco da rep


@dataclass
class AlertEvent:
    """
    Representa um alerta que seria enviado ao professor via WebSocket/RabbitMQ.
    Simula exatamente o payload de gym.alert.created.
    """
    timestamp_ms: float
    frame_seq: int
    error_type: str
    risk_level: str
    description: str
    joint_angle: Optional[float]
    score: float
    phase: str


@dataclass
class VideoAnalysisReport:
    # Metadata
    exercise_type: str
    video_duration_ms: float
    total_frames_analyzed: int
    frames_with_landmarks: int
    analysis_fps: float

    # Scores
    avg_score: float
    min_score: float
    max_score: float
    score_timeline: list[dict]      # [{ms, score, phase}]

    # Repetições
    total_reps: int
    reps: list[dict]

    # Erros
    total_alerts_fired: int
    error_frequency: dict           # {error_type: count}
    top_errors: list[dict]          # top 5 erros por frequência

    # Alertas ao professor (simulados)
    professor_alerts: list[dict]    # payload completo de cada alerta disparado

    # Por fase
    phase_distribution: dict        # {phase: frame_count}
    avg_score_by_phase: dict        # {phase: avg_score}

    # Frames com problemas críticos
    critical_frames: list[dict]     # frames com score < 50 ou erro HIGH


# ── Rep counter ───────────────────────────────────────────────────────────────

class RepCounter:
    """
    Detecta repetições via transição de fases.
    Ciclo completo: STANDING → DESCENDING → BOTTOM → ASCENDING → STANDING
    Aceita variações parciais para robustez com vídeos curtos.
    """

    def __init__(self):
        self.reps: list[RepResult] = []
        self._rep_frames: list[FrameResult] = []
        self._prev_phase = MovementPhase.UNKNOWN
        self._rep_start_ms = 0.0
        self._in_rep = False
        self._saw_bottom = False

    def feed(self, frame: FrameResult):
        phase = MovementPhase(frame.phase) if frame.phase in MovementPhase._value2member_map_ else MovementPhase.UNKNOWN

        # Início de rep: desceu do STANDING
        if (not self._in_rep and
                self._prev_phase == MovementPhase.STANDING and
                phase == MovementPhase.DESCENDING):
            self._in_rep = True
            self._rep_start_ms = frame.timestamp_ms
            self._rep_frames = []
            self._saw_bottom = False

        if self._in_rep:
            self._rep_frames.append(frame)
            if phase == MovementPhase.BOTTOM:
                self._saw_bottom = True

            # Fim de rep: voltou ao STANDING depois de ter estado no BOTTOM
            if (self._saw_bottom and
                    self._prev_phase in (MovementPhase.ASCENDING, MovementPhase.BOTTOM) and
                    phase == MovementPhase.STANDING):
                self._finish_rep(frame.timestamp_ms)

        self._prev_phase = phase

    def _finish_rep(self, end_ms: float):
        frames = self._rep_frames
        if not frames:
            return

        scores = [f.score for f in frames if f.score > 0]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        knee_angles = [
            f.joint_angles.get("left_knee") or f.joint_angles.get("right_knee")
            for f in frames
            if f.joint_angles.get("left_knee") or f.joint_angles.get("right_knee")
        ]
        min_knee = min(knee_angles) if knee_angles else None

        all_errors = [e.error_type.value for f in frames for e in f.errors]
        risk_levels = [e.risk_level.value for f in frames for e in f.errors]
        worst_risk = "LOW"
        if "HIGH" in risk_levels:
            worst_risk = "HIGH"
        elif "MEDIUM" in risk_levels:
            worst_risk = "MEDIUM"

        self.reps.append(RepResult(
            rep_number=len(self.reps) + 1,
            start_ms=self._rep_start_ms,
            end_ms=end_ms,
            min_knee_angle=round(min_knee, 1) if min_knee else None,
            avg_score=round(avg_score, 1),
            errors_in_rep=list(set(all_errors)),
            risk_level=worst_risk,
        ))

        self._in_rep = False
        self._rep_frames = []
        self._saw_bottom = False

    def finish(self):
        """Força fechamento da última rep se o vídeo terminar mid-rep."""
        if self._in_rep and self._rep_frames:
            self._finish_rep(self._rep_frames[-1].timestamp_ms)


# ── Pipeline principal ────────────────────────────────────────────────────────

class VideoAnalyzer:
    """
    Processa um vídeo frame a frame, simulando o comportamento do app Android.
    """

    def __init__(self, tf_client, analyzer: ExerciseAnalyzer):
        self.tf_client = tf_client
        self.analyzer = analyzer

    async def analyze(
        self,
        video_bytes: bytes,
        exercise_type: str,
        session_id: str = "video-session",
        student_id: str = "video-student",
        academy_id: str = "unknown",
        frame_interval_ms: float = DEFAULT_FRAME_INTERVAL_MS,
    ) -> VideoAnalysisReport:
        """
        Ponto de entrada principal.
        Salva o vídeo em temp file, extrai frames, analisa e monta relatório.
        """
        import cv2  # lazy — só necessário aqui; RepCounter/FrameResult não precisam

        t_total = time.perf_counter()

        try:
            ex_type = ExerciseType(exercise_type.upper())
        except ValueError:
            ex_type = ExerciseType.UNKNOWN

        # Salva bytes em arquivo temporário (cv2 precisa de path)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        frame_results: list[FrameResult] = []
        alert_events: list[AlertEvent] = []
        last_alert_time: dict[str, float] = defaultdict(float)  # error_type → mono time

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise ValueError("Não foi possível abrir o vídeo. Verifique o formato (mp4/mov/avi).")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_video_ms = (cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps) * 1000

        if total_video_ms > MAX_VIDEO_DURATION_S * 1000:
            cap.release()
            raise ValueError(f"Vídeo muito longo. Máximo: {MAX_VIDEO_DURATION_S}s.")

        frame_step = max(1, int((frame_interval_ms / 1000.0) * fps))
        frame_seq = 0
        video_frame_idx = 0

        rep_counter = RepCounter()

        log.info(f"Analisando vídeo: {total_video_ms:.0f}ms | fps={fps:.1f} | step={frame_step}")

        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_idx)
            ret, frame_bgr = cap.read()
            if not ret:
                break

            timestamp_ms = (video_frame_idx / fps) * 1000
            video_frame_idx += frame_step
            frame_seq += 1

            # Converte frame para JPEG
            _, jpeg_bytes = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            jpeg_bytes = jpeg_bytes.tobytes()

            # Detecção de pose
            try:
                landmarks, inference_ms, orientation = self.tf_client.predict(jpeg_bytes)
            except Exception as e:
                log.warning(f"Erro na inferência frame {frame_seq}: {e}")
                landmarks = []
                inference_ms = 0.0
                orientation = None

            # Análise de exercício
            from types import SimpleNamespace
            result = self.analyzer.analyze(SimpleNamespace(
                session_id=session_id,
                student_id=student_id,
                exercise_type=ex_type,
                frame_seq=frame_seq,
                landmarks=landmarks,
            ), orientation=orientation)

            angles_dict = {
                "left_knee":  result.joint_angles.left_knee,
                "right_knee": result.joint_angles.right_knee,
                "back_angle": result.joint_angles.back_angle,
                "left_hip":   result.joint_angles.left_hip,
            }

            frame_result = FrameResult(
                frame_seq=frame_seq,
                timestamp_ms=round(timestamp_ms, 1),
                phase=result.phase.value,
                score=result.score,
                landmark_count=result.landmark_count,
                errors=result.errors,
                has_alert=result.has_alert,
                joint_angles=angles_dict,
            )

            frame_results.append(frame_result)
            rep_counter.feed(frame_result)

            # ── Simulação de notificação ao professor ─────────────────────
            # Mesma lógica do messaging.py: throttle 5s por error_type
            if result.has_alert:
                now_mono = time.monotonic()
                for err in result.errors:
                    if err.risk_level not in (RiskLevel.MEDIUM, RiskLevel.HIGH):
                        continue
                    key = err.error_type.value
                    if now_mono - last_alert_time[key] < THROTTLE_S:
                        log.debug(f"Alerta throttled: {key} @ {timestamp_ms:.0f}ms")
                        continue
                    last_alert_time[key] = now_mono

                    alert_events.append(AlertEvent(
                        timestamp_ms=round(timestamp_ms, 1),
                        frame_seq=frame_seq,
                        error_type=err.error_type.value,
                        risk_level=err.risk_level.value,
                        description=err.description,
                        joint_angle=err.joint_angle,
                        score=result.score,
                        phase=result.phase.value,
                    ))
                    log.info(
                        f"[PROFESSOR NOTIFICADO] {err.risk_level.value} | "
                        f"{err.error_type.value} | {timestamp_ms:.0f}ms | score={result.score}"
                    )

            # Yield para event loop não bloquear (vídeos longos)
            if frame_seq % 20 == 0:
                await asyncio.sleep(0)

        cap.release()
        rep_counter.finish()

        # ── Monta relatório ───────────────────────────────────────────────
        return self._build_report(
            frame_results=frame_results,
            alert_events=alert_events,
            rep_counter=rep_counter,
            exercise_type=exercise_type.upper(),
            total_video_ms=total_video_ms,
            frame_interval_ms=frame_interval_ms,
        )

    def _build_report(
        self,
        frame_results: list[FrameResult],
        alert_events: list[AlertEvent],
        rep_counter: RepCounter,
        exercise_type: str,
        total_video_ms: float,
        frame_interval_ms: float,
    ) -> VideoAnalysisReport:

        if not frame_results:
            return VideoAnalysisReport(
                exercise_type=exercise_type,
                video_duration_ms=total_video_ms,
                total_frames_analyzed=0,
                frames_with_landmarks=0,
                analysis_fps=0,
                avg_score=0, min_score=0, max_score=0,
                score_timeline=[], total_reps=0, reps=[],
                total_alerts_fired=0, error_frequency={},
                top_errors=[], professor_alerts=[],
                phase_distribution={}, avg_score_by_phase={},
                critical_frames=[],
            )

        frames_with_lm = [f for f in frame_results if f.landmark_count > 0]
        valid_scores = [f.score for f in frames_with_lm if f.score > 0]

        # Score timeline
        score_timeline = [
            {"ms": f.timestamp_ms, "score": f.score, "phase": f.phase}
            for f in frame_results
        ]

        # Error frequency
        all_errors = [e.error_type.value for f in frame_results for e in f.errors]
        error_freq = dict(Counter(all_errors).most_common())

        top_errors = [
            {
                "error_type": et,
                "count": cnt,
                "pct_frames": round(cnt / max(len(frame_results), 1) * 100, 1),
            }
            for et, cnt in Counter(all_errors).most_common(5)
        ]

        # Phase distribution
        phase_counts = Counter(f.phase for f in frame_results)
        phase_dist = dict(phase_counts)

        # Avg score by phase
        phase_scores: dict[str, list] = defaultdict(list)
        for f in frame_results:
            if f.score > 0:
                phase_scores[f.phase].append(f.score)
        avg_score_by_phase = {
            ph: round(sum(scores) / len(scores), 1)
            for ph, scores in phase_scores.items()
        }

        # Critical frames (score < 50 or HIGH error)
        critical_frames = [
            {
                "frame_seq": f.frame_seq,
                "timestamp_ms": f.timestamp_ms,
                "score": f.score,
                "phase": f.phase,
                "errors": [
                    {"type": e.error_type.value, "risk": e.risk_level.value, "desc": e.description}
                    for e in f.errors
                ],
            }
            for f in frame_results
            if f.score < 50 or any(e.risk_level == RiskLevel.HIGH for e in f.errors)
        ]

        # Reps
        reps_dicts = [
            {
                "rep_number": r.rep_number,
                "start_ms": r.start_ms,
                "end_ms": r.end_ms,
                "duration_ms": round(r.end_ms - r.start_ms, 1),
                "min_knee_angle": r.min_knee_angle,
                "avg_score": r.avg_score,
                "errors": r.errors_in_rep,
                "risk_level": r.risk_level,
            }
            for r in rep_counter.reps
        ]

        # Professor alerts payload
        professor_alerts = [
            {
                "timestamp_ms": a.timestamp_ms,
                "timestamp_label": _ms_to_label(a.timestamp_ms),
                "frame_seq": a.frame_seq,
                "error_type": a.error_type,
                "risk_level": a.risk_level,
                "description": a.description,
                "joint_angle": a.joint_angle,
                "score": a.score,
                "phase": a.phase,
                "channel": "WebSocket → gym.alert.created → Notification Service",
            }
            for a in alert_events
        ]

        return VideoAnalysisReport(
            exercise_type=exercise_type,
            video_duration_ms=round(total_video_ms, 1),
            total_frames_analyzed=len(frame_results),
            frames_with_landmarks=len(frames_with_lm),
            analysis_fps=round(1000 / frame_interval_ms, 1),
            avg_score=round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0.0,
            min_score=round(min(valid_scores), 1) if valid_scores else 0.0,
            max_score=round(max(valid_scores), 1) if valid_scores else 0.0,
            score_timeline=score_timeline,
            total_reps=len(rep_counter.reps),
            reps=reps_dicts,
            total_alerts_fired=len(alert_events),
            error_frequency=error_freq,
            top_errors=top_errors,
            professor_alerts=professor_alerts,
            phase_distribution=phase_dist,
            avg_score_by_phase=avg_score_by_phase,
            critical_frames=critical_frames[:20],  # máx 20 no relatório
        )


def _ms_to_label(ms: float) -> str:
    """Converte milissegundos em label legível: 0:04.200"""
    s = ms / 1000
    mins = int(s // 60)
    secs = s % 60
    return f"{mins}:{secs:06.3f}"
