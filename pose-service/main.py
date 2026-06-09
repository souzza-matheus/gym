"""
main.py — GymVision Pose + Exercise Analyzer Service (porta 8083)

Dois modos de análise (mesmo pipeline, comportamento idêntico):
  1. Frame por frame  — POST /api/v1/pose/analyze
  2. Upload de vídeo  — POST /api/v1/pose/analyze-video

Ambos persistem no TimescaleDB e publicam no RabbitMQ.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import messaging
import timescale_client as tsdb
from config import settings
from exercise_analyzer import ExerciseAnalyzer
from models import (
    ExerciseAnalysis, ExerciseType, HealthResponse,
    PoseAnalysisResponse, MovementPhase, JointAngles,
)
from tf_serving_client import tf_client
from video_analyzer import VideoAnalyzer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_analyzer: ExerciseAnalyzer = ExerciseAnalyzer()
_video_analyzer: VideoAnalyzer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _video_analyzer
    log.info("Iniciando Pose + Analyzer Service v3...")
    tf_client.connect()
    await messaging.connect()
    await tsdb.connect()
    _video_analyzer = VideoAnalyzer(tf_client, _analyzer)
    log.info("Pronto — frame mode + video mode + timescaledb ativos.")
    yield
    await messaging.disconnect()
    await tsdb.disconnect()
    tf_client.close()
    log.info("Serviço encerrado.")


app = FastAPI(
    title="GymVision — Pose + Analyzer Service",
    version="3.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", model_loaded=True,
                          tf_serving_connected=tf_client.is_connected)


@app.get("/api/v1/pose/health")
async def pose_health():
    return {
        "status":      "ok" if tf_client.is_connected else "degraded",
        "tf_serving":  {"connected": tf_client.is_connected, "model": settings.model_name},
        "rabbitmq":    {"connected": messaging.is_connected()},
        "timescaledb": {"connected": tsdb.is_connected()},
        "analyzer":    "enabled",
        "video_mode":  "enabled",
    }


# ── MODO 1: Frame por frame (app Android em tempo real) ───────────────────────

@app.post(
    "/api/v1/pose/analyze",
    response_model=PoseAnalysisResponse,
    summary="Analisa um frame JPEG — endpoint principal do app Android",
)
async def analyze_pose(
    frame:         UploadFile = File(..., description="Frame JPEG (480×640, câmera lateral)"),
    exercise_type: str        = Form(..., description="SQUAT | DEADLIFT | LUNGE"),
    session_id:    str        = Form(default="no-session"),
    student_id:    str        = Form(default="no-student"),
    academy_id:    str        = Form(default="unknown"),
    frame_seq:     int        = Form(default=0),
):
    try:
        ex_type = ExerciseType(exercise_type.upper())
    except ValueError:
        raise HTTPException(400, f"exercise_type inválido: '{exercise_type}'")

    if frame.content_type not in ("image/jpeg","image/png","application/octet-stream"):
        raise HTTPException(415, f"Content-Type inválido: {frame.content_type}")

    frame_bytes = await frame.read()
    if not frame_bytes:
        raise HTTPException(400, "Frame vazio.")
    if len(frame_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Frame muito grande (máx 10 MB).")

    img = cv2.imdecode(np.frombuffer(frame_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(422, "Frame não pôde ser decodificado.")

    frame_h, frame_w = img.shape[:2]

    # 1. MoveNet Thunder via TF Serving gRPC
    try:
        landmarks, inference_ms, orientation = tf_client.predict(frame_bytes)
    except Exception as e:
        raise HTTPException(500, f"Erro na detecção de pose: {e}")

    # 2. Analyzer in-process (< 5ms) — reutiliza orientação já detectada pelo TF client
    result = _analyzer.analyze(SimpleNamespace(
        session_id=session_id, student_id=student_id,
        exercise_type=ex_type, frame_seq=frame_seq, landmarks=landmarks,
    ), orientation=orientation)

    if result.has_alert:
        log.warning("ALERTA session=%s frame=%d %s",
                    session_id, frame_seq,
                    [e.error_type.value for e in result.errors
                     if e.risk_level.value in ("MEDIUM","HIGH")])

    # 3. Background: RabbitMQ + TimescaleDB
    asyncio.create_task(messaging.publish_result(result, academy_id))
    asyncio.create_task(tsdb.persist_frame(
        session_id, student_id, academy_id, exercise_type,
        frame_seq, len(landmarks), inference_ms, frame_w, frame_h))
    asyncio.create_task(tsdb.persist_analysis(
        session_id, student_id, academy_id, exercise_type, frame_seq,
        result.phase.value, result.score, result.has_alert,
        result.errors, result.joint_angles, result.analysis_ms))

    return PoseAnalysisResponse(
        landmarks=landmarks,
        landmark_count=len(landmarks),
        inference_ms=round(inference_ms, 2),
        frame_width=frame_w,
        frame_height=frame_h,
        analysis=ExerciseAnalysis(
            exercise_type=result.exercise_type,
            phase=result.phase,
            score=result.score,
            joint_angles=result.joint_angles,
            errors=result.errors,
            has_alert=result.has_alert,
            analysis_ms=result.analysis_ms,
        ),
    )


# ── MODO 2: Upload de vídeo ───────────────────────────────────────────────────

class VideoAnalysisResponse(BaseModel):
    exercise_type:         str
    video_duration_ms:     float
    total_frames_analyzed: int
    frames_with_landmarks: int
    analysis_fps:          float
    avg_score:             float
    min_score:             float
    max_score:             float
    total_reps:            int
    total_alerts_fired:    int
    top_errors:            list[dict]
    professor_alerts:      list[dict]
    reps:                  list[dict]
    score_timeline:        list[dict]
    phase_distribution:    dict
    avg_score_by_phase:    dict
    critical_frames:       list[dict]


@app.post(
    "/api/v1/pose/analyze-video",
    response_model=VideoAnalysisResponse,
    summary="Analisa um vídeo completo — mesmo pipeline do modo frame",
    description="""
Aceita .mp4 / .mov / .avi e aplica exatamente o mesmo pipeline do modo
frame-a-frame. Ideal para testes sem o app Android.

```bash
curl -X POST http://localhost:8090/api/v1/pose/analyze-video \\
  -H "Authorization: Bearer <JWT>" \\
  -F "video=@agachamento.mp4" \\
  -F "exercise_type=SQUAT" \\
  -F "frame_interval_ms=200"
```

Campos chave no relatório:
- `professor_alerts` — cada alerta com timestamp, tipo, risco e canal
- `score_timeline`   — [{ms, score, phase}] por frame
- `reps`             — detalhes de cada repetição detectada
- `critical_frames`  — frames com score<50 ou erro HIGH
""",
)
async def analyze_video(
    video: UploadFile = File(..., description=".mp4/.mov/.avi (máx 500 MB / 5 min)"),
    exercise_type:     str   = Form(...,  description="SQUAT | DEADLIFT | LUNGE"),
    session_id:        str   = Form(default="video-session"),
    student_id:        str   = Form(default="video-student"),
    academy_id:        str   = Form(default="unknown"),
    frame_interval_ms: float = Form(default=200.0,
        description="Intervalo entre frames em ms (200=5fps, 100=10fps, 33≈30fps)"),
):
    allowed = ("video/mp4","video/quicktime","video/x-msvideo",
               "video/avi","application/octet-stream")
    if video.content_type not in allowed:
        raise HTTPException(415, f"Formato não suportado: {video.content_type}")

    video_bytes = await video.read()
    if not video_bytes:
        raise HTTPException(400, "Arquivo de vídeo vazio.")
    if len(video_bytes) > 500 * 1024 * 1024:
        raise HTTPException(413, "Vídeo muito grande (máx 500 MB).")

    try:
        ex_type = ExerciseType(exercise_type.upper())
    except ValueError:
        raise HTTPException(400, f"exercise_type inválido: '{exercise_type}'")

    if frame_interval_ms < 33:
        raise HTTPException(400, "frame_interval_ms mínimo é 33ms.")

    if _video_analyzer is None:
        raise HTTPException(503, "VideoAnalyzer não inicializado.")

    try:
        report = await _video_analyzer.analyze(
            video_bytes=video_bytes,
            exercise_type=exercise_type,
            session_id=session_id,
            student_id=student_id,
            academy_id=academy_id,
            frame_interval_ms=frame_interval_ms,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        log.error("Erro na análise de vídeo: %s", e, exc_info=True)
        raise HTTPException(500, f"Erro interno na análise: {e}")

    # Publica resumo do vídeo no RabbitMQ
    if report.total_frames_analyzed > 0:
        dummy = SimpleNamespace(
            session_id=session_id, student_id=student_id,
            exercise_type=ex_type,
            frame_seq=report.total_frames_analyzed,
            phase=MovementPhase.STANDING,
            score=report.avg_score,
            joint_angles=JointAngles(),
            errors=[],
            has_alert=report.total_alerts_fired > 0,
            landmark_count=report.frames_with_landmarks,
            analysis_ms=0.0,
        )
        asyncio.create_task(messaging.publish_result(dummy, academy_id))

    return VideoAnalysisResponse(**report.__dict__)


# ── Extras: TimescaleDB queries ───────────────────────────────────────────────

@app.get("/api/v1/pose/sessions/{session_id}/timeline",
         summary="Timeline de score de uma sessão (TimescaleDB)")
async def session_timeline(session_id: str):
    data = await tsdb.get_session_timeline(session_id)
    return {"session_id": session_id, "frames": len(data), "timeline": data}


@app.get("/api/v1/pose/sessions/{session_id}/stats",
         summary="Estatísticas agregadas da sessão (TimescaleDB)")
async def session_stats(session_id: str):
    stats = await tsdb.get_session_stats(session_id)
    return {"session_id": session_id, **stats}


@app.get("/api/v1/pose/rules/{exercise_type}",
         summary="Thresholds de um exercício")
async def exercise_rules(exercise_type: str):
    rules = await tsdb.get_exercise_rules(exercise_type)
    return {"exercise_type": exercise_type.upper(), "rules": rules}


@app.put("/api/v1/pose/rules/{exercise_type}/{rule_name}",
         summary="Atualiza threshold em tempo real (hot-reload)")
async def update_rule(exercise_type: str, rule_name: str, threshold: float):
    ok = await tsdb.update_exercise_rule(exercise_type, rule_name, threshold)
    if not ok:
        raise HTTPException(500, "Falha ao atualizar regra.")
    ex_upper = exercise_type.upper()
    if ex_upper not in _analyzer.thresholds:
        _analyzer.thresholds[ex_upper] = {}
    _analyzer.thresholds[ex_upper][rule_name] = threshold
    return {"exercise_type": ex_upper, "rule_name": rule_name, "threshold": threshold}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
