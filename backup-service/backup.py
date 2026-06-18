"""
backup-service/backup.py — GymVision Backup Service

Executa diariamente às 03:00 UTC:
  - pg_dump de gymvision_users + gymvision_sessions (postgres:5432)
  - pg_dump de gymvision_analyzer (timescale:5432)
  - Exportação JSON gzipada de gymvision_analytics (mongodb:27017)
  - Upload para MinIO bucket gymvision-backups
  - Remoção de backups com mais de RETENTION_DAYS dias
"""

import gzip
import io
import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pymongo
from apscheduler.schedulers.blocking import BlockingScheduler
from minio import Minio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("backup")

# ── Config ────────────────────────────────────────────────────────────────────

PG_HOST    = os.getenv("PG_HOST",    "postgres")
PG_PORT    = os.getenv("PG_PORT",    "5432")
PG_USER    = os.getenv("PG_USER",    "gymvision")
PG_PASS    = os.getenv("PG_PASS",    "gymvision123")
PG_DBS     = [d.strip() for d in os.getenv("PG_DBS", "gymvision_users,gymvision_sessions").split(",")]

TS_HOST    = os.getenv("TS_HOST",    "timescale")
TS_PORT    = os.getenv("TS_PORT",    "5432")
TS_USER    = os.getenv("TS_USER",    "gymvision")
TS_PASS    = os.getenv("TS_PASS",    "gymvision123")
TS_DBS     = [d.strip() for d in os.getenv("TS_DBS", "gymvision_analyzer").split(",")]

MONGO_URL  = os.getenv("MONGO_URL",  "mongodb://gymvision:gymvision123@mongodb:27017/?authSource=admin")
MONGO_DBS  = [d.strip() for d in os.getenv("MONGO_DBS", "gymvision_analytics").split(",")]

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "gymvision")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "gymvision123")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET",     "gymvision-backups")
RETENTION_DAYS   = int(os.getenv("RETENTION_DAYS", "30"))
RUN_ON_START     = os.getenv("RUN_ON_START", "false").lower() == "true"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _minio_client() -> Minio:
    return Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
                 secret_key=MINIO_SECRET_KEY, secure=False)


def _ensure_bucket(client: Minio):
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)
        log.info("Bucket '%s' criado.", MINIO_BUCKET)


def _upload(client: Minio, name: str, data: bytes):
    buf = io.BytesIO(data)
    client.put_object(MINIO_BUCKET, name, buf, len(data))
    log.info("  ✓ %s (%d KB)", name, len(data) // 1024)


# ── PostgreSQL backup ─────────────────────────────────────────────────────────

def _pg_dump(host: str, port: str, user: str, password: str, dbname: str) -> bytes:
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    result = subprocess.run(
        ["pg_dump", "-h", host, "-p", port, "-U", user, "-Fc", "--no-password", dbname],
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump {dbname} falhou: {result.stderr.decode()}")
    return result.stdout


# ── MongoDB backup ────────────────────────────────────────────────────────────

def _mongo_export(mongo_url: str, dbname: str) -> bytes:
    """Exporta todas as coleções do banco como JSON gzipado."""
    client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=10_000)
    try:
        db = client[dbname]
        export: dict = {}
        for col_name in db.list_collection_names():
            docs = list(db[col_name].find())
            for doc in docs:
                doc["_id"] = str(doc["_id"])
            export[col_name] = docs
        json_bytes = json.dumps(export, default=str, ensure_ascii=False).encode("utf-8")
    finally:
        client.close()

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(json_bytes)
    return buf.getvalue()


# ── Retention cleanup ─────────────────────────────────────────────────────────

def _cleanup(client: Minio, now: datetime):
    cutoff = now - timedelta(days=RETENTION_DAYS)
    removed = 0
    for obj in client.list_objects(MINIO_BUCKET, recursive=True):
        obj_time = obj.last_modified
        if obj_time.tzinfo is None:
            obj_time = obj_time.replace(tzinfo=timezone.utc)
        if obj_time < cutoff:
            client.remove_object(MINIO_BUCKET, obj.object_name)
            removed += 1
    if removed:
        log.info("Limpeza: %d backups com mais de %d dias removidos.", removed, RETENTION_DAYS)


# ── Main job ──────────────────────────────────────────────────────────────────

def run_backup():
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d_%H-%M")
    log.info("=== Iniciando backup: %s ===", date_str)

    errors: list[str] = []
    client = _minio_client()

    try:
        _ensure_bucket(client)
    except Exception as exc:
        log.error("Não foi possível conectar ao MinIO: %s", exc)
        return

    # PostgreSQL
    log.info("PostgreSQL (%s):", PG_HOST)
    for db in PG_DBS:
        try:
            data = _pg_dump(PG_HOST, PG_PORT, PG_USER, PG_PASS, db)
            _upload(client, f"postgres/{date_str}/{db}.dump", data)
        except Exception as exc:
            log.error("  ✗ %s: %s", db, exc)
            errors.append(f"postgres/{db}: {exc}")

    # TimescaleDB
    log.info("TimescaleDB (%s):", TS_HOST)
    for db in TS_DBS:
        try:
            data = _pg_dump(TS_HOST, TS_PORT, TS_USER, TS_PASS, db)
            _upload(client, f"timescale/{date_str}/{db}.dump", data)
        except Exception as exc:
            log.error("  ✗ %s: %s", db, exc)
            errors.append(f"timescale/{db}: {exc}")

    # MongoDB
    log.info("MongoDB (%s):", MONGO_URL.split("@")[-1])
    for db in MONGO_DBS:
        try:
            data = _mongo_export(MONGO_URL, db)
            _upload(client, f"mongodb/{date_str}/{db}.json.gz", data)
        except Exception as exc:
            log.error("  ✗ %s: %s", db, exc)
            errors.append(f"mongodb/{db}: {exc}")

    # Retenção
    try:
        _cleanup(client, now)
    except Exception as exc:
        log.warning("Erro na limpeza de backups antigos: %s", exc)

    if errors:
        log.warning("=== Backup concluído com %d erro(s): %s ===", len(errors), errors)
    else:
        log.info("=== Backup concluído sem erros ===")


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if RUN_ON_START:
        log.info("RUN_ON_START=true — executando backup imediato.")
        run_backup()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_backup, "cron", hour=3, minute=0, id="daily_backup")
    log.info("Agendador iniciado. Próximo backup: 03:00 UTC diariamente.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Backup service encerrado.")
