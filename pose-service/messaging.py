"""
messaging.py — GymVision Pose Service
Publica eventos no RabbitMQ após cada análise.

Eventos publicados:
  gym.exercise.result  — todo frame analisado (score, fase, erros)
  gym.alert.created    — erros MEDIUM/HIGH com throttle 5s por (session+error_type)
  gym.session.ended    — resumo quando analyze-video termina (para Analytics)
"""

import asyncio
import json
import logging
import time
from collections import defaultdict

import aio_pika

from config import settings

log = logging.getLogger(__name__)

_connection = None
_channel    = None
_throttle: dict[str, float] = defaultdict(float)
THROTTLE_S  = 5.0
EXCHANGE    = "gymvision"

QUEUE_RESULT  = "gym.exercise.result"
QUEUE_ALERT   = "gym.alert.created"
QUEUE_ENDED   = "gym.session.ended"


async def connect():
    global _connection, _channel
    try:
        url = (
            f"amqp://{settings.rabbitmq_user}:{settings.rabbitmq_pass}"
            f"@{settings.rabbitmq_host}:{settings.rabbitmq_port}/"
        )
        _connection = await aio_pika.connect_robust(url)
        _channel    = await _connection.channel()

        # Declara o exchange topic e as filas
        exchange = await _channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        for q_name in (QUEUE_RESULT, QUEUE_ALERT, QUEUE_ENDED):
            q = await _channel.declare_queue(q_name, durable=True)
            await q.bind(exchange, routing_key=q_name)

        log.info("RabbitMQ conectado: %s", url)
    except Exception as e:
        log.warning("RabbitMQ indisponível (modo degradado): %s", e)
        _connection = None
        _channel    = None


async def disconnect():
    global _connection
    if _connection:
        await _connection.close()


def is_connected() -> bool:
    return _channel is not None


async def _publish(routing_key: str, payload: dict):
    if not _channel:
        return
    try:
        exchange = await _channel.get_exchange(EXCHANGE)
        envelope = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "data": payload,
        }
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(envelope, default=str).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
    except Exception as e:
        log.warning("Falha ao publicar %s: %s", routing_key, e)


async def publish_result(result, academy_id: str = "unknown"):
    """Publica gym.exercise.result (sempre) e gym.alert.created (throttled)."""
    payload_result = {
        "session_id":    result.session_id,
        "student_id":    result.student_id,
        "academy_id":    academy_id,
        "exercise_type": result.exercise_type.value,
        "frame_seq":     result.frame_seq,
        "phase":         result.phase.value,
        "score":         result.score,
        "has_alert":     result.has_alert,
        "errors": [
            {
                "error_type":  e.error_type.value,
                "risk_level":  e.risk_level.value,
                "description": e.description,
            }
            for e in result.errors
        ],
        "landmark_count": result.landmark_count,
        "analysis_ms":    result.analysis_ms,
    }
    await _publish(QUEUE_RESULT, payload_result)

    # Alertas: throttle 5s por (session_id + error_type)
    if result.has_alert:
        now = time.monotonic()
        for err in result.errors:
            if err.risk_level.value not in ("MEDIUM", "HIGH"):
                continue
            key = f"{result.session_id}:{err.error_type.value}"
            if now - _throttle[key] < THROTTLE_S:
                continue
            _throttle[key] = now

            await _publish(QUEUE_ALERT, {
                "session_id":  result.session_id,
                "student_id":  result.student_id,
                "academy_id":  academy_id,
                "error_type":  err.error_type.value,
                "risk_level":  err.risk_level.value,
                "description": err.description,
                "joint_angle": err.joint_angle,
                "score":       result.score,
                "phase":       result.phase.value,
            })


async def publish_session_ended(
    session_id: str,
    student_id: str,
    academy_id: str,
    exercise_type: str,
    avg_score: float,
    total_reps: int,
    alert_count: int,
    dominant_error: str | None,
    duration_ms: float,
    started_at: str,
    ended_at: str,
):
    """Publica gym.session.ended para o Analytics Service."""
    await _publish(QUEUE_ENDED, {
        "session_id":     session_id,
        "student_id":     student_id,
        "academy_id":     academy_id,
        "exercise_type":  exercise_type,
        "avg_score":      avg_score,
        "total_reps":     total_reps,
        "alert_count":    alert_count,
        "dominant_error": dominant_error,
        "duration_ms":    duration_ms,
        "started_at":     started_at,
        "ended_at":       ended_at,
    })
