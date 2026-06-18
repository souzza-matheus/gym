"""
video_storage.py — Upload de vídeos para MinIO (S3-compatible).
Bucket: gymvision-videos
Chave:  {academy_id}/{session_id}/{timestamp}.mp4
URL pública válida por 7 dias (presigned).
"""

import io
import logging
import os
import time

log = logging.getLogger(__name__)

_client = None
_bucket  = "gymvision-videos"


def connect():
    global _client, _bucket
    endpoint   = os.getenv("MINIO_ENDPOINT",   "minio:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY",  "gymvision")
    secret_key = os.getenv("MINIO_SECRET_KEY",  "gymvision123")
    _bucket    = os.getenv("MINIO_BUCKET",      "gymvision-videos")
    try:
        from minio import Minio
        _client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        if not _client.bucket_exists(_bucket):
            _client.make_bucket(_bucket)
        log.info("MinIO conectado: %s (bucket: %s)", endpoint, _bucket)
    except Exception as e:
        log.warning("MinIO indisponível (storage desabilitado): %s", e)
        _client = None


def is_connected() -> bool:
    return _client is not None


async def upload_video(
    video_bytes: bytes,
    session_id: str,
    academy_id: str,
    content_type: str = "video/mp4",
) -> str | None:
    """Faz upload do vídeo e retorna a object key. Retorna None se MinIO indisponível."""
    if not _client:
        return None
    try:
        ts  = int(time.time())
        key = f"{academy_id}/{session_id}/{ts}.mp4"
        _client.put_object(
            _bucket, key,
            data=io.BytesIO(video_bytes),
            length=len(video_bytes),
            content_type=content_type,
        )
        log.info("Vídeo salvo no MinIO: %s/%s", _bucket, key)
        return key
    except Exception as e:
        log.warning("Falha ao salvar vídeo no MinIO: %s", e)
        return None


def presigned_url(object_key: str, expires_hours: int = 168) -> str | None:
    """Gera URL de download válida por até 7 dias (padrão)."""
    if not _client or not object_key:
        return None
    try:
        from datetime import timedelta
        url = _client.presigned_get_object(
            _bucket, object_key,
            expires=timedelta(hours=expires_hours),
        )
        return url
    except Exception as e:
        log.warning("Falha ao gerar presigned URL: %s", e)
        return None
