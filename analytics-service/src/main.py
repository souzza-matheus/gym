"""
analytics-service/src/main.py — GymVision Analytics Service (porta 8086)

Responsabilidades:
  - Consome gym.session.ended do RabbitMQ
  - Persiste resumos no MongoDB (sessions_summary, student_progress, academy_stats)
  - Expõe endpoints de consulta histórica por aluno, sessão e academia
  - Gera relatórios de evolução com tendências semanais
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import aio_pika
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
import json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MONGO_URL     = os.getenv("MONGO_URL",     "mongodb://gymvision:gymvision123@mongodb:27017/gymvision_analytics?authSource=admin")
RABBITMQ_URL  = os.getenv("RABBITMQ_URL",  "amqp://gymvision:gymvision123@rabbitmq:5672/")
PORT          = int(os.getenv("PORT",      "8086"))

QUEUE_SESSION_ENDED = "gym.session.ended"
QUEUE_EXERCISE_RESULT = "gym.exercise.result"

# ── MongoDB client ─────────────────────────────────────────────────────────────
mongo: AsyncIOMotorClient = None
db = None

# ── RabbitMQ ──────────────────────────────────────────────────────────────────
_rabbit_conn = None
_rabbit_channel = None


async def connect_rabbitmq():
    global _rabbit_conn, _rabbit_channel
    try:
        _rabbit_conn    = await aio_pika.connect_robust(RABBITMQ_URL)
        _rabbit_channel = await _rabbit_conn.channel()
        await _rabbit_channel.set_qos(prefetch_count=10)

        # Declara as filas que este serviço consome
        q_ended = await _rabbit_channel.declare_queue(QUEUE_SESSION_ENDED, durable=True)
        q_result = await _rabbit_channel.declare_queue(QUEUE_EXERCISE_RESULT, durable=True)

        await q_ended.consume(on_session_ended)
        await q_result.consume(on_exercise_result)
        log.info("RabbitMQ conectado, consumindo %s e %s", QUEUE_SESSION_ENDED, QUEUE_EXERCISE_RESULT)
    except Exception as e:
        log.error("Erro ao conectar RabbitMQ: %s", e)


async def disconnect_rabbitmq():
    if _rabbit_conn:
        await _rabbit_conn.close()


# ── Event handlers ────────────────────────────────────────────────────────────

async def on_session_ended(message: aio_pika.IncomingMessage):
    """
    Consome gym.session.ended.
    Persiste sessions_summary e atualiza student_progress + academy_stats.
    """
    async with message.process():
        try:
            data = json.loads(message.body)
            await persist_session_summary(data)
            await update_student_progress(data)
            await update_academy_stats(data)
            log.info("Sessão persistida: session_id=%s", data.get("session_id"))
        except Exception as e:
            log.error("Erro ao processar session.ended: %s", e, exc_info=True)


async def on_exercise_result(message: aio_pika.IncomingMessage):
    """
    Consome gym.exercise.result para métricas em tempo real por academia.
    Atualiza contador de frames analisados e alertas disparados.
    """
    async with message.process():
        try:
            data = json.loads(message.body)
            academy_id = data.get("academy_id", "unknown")
            has_alert  = data.get("has_alert", False)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            await db.academy_daily.update_one(
                {"academy_id": academy_id, "date": today},
                {
                    "$inc": {
                        "frames_analyzed": 1,
                        "alerts_fired": 1 if has_alert else 0,
                    },
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                    "$setOnInsert": {"academy_id": academy_id, "date": today},
                },
                upsert=True,
            )
        except Exception as e:
            log.error("Erro ao processar exercise.result: %s", e)


# ── Persistence helpers ────────────────────────────────────────────────────────

async def persist_session_summary(data: dict):
    doc = {
        "session_id":    data.get("session_id"),
        "student_id":    data.get("student_id"),
        "academy_id":    data.get("academy_id"),
        "exercise_type": data.get("exercise_type"),
        "avg_score":     data.get("avg_score", 0),
        "total_reps":    data.get("total_reps", 0),
        "alert_count":   data.get("alert_count", 0),
        "dominant_error":data.get("dominant_error"),
        "duration_ms":   data.get("duration_ms", 0),
        "started_at":    data.get("started_at"),
        "ended_at":      data.get("ended_at"),
        "created_at":    datetime.now(timezone.utc),
    }
    await db.sessions_summary.insert_one(doc)


async def update_student_progress(data: dict):
    student_id = data.get("student_id")
    if not student_id:
        return

    week = datetime.now(timezone.utc).strftime("%Y-W%W")
    avg_score  = data.get("avg_score", 0)
    dom_error  = data.get("dominant_error")

    # Upsert weekly progress — calcula média móvel do score
    existing = await db.student_progress.find_one({"student_id": student_id, "week": week})
    if existing:
        sessions = existing.get("sessions_count", 1)
        new_avg  = (existing.get("avg_score", 0) * sessions + avg_score) / (sessions + 1)
        await db.student_progress.update_one(
            {"student_id": student_id, "week": week},
            {"$set": {"avg_score": round(new_avg, 1), "dominant_error": dom_error},
             "$inc": {"sessions_count": 1}},
        )
    else:
        await db.student_progress.insert_one({
            "student_id":     student_id,
            "academy_id":     data.get("academy_id"),
            "week":           week,
            "avg_score":      avg_score,
            "dominant_error": dom_error,
            "sessions_count": 1,
            "created_at":     datetime.now(timezone.utc),
        })


async def update_academy_stats(data: dict):
    academy_id = data.get("academy_id")
    if not academy_id:
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.academy_stats.update_one(
        {"academy_id": academy_id, "date": today},
        {
            "$inc": {
                "sessions_completed": 1,
                "total_reps":         data.get("total_reps", 0),
                "total_alerts":       data.get("alert_count", 0),
            },
            "$setOnInsert": {"academy_id": academy_id, "date": today},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mongo, db
    log.info("Iniciando Analytics Service...")
    mongo = AsyncIOMotorClient(MONGO_URL)
    db    = mongo.gymvision_analytics

    # Índices
    await db.sessions_summary.create_index([("student_id", 1), ("started_at", -1)])
    await db.sessions_summary.create_index([("academy_id", 1), ("started_at", -1)])
    await db.student_progress.create_index([("student_id", 1), ("week", -1)])
    await db.academy_stats.create_index([("academy_id", 1), ("date", -1)])

    await connect_rabbitmq()
    log.info("Analytics Service pronto.")
    yield
    await disconnect_rabbitmq()
    mongo.close()
    log.info("Analytics Service encerrado.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GymVision — Analytics Service",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    try:
        await mongo.admin.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return {"status": "ok" if mongo_ok else "degraded", "mongodb": mongo_ok}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/analytics/student/{student_id}")
async def student_analytics(
    student_id: str,
    weeks: int = Query(default=8, ge=1, le=52, description="Número de semanas para histórico"),
    exercise_type: Optional[str] = Query(default=None),
):
    """Evolução do aluno: score semanal, erros dominantes e progresso."""
    # Progresso semanal
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    progress_cursor = db.student_progress.find(
        {"student_id": student_id},
        {"_id": 0}
    ).sort("week", -1).limit(weeks)
    progress = await progress_cursor.to_list(length=weeks)

    # Últimas sessões
    filt = {"student_id": student_id}
    if exercise_type:
        filt["exercise_type"] = exercise_type.upper()

    sessions_cursor = db.sessions_summary.find(filt, {"_id": 0}).sort("started_at", -1).limit(20)
    sessions = await sessions_cursor.to_list(length=20)

    # Estatísticas gerais
    pipeline = [
        {"$match": filt},
        {"$group": {
            "_id": None,
            "total_sessions": {"$sum": 1},
            "total_reps":     {"$sum": "$total_reps"},
            "avg_score":      {"$avg": "$avg_score"},
            "best_score":     {"$max": "$avg_score"},
        }},
    ]
    stats_list = await db.sessions_summary.aggregate(pipeline).to_list(1)
    stats = stats_list[0] if stats_list else {}
    stats.pop("_id", None)

    # Erros mais frequentes
    error_pipeline = [
        {"$match": {**filt, "dominant_error": {"$ne": None}}},
        {"$group": {"_id": "$dominant_error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_errors = await db.sessions_summary.aggregate(error_pipeline).to_list(5)

    return {
        "student_id":  student_id,
        "weekly_progress": progress,
        "recent_sessions": sessions,
        "overall_stats":   stats,
        "top_errors":      [{"error": e["_id"], "count": e["count"]} for e in top_errors],
    }


@app.get("/api/v1/analytics/session/{session_id}/report")
async def session_report(session_id: str):
    """Relatório completo de uma sessão encerrada."""
    doc = await db.sessions_summary.find_one({"session_id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, f"Sessão '{session_id}' não encontrada no analytics.")
    return doc


@app.get("/api/v1/analytics/academy/{academy_id}/stats")
async def academy_stats(
    academy_id: str,
    days: int = Query(default=30, ge=1, le=365, description="Janela de dias"),
):
    """Estatísticas da academia: alunos ativos, alertas, top erros."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    # Aggregate daily stats
    pipeline = [
        {"$match": {"academy_id": academy_id, "date": {"$gte": cutoff}}},
        {"$group": {
            "_id": None,
            "total_sessions":  {"$sum": "$sessions_completed"},
            "total_reps":      {"$sum": "$total_reps"},
            "total_alerts":    {"$sum": "$total_alerts"},
            "frames_analyzed": {"$sum": "$frames_analyzed"},
        }},
    ]
    agg = await db.academy_stats.aggregate(pipeline).to_list(1)
    totals = agg[0] if agg else {}
    totals.pop("_id", None)

    # Alunos ativos no período
    active_students = await db.sessions_summary.distinct(
        "student_id",
        {"academy_id": academy_id, "started_at": {"$gte": cutoff}},
    )

    # Top erros da academia
    err_pipeline = [
        {"$match": {"academy_id": academy_id, "dominant_error": {"$ne": None}}},
        {"$group": {"_id": "$dominant_error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_errors = await db.sessions_summary.aggregate(err_pipeline).to_list(5)

    # Score médio por exercício
    ex_pipeline = [
        {"$match": {"academy_id": academy_id}},
        {"$group": {
            "_id":       "$exercise_type",
            "avg_score": {"$avg": "$avg_score"},
            "count":     {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    by_exercise = await db.sessions_summary.aggregate(ex_pipeline).to_list(10)

    return {
        "academy_id":      academy_id,
        "period_days":     days,
        "totals":          totals,
        "active_students": len(active_students),
        "top_errors":      [{"error": e["_id"], "count": e["count"]} for e in top_errors],
        "by_exercise":     [{"exercise": e["_id"], "avg_score": round(e["avg_score"], 1), "sessions": e["count"]} for e in by_exercise],
    }


@app.get("/api/v1/analytics/academy/{academy_id}/leaderboard")
async def academy_leaderboard(
    academy_id: str,
    exercise_type: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Ranking de alunos por score médio."""
    filt = {"academy_id": academy_id}
    if exercise_type:
        filt["exercise_type"] = exercise_type.upper()

    pipeline = [
        {"$match": filt},
        {"$group": {
            "_id":       "$student_id",
            "avg_score": {"$avg": "$avg_score"},
            "sessions":  {"$sum": 1},
            "total_reps":{"$sum": "$total_reps"},
        }},
        {"$sort": {"avg_score": -1}},
        {"$limit": limit},
    ]
    results = await db.sessions_summary.aggregate(pipeline).to_list(limit)
    return {
        "academy_id":  academy_id,
        "leaderboard": [
            {
                "rank":       i + 1,
                "student_id": r["_id"],
                "avg_score":  round(r["avg_score"], 1),
                "sessions":   r["sessions"],
                "total_reps": r["total_reps"],
            }
            for i, r in enumerate(results)
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
