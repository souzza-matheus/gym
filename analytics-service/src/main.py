"""
analytics-service/src/main.py — GymVision Analytics Service (porta 8086)

Responsabilidades:
  - Consome gym.session.ended do RabbitMQ
  - Persiste resumos no MongoDB (sessions_summary, student_progress, academy_stats)
  - Expõe endpoints de consulta histórica por aluno, sessão e academia
  - Gera relatórios de evolução com tendências semanais
"""

import asyncio
import calendar
import io
import logging
import os
import smtplib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aio_pika
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
import json

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MONGO_URL        = os.getenv("MONGO_URL",        "mongodb://gymvision:gymvision123@mongodb:27017/gymvision_analytics?authSource=admin")
RABBITMQ_URL     = os.getenv("RABBITMQ_URL",     "amqp://gymvision:gymvision123@rabbitmq:5672/")
PORT             = int(os.getenv("PORT",         "8086"))
SMTP_HOST        = os.getenv("SMTP_HOST",        "smtp.mailtrap.io")
SMTP_PORT        = int(os.getenv("SMTP_PORT",    "587"))
SMTP_USER        = os.getenv("SMTP_USER",        "")
SMTP_PASS        = os.getenv("SMTP_PASS",        "")
SMTP_FROM        = os.getenv("SMTP_FROM",        "GymVision <noreply@gymvision.com>")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8081")

QUEUE_SESSION_ENDED = "gym.session.ended"
QUEUE_EXERCISE_RESULT = "gym.exercise.result"

# ── MongoDB client ─────────────────────────────────────────────────────────────
mongo: AsyncIOMotorClient = None
db = None

# ── RabbitMQ ──────────────────────────────────────────────────────────────────
_rabbit_conn = None
_rabbit_channel = None

# ── Scheduler ─────────────────────────────────────────────────────────────────
_scheduler: AsyncIOScheduler = None


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
        "dominant_error": data.get("dominant_error"),
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
    global mongo, db, _scheduler
    log.info("Iniciando Analytics Service...")
    mongo = AsyncIOMotorClient(MONGO_URL)
    db    = mongo.gymvision_analytics

    # Índices
    await db.sessions_summary.create_index([("student_id", 1), ("started_at", -1)])
    await db.sessions_summary.create_index([("academy_id", 1), ("started_at", -1)])
    await db.student_progress.create_index([("student_id", 1), ("week", -1)])
    await db.academy_stats.create_index([("academy_id", 1), ("date", -1)])

    await connect_rabbitmq()

    # Agendador mensal de relatórios PDF (dia 1, 08:00 UTC)
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(send_monthly_reports, "cron", day=1, hour=8, minute=0,
                       id="monthly_pdf_reports", replace_existing=True)
    _scheduler.start()
    log.info("Analytics Service pronto. Agendador de relatórios ativo.")
    yield
    _scheduler.shutdown(wait=False)
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
            "total_reps": {"$sum": "$total_reps"},
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


@app.get("/api/v1/analytics/gamification/{student_id}")
async def student_gamification(student_id: str):
    """
    Retorna pontuação, streak, nível e conquistas do aluno.

    Fórmula de pontos: cada sessão vale avg_score * 1 ponto base.
    Nível = pontos // 500.
    Streak = dias consecutivos com ao menos uma sessão (até hoje).
    Conquistas são desbloqueadas por marcos de sessions/reps/score.
    """
    sessions_cursor = db.sessions_summary.find(
        {"student_id": student_id},
        {"_id": 0, "avg_score": 1, "total_reps": 1, "alert_count": 1, "started_at": 1, "exercise_type": 1},
    ).sort("started_at", -1)
    sessions = await sessions_cursor.to_list(length=500)

    if not sessions:
        return {
            "student_id":        student_id,
            "points":            0,
            "level":             0,
            "next_level_points": 500,
            "streak_days":       0,
            "total_sessions":    0,
            "clean_sessions":    0,
            "total_reps":        0,
            "best_score":        0.0,
            "achievements":      [],
        }

    # ── Pontos totais ─────────────────────────────────────────────────────────
    total_points = sum(int(s.get("avg_score", 0)) for s in sessions)

    # ── Sessões sem alerta (clean sessions) ───────────────────────────────────
    clean_sessions = sum(1 for s in sessions if s.get("alert_count", 0) == 0)

    # ── Total de reps ─────────────────────────────────────────────────────────
    total_reps = sum(s.get("total_reps", 0) for s in sessions)

    # ── Melhor score ──────────────────────────────────────────────────────────
    best_score = max((s.get("avg_score", 0) for s in sessions), default=0)

    # ── Nível ─────────────────────────────────────────────────────────────────
    level = total_points // 500
    next_level_points = (level + 1) * 500

    # ── Streak de dias consecutivos ───────────────────────────────────────────
    session_dates = set()
    for s in sessions:
        raw = s.get("started_at")
        if raw:
            try:
                if isinstance(raw, str):
                    d = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
                else:
                    d = raw.date() if hasattr(raw, "date") else None
                if d:
                    session_dates.add(d)
            except Exception:
                pass

    streak = 0
    check_date = datetime.now(timezone.utc).date()
    while check_date in session_dates:
        streak += 1
        check_date = check_date - timedelta(days=1)

    # ── Conquistas ────────────────────────────────────────────────────────────
    total_sessions = len(sessions)
    achievements = []

    def badge(key, name, description, icon, unlocked):
        if unlocked:
            achievements.append({"key": key, "name": name, "description": description, "icon": icon})

    badge("first_session",  "Primeira Sessão",  "Completou sua primeira sessão",              "🏃", total_sessions >= 1)
    badge("ten_sessions",   "10 Sessões",        "Completou 10 sessões de treino",             "🔥", total_sessions >= 10)
    badge("fifty_sessions", "50 Sessões",        "Atleta dedicado! 50 sessões concluídas",     "💪", total_sessions >= 50)
    badge("clean_form",     "Técnica Perfeita",  "Completou uma sessão sem nenhum alerta",     "✅", clean_sessions >= 1)
    badge("clean_streak",   "Mestre da Forma",   "5 sessões seguidas sem alertas críticos",    "🏆", clean_sessions >= 5)
    badge("rep_100",        "100 Repetições",    "Acumulou 100 repetições no total",           "💯", total_reps >= 100)
    badge("rep_1000",       "1.000 Reps",        "Acumulou 1.000 repetições! Incrível",        "🚀", total_reps >= 1000)
    badge("streak_3",       "Sequência de 3",    "Treinou 3 dias seguidos",                    "📅", streak >= 3)
    badge("streak_7",       "Semana Completa",   "Treinou 7 dias seguidos",                    "🗓️", streak >= 7)
    badge("perfect_score",  "Score Perfeito",    "Obteve 100 pontos em uma sessão",            "⭐", best_score >= 100)
    badge("level_5",        "Nível 5",           "Atingiu o nível 5 — especialista",           "🥈", level >= 5)
    badge("level_10",       "Nível 10",          "Atingiu o nível 10 — elite",                 "🥇", level >= 10)

    return {
        "student_id":        student_id,
        "points":            total_points,
        "level":             level,
        "next_level_points": next_level_points,
        "streak_days":       streak,
        "total_sessions":    total_sessions,
        "clean_sessions":    clean_sessions,
        "total_reps":        total_reps,
        "best_score":        round(best_score, 1),
        "achievements":      achievements,
    }


@app.get("/api/v1/analytics/my/sessions")
async def my_sessions(
    student_id: str = Query(..., description="ID do aluno"),
    exercise_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Histórico de sessões do aluno logado (aceita student_id via query param)."""
    filt: dict = {"student_id": student_id}
    if exercise_type:
        filt["exercise_type"] = exercise_type.upper()
    cursor = db.sessions_summary.find(filt, {"_id": 0}).sort("started_at", -1).limit(limit)
    sessions = await cursor.to_list(length=limit)
    return {"sessions": sessions, "total": len(sessions)}


# ── PDF generation ─────────────────────────────────────────────────────────────

def _build_pdf(student_id: str, month_label: str, sessions: list,
               top_errors: list, overall: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles   = getSampleStyleSheet()
    gv_blue  = colors.HexColor("#3b82f6")
    gv_dark  = colors.HexColor("#111827")
    gv_gray  = colors.HexColor("#6b7280")
    gv_light = colors.HexColor("#f9fafb")
    gv_border = colors.HexColor("#e5e7eb")

    title_style = ParagraphStyle(
        "GVTitle", parent=styles["Title"],
        fontSize=26, textColor=gv_blue, spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        "GVSub", parent=styles["Normal"],
        fontSize=11, textColor=gv_gray, spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "GVSection", parent=styles["Heading2"],
        fontSize=12, textColor=gv_dark, spaceBefore=14, spaceAfter=6,
    )
    small_style = ParagraphStyle(
        "GVSmall", parent=styles["Normal"],
        fontSize=8, textColor=gv_gray, spaceAfter=0,
    )

    story = [
        Paragraph("GymVision", title_style),
        Paragraph(f"Relatório Mensal de Desempenho — {month_label}", sub_style),
        Paragraph(f"Aluno: <font color='#3b82f6'>{student_id}</font>", styles["Normal"]),
        Spacer(1, 0.4 * cm),
        HRFlowable(width="100%", thickness=1, color=gv_blue, spaceAfter=8),
    ]

    # ── Resumo ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Resumo do Período", section_style))
    n_sess  = overall.get("total_sessions", 0)
    n_reps  = overall.get("total_reps", 0)
    avg_sc  = round(overall.get("avg_score", 0.0), 1)
    best_sc = round(overall.get("best_score", 0.0), 1)

    stats_data = [
        ["Sessões", "Repetições", "Score Médio", "Melhor Score"],
        [str(n_sess), str(n_reps), str(avg_sc), str(best_sc)],
    ]
    stats_tbl = Table(stats_data, colWidths=[4.1 * cm] * 4)
    stats_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), gv_blue),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0), 9),
        ("FONTSIZE",     (0, 1), (-1, 1), 16),
        ("FONTNAME",     (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR",    (0, 1), (-1, 1), gv_dark),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [gv_light]),
        ("GRID",         (0, 0), (-1, -1), 0.5, gv_border),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(stats_tbl)

    # ── Sessões recentes ──────────────────────────────────────────────────────
    if sessions:
        story.append(Paragraph("Sessões no Período", section_style))
        sess_data = [["Data", "Exercício", "Reps", "Alertas", "Score"]]
        for s in sessions[:15]:
            raw = s.get("started_at", "")
            try:
                if isinstance(raw, str):
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                else:
                    dt = raw
                date_str = dt.strftime("%d/%m/%Y")
            except Exception:
                date_str = str(raw)[:10]
            ex    = s.get("exercise_type", "").replace("_", " ").title()
            score = round(s.get("avg_score", 0), 1)
            sess_data.append([
                date_str, ex,
                str(s.get("total_reps", 0)),
                str(s.get("alert_count", 0)),
                str(score),
            ])

        col_w = [3 * cm, 5.5 * cm, 2.2 * cm, 2.2 * cm, 3.1 * cm]
        sess_tbl = Table(sess_data, colWidths=col_w)
        sess_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), gv_blue),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 8),
            ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",        (1, 0), (1, -1), "LEFT"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [gv_light, colors.white]),
            ("GRID",         (0, 0), (-1, -1), 0.5, gv_border),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(sess_tbl)

    # ── Erros mais frequentes ─────────────────────────────────────────────────
    if top_errors:
        story.append(Paragraph("Erros Mais Frequentes", section_style))
        err_data = [["Erro", "Ocorrências"]]
        for e in top_errors:
            err_data.append([
                e.get("error", "").replace("_", " ").title(),
                str(e.get("count", 0)),
            ])
        err_tbl = Table(err_data, colWidths=[12.5 * cm, 3.5 * cm])
        err_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.HexColor("#92400e")),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, -1), 9),
            ("ALIGN",        (1, 0), (1, -1), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fffbeb"), colors.white]),
            ("GRID",         (0, 0), (-1, -1), 0.5, gv_border),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(err_tbl)

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=gv_border))
    story.append(Paragraph(
        f"Gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC — GymVision Analytics",
        small_style,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── PDF endpoint ───────────────────────────────────────────────────────────────

@app.get("/api/v1/analytics/student/{student_id}/report/pdf")
async def student_report_pdf(
    student_id: str,
    month: Optional[str] = Query(default=None, description="Período no formato YYYY-MM (padrão: mês atual)"),
):
    """Gera e retorna o relatório PDF mensal do aluno."""
    now = datetime.now(timezone.utc)
    if month:
        try:
            year, mon = map(int, month.split("-"))
            if not (1 <= mon <= 12):
                raise ValueError
        except (ValueError, AttributeError):
            raise HTTPException(400, "Formato de mês inválido. Use YYYY-MM")
    else:
        year, mon = now.year, now.month

    month_label = datetime(year, mon, 1).strftime("%B de %Y")
    first_day   = f"{year}-{mon:02d}-01T00:00:00"
    last_day    = f"{year}-{mon:02d}-{calendar.monthrange(year, mon)[1]:02d}T23:59:59.999"

    filt = {"student_id": student_id, "started_at": {"$gte": first_day, "$lte": last_day}}

    sessions = await db.sessions_summary.find(filt, {"_id": 0}).sort("started_at", -1).to_list(50)

    pipeline = [
        {"$match": filt},
        {"$group": {
            "_id":            None,
            "total_sessions": {"$sum": 1},
            "total_reps":     {"$sum": "$total_reps"},
            "avg_score":      {"$avg": "$avg_score"},
            "best_score":     {"$max": "$avg_score"},
        }},
    ]
    overall_list = await db.sessions_summary.aggregate(pipeline).to_list(1)
    overall      = overall_list[0] if overall_list else {}
    overall.pop("_id", None)

    err_pipeline = [
        {"$match": {**filt, "dominant_error": {"$ne": None}}},
        {"$group": {"_id": "$dominant_error", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    top_errors_raw = await db.sessions_summary.aggregate(err_pipeline).to_list(5)
    top_errors     = [{"error": e["_id"], "count": e["count"]} for e in top_errors_raw]

    pdf_bytes = _build_pdf(student_id, month_label, sessions, top_errors, overall)
    filename  = f"gymvision-{student_id[:8]}-{year}-{mon:02d}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Monthly email job ──────────────────────────────────────────────────────────

async def _get_student_email(student_id: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{USER_SERVICE_URL}/api/v1/users/{student_id}")
            if r.status_code == 200:
                return r.json().get("data", {}).get("email")
    except Exception as exc:
        log.warning("Não foi possível obter e-mail do aluno %s: %s", student_id, exc)
    return None


def _send_pdf_sync(to: str, subject: str, html_body: str, pdf_bytes: bytes, filename: str):
    msg = MIMEMultipart()
    msg["From"]    = SMTP_FROM
    msg["To"]      = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))
    att = MIMEApplication(pdf_bytes, _subtype="pdf")
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.ehlo()
        srv.starttls()
        if SMTP_USER:
            srv.login(SMTP_USER, SMTP_PASS)
        srv.sendmail(SMTP_FROM, [to], msg.as_string())


async def send_monthly_reports():
    """Executa no dia 1 de cada mês: gera e envia relatórios PDF para todos os alunos."""
    now        = datetime.now(timezone.utc)
    prev       = now.replace(day=1) - timedelta(days=1)
    year, mon  = prev.year, prev.month
    first_day  = f"{year}-{mon:02d}-01T00:00:00"
    last_day   = f"{year}-{mon:02d}-{calendar.monthrange(year, mon)[1]:02d}T23:59:59.999"

    student_ids = await db.sessions_summary.distinct(
        "student_id", {"started_at": {"$gte": first_day, "$lte": last_day}}
    )
    month_label = datetime(year, mon, 1).strftime("%B de %Y")
    log.info("Relatórios mensais: %d alunos para %s", len(student_ids), month_label)

    for student_id in student_ids:
        try:
            email = await _get_student_email(student_id)
            if not email:
                log.warning("E-mail não encontrado para %s — pulando", student_id)
                continue

            filt = {"student_id": student_id, "started_at": {"$gte": first_day, "$lte": last_day}}
            sessions       = await db.sessions_summary.find(filt, {"_id": 0}).sort("started_at", -1).to_list(50)
            overall_list   = await db.sessions_summary.aggregate([
                {"$match": filt},
                {"$group": {"_id": None, "total_sessions": {"$sum": 1}, "total_reps": {"$sum": "$total_reps"},
                            "avg_score": {"$avg": "$avg_score"}, "best_score": {"$max": "$avg_score"}}},
            ]).to_list(1)
            overall = overall_list[0] if overall_list else {}
            overall.pop("_id", None)
            top_errors_raw = await db.sessions_summary.aggregate([
                {"$match": {**filt, "dominant_error": {"$ne": None}}},
                {"$group": {"_id": "$dominant_error", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}, {"$limit": 5},
            ]).to_list(5)
            top_errors = [{"error": e["_id"], "count": e["count"]} for e in top_errors_raw]

            pdf_bytes = _build_pdf(student_id, month_label, sessions, top_errors, overall)
            filename  = f"gymvision-{year}-{mon:02d}.pdf"
            subject   = f"GymVision — Relatório de {month_label} pronto!"
            html_body = f"""
            <div style="font-family:sans-serif;max-width:520px;margin:0 auto;
                        background:#f9fafb;padding:24px;border-radius:16px">
              <h2 style="color:#111827;margin-bottom:4px">Seu relatório mensal chegou 📊</h2>
              <p style="color:#6b7280">
                Veja em anexo o seu relatório de desempenho de <strong>{month_label}</strong>.
              </p>
              <div style="background:#fff;border-radius:12px;padding:16px;margin:16px 0;
                          box-shadow:0 1px 3px rgba(0,0,0,.08)">
                <p style="margin:0;color:#374151">
                  <strong>Sessões:</strong> {overall.get('total_sessions', 0)} &nbsp;|&nbsp;
                  <strong>Reps:</strong> {overall.get('total_reps', 0)} &nbsp;|&nbsp;
                  <strong>Score médio:</strong> {round(overall.get('avg_score', 0), 1)}
                </p>
              </div>
              <p style="color:#9ca3af;font-size:12px;text-align:center">
                GymVision · Análise automática de postura
              </p>
            </div>"""

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, _send_pdf_sync, email, subject, html_body, pdf_bytes, filename
            )
            log.info("Relatório enviado para %s (%s)", student_id, email)
        except Exception as exc:
            log.error("Erro ao processar relatório de %s: %s", student_id, exc, exc_info=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
