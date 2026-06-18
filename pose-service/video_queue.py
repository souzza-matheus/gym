"""
video_queue.py — Fila assíncrona para processamento de vídeo em background.

Fluxo:
  1. POST /analyze-video → enfileira job, retorna {"job_id": "...", "status": "queued"}
  2. Worker consome a fila, processa, publica resultado no Redis (key: job:{id})
  3. GET  /analyze-video/{job_id} → retorna status + resultado quando pronto
  4. Após análise, publica no WebSocket via messaging (igual ao fluxo síncrono)
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import video_cache as cache

log = logging.getLogger(__name__)

JOB_TTL    = 3600   # resultado fica no Redis por 1 hora
MAX_QUEUE  = 20     # máx jobs em espera simultâneos


@dataclass
class VideoJob:
    job_id:          str
    video_bytes:     bytes
    exercise_type:   str
    session_id:      str
    student_id:      str
    academy_id:      str
    frame_interval:  float
    created_at:      float = field(default_factory=time.monotonic)


_queue: asyncio.Queue[VideoJob] = asyncio.Queue(maxsize=MAX_QUEUE)
_worker_task: asyncio.Task | None = None


async def _save_status(job_id: str, status: str, result: Any = None, error: str | None = None):
    payload = {"job_id": job_id, "status": status}
    if result is not None:
        payload["result"] = result
    if error:
        payload["error"] = error
    await cache.set(f"job:{job_id}", payload)
    # Sobrescreve o TTL para jobs concluídos / com erro
    if status in ("done", "error") and cache._client:
        try:
            await cache._client.expire(f"job:{job_id}", JOB_TTL)
        except Exception:
            pass


async def get_job_status(job_id: str) -> dict | None:
    return await cache.get(f"job:{job_id}")


async def _worker(video_analyzer, messaging_module):
    log.info('{"ts":null,"service":"pose-service","level":"INFO","msg":"video_queue worker iniciado"}')
    while True:
        job: VideoJob = await _queue.get()
        try:
            await _save_status(job.job_id, "processing")
            report = await video_analyzer.analyze(
                video_bytes=job.video_bytes,
                exercise_type=job.exercise_type,
                session_id=job.session_id,
                student_id=job.student_id,
                academy_id=job.academy_id,
                frame_interval_ms=job.frame_interval,
            )
            # Publica alertas no RabbitMQ (igual ao endpoint síncrono)
            for alert in report.professor_alerts:
                asyncio.create_task(messaging_module.publish_alert(
                    session_id=job.session_id, student_id=job.student_id,
                    academy_id=job.academy_id, exercise_type=job.exercise_type,
                    error_type=alert["error_type"], risk_level=alert["risk_level"],
                    description=alert["description"], joint_angle=alert.get("joint_angle"),
                    score=alert["score"], phase=alert["phase"],
                ))
            # Salva resultado
            result_dict = report.__dict__
            await cache.set(f"job:{job.job_id}", {
                "job_id": job.job_id, "status": "done", "result": result_dict
            })
            if cache._client:
                await cache._client.expire(f"job:{job.job_id}", JOB_TTL)
            log.info('{"ts":null,"service":"pose-service","level":"INFO","msg":"job %s concluído"}',
                     job.job_id)
        except Exception as e:
            await _save_status(job.job_id, "error", error=str(e))
            log.error('{"ts":null,"service":"pose-service","level":"ERROR","msg":"job %s falhou: %s"}',
                      job.job_id, e)
        finally:
            _queue.task_done()


def start_worker(video_analyzer, messaging_module):
    global _worker_task
    _worker_task = asyncio.create_task(_worker(video_analyzer, messaging_module))


def stop_worker():
    if _worker_task:
        _worker_task.cancel()


async def enqueue(
    video_bytes: bytes,
    exercise_type: str,
    session_id: str,
    student_id: str,
    academy_id: str,
    frame_interval: float,
) -> str:
    job_id = str(uuid.uuid4())
    job = VideoJob(
        job_id=job_id,
        video_bytes=video_bytes,
        exercise_type=exercise_type,
        session_id=session_id,
        student_id=student_id,
        academy_id=academy_id,
        frame_interval=frame_interval,
    )
    await _save_status(job_id, "queued")
    try:
        _queue.put_nowait(job)
    except asyncio.QueueFull:
        await _save_status(job_id, "error", error="Fila cheia — tente novamente em instantes")
    return job_id
