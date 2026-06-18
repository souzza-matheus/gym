"""
video_cache.py — Cache Redis para resultados de análise de vídeo.
Chave: hash MD5 do vídeo + exercise_type + frame_interval_ms
TTL:  24 horas (86400s)
"""

import hashlib
import json
import logging
import os

import redis.asyncio as redis

log = logging.getLogger(__name__)

_client: redis.Redis | None = None
CACHE_TTL = 86400  # 24h


async def connect():
    global _client
    host     = os.getenv("REDIS_HOST",     "redis")
    port     = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD", "gymvision123")
    try:
        _client = redis.Redis(host=host, port=port, password=password,
                              decode_responses=True, socket_timeout=2)
        await _client.ping()
        log.info("Redis cache conectado: %s:%s", host, port)
    except Exception as e:
        log.warning("Redis indisponível (cache desabilitado): %s", e)
        _client = None


async def disconnect():
    if _client:
        await _client.aclose()


def video_hash(video_bytes: bytes, exercise_type: str, frame_interval_ms: float) -> str:
    digest = hashlib.md5(video_bytes).hexdigest()
    return f"video:{digest}:{exercise_type}:{int(frame_interval_ms)}"


async def get(key: str) -> dict | None:
    if not _client:
        return None
    try:
        raw = await _client.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def set(key: str, value: dict):
    if not _client:
        return
    try:
        await _client.setex(key, CACHE_TTL, json.dumps(value, default=str))
    except Exception:
        pass
