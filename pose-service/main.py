"""
main.py — GymVision Pose + Exercise Analyzer Service (porta 8083)

Dois modos de análise (mesmo pipeline, comportamento idêntico):
  1. Frame por frame  — POST /api/v1/pose/analyze
  2. Upload de vídeo  — POST /api/v1/pose/analyze-video

Ambos persistem no TimescaleDB e publicam no RabbitMQ.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "service": "pose-service",
            "level":   record.levelname,
            "msg":     record.getMessage(),
            **({"exc": self.formatException(record.exc_info)} if record.exc_info else {}),
        })

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import messaging
import timescale_client as tsdb
import video_cache as cache
import video_queue as vqueue
import video_storage as storage
from config import settings
from ai_exercise_analyzer import ExerciseAnalyzer
from models import (
    ExerciseAnalysis, ExerciseType, HealthResponse,
    PoseAnalysisResponse, MovementPhase, JointAngles,
)
from tf_serving_client import tf_client
from video_analyzer import VideoAnalyzer

_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.root.setLevel(logging.INFO)
logging.root.handlers = [_handler]
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
    await cache.connect()
    storage.connect()
    _video_analyzer = VideoAnalyzer(tf_client, _analyzer)
    vqueue.start_worker(_video_analyzer, messaging)
    log.info("Pronto — frame mode + video mode + timescaledb ativos.")
    yield
    vqueue.stop_worker()
    await messaging.disconnect()
    await tsdb.disconnect()
    await cache.disconnect()
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


# ── Auto-detecção de exercício ────────────────────────────────────────────────

class ExerciseDetectionResponse(BaseModel):
    exercise_type: str
    confidence: float
    reason: str
    landmarks: list
    landmark_count: int


@app.post(
    "/api/v1/pose/detect-exercise",
    response_model=ExerciseDetectionResponse,
    summary="Detecta o tipo de exercício automaticamente a partir de um frame",
)
async def detect_exercise(
    frame:      UploadFile = File(..., description="Frame JPEG da câmera"),
    session_id: str        = Form(default="no-session"),
    student_id: str        = Form(default="no-student"),
):
    if frame.content_type not in ("image/jpeg", "image/png", "application/octet-stream"):
        raise HTTPException(415, f"Content-Type inválido: {frame.content_type}")

    frame_bytes = await frame.read()
    if not frame_bytes:
        raise HTTPException(400, "Frame vazio.")

    try:
        landmarks, inference_ms, orientation = tf_client.predict(frame_bytes)
    except Exception as e:
        raise HTTPException(500, f"Erro na detecção de pose: {e}")

    from ai_exercise_classifier import classify_single
    result = classify_single(landmarks)

    log.info("detect-exercise session=%s result=%s conf=%.2f",
             session_id, result.exercise_type.value, result.confidence)

    return ExerciseDetectionResponse(
        exercise_type=result.exercise_type.value,
        confidence=round(result.confidence, 3),
        reason=result.reason,
        landmarks=[lm.dict() for lm in landmarks],
        landmark_count=len(landmarks),
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

    # Verifica cache Redis antes de processar
    cache_key = cache.video_hash(video_bytes, exercise_type, frame_interval_ms)
    cached = await cache.get(cache_key)
    if cached:
        log.info('{"ts":null,"service":"pose-service","level":"INFO","msg":"cache hit para vídeo %s"}', cache_key[:16])
        return VideoAnalysisResponse(**cached)

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

    # Publica alertas reais e resumo no RabbitMQ
    if report.total_frames_analyzed > 0:
        # 1. Alertas individuais → gym.alert.created → WebSocket do professor
        for alert in report.professor_alerts:
            asyncio.create_task(messaging.publish_alert(
                session_id=session_id,
                student_id=student_id,
                academy_id=academy_id,
                exercise_type=exercise_type,
                error_type=alert["error_type"],
                risk_level=alert["risk_level"],
                description=alert["description"],
                joint_angle=alert.get("joint_angle"),
                score=alert["score"],
                phase=alert["phase"],
            ))

        # 2. Resumo da sessão → gym.exercise.result (score médio, has_alert)
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

    # Salva no cache para reutilização e faz upload para MinIO em background
    await cache.set(cache_key, report.__dict__)
    asyncio.create_task(storage.upload_video(
        video_bytes, session_id, academy_id,
        content_type=video.content_type or "video/mp4",
    ))

    return VideoAnalysisResponse(**report.__dict__)


# ── MODO 2b: Upload de vídeo assíncrono ──────────────────────────────────────

@app.post(
    "/api/v1/pose/analyze-video/async",
    summary="Enfileira análise de vídeo — retorna job_id imediatamente",
)
async def analyze_video_async(
    video:             UploadFile = File(...),
    exercise_type:     str        = Form(...),
    session_id:        str        = Form(default="video-session"),
    student_id:        str        = Form(default="video-student"),
    academy_id:        str        = Form(default="unknown"),
    frame_interval_ms: float      = Form(default=200.0),
):
    allowed = ("video/mp4","video/quicktime","video/x-msvideo",
               "video/avi","application/octet-stream")
    if video.content_type not in allowed:
        raise HTTPException(415, f"Formato não suportado: {video.content_type}")
    video_bytes = await video.read()
    if not video_bytes:
        raise HTTPException(400, "Arquivo vazio.")
    if len(video_bytes) > 500 * 1024 * 1024:
        raise HTTPException(413, "Vídeo muito grande (máx 500 MB).")
    try:
        ExerciseType(exercise_type.upper())
    except ValueError:
        raise HTTPException(400, f"exercise_type inválido: '{exercise_type}'")

    job_id = await vqueue.enqueue(
        video_bytes=video_bytes,
        exercise_type=exercise_type.upper(),
        session_id=session_id,
        student_id=student_id,
        academy_id=academy_id,
        frame_interval=frame_interval_ms,
    )
    return {"job_id": job_id, "status": "queued",
            "poll_url": f"/api/v1/pose/analyze-video/status/{job_id}"}


@app.get(
    "/api/v1/pose/analyze-video/status/{job_id}",
    summary="Consulta status de um job de análise de vídeo assíncrono",
)
async def video_job_status(job_id: str):
    status = await vqueue.get_job_status(job_id)
    if status is None:
        raise HTTPException(404, f"Job '{job_id}' não encontrado ou expirado.")
    return status


# ── Extras: TimescaleDB queries ───────────────────────────────────────────────

@app.get("/api/v1/pose/videos/{academy_id}/{session_id}",
         summary="Gera URL de download do vídeo armazenado no MinIO (válida 7 dias)")
async def video_download_url(academy_id: str, session_id: str):
    if not storage.is_connected():
        raise HTTPException(503, "Storage de vídeos indisponível.")
    import time as _time
    key = f"{academy_id}/{session_id}/{int(_time.time())}.mp4"
    url = storage.presigned_url(key)
    if not url:
        raise HTTPException(404, "Vídeo não encontrado.")
    return {"url": url, "expires_in": "7 dias"}


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
