"""
timescale_client.py — GymVision Pose Service
Persiste frames analisados e resultados no TimescaleDB (hypertables).

Tabelas:
  pose_frames       — cada frame recebido com landmarks raw
  analysis_results  — resultado do analyzer por frame (score, erros, fase)
  exercise_rules    — thresholds configuráveis por exercício (lidos em cache)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import asyncpg

log = logging.getLogger(__name__)

TIMESCALE_URL = os.getenv(
    "TIMESCALE_URL",
    "postgresql://gymvision:gymvision123@timescale:5432/gymvision_analyzer"
)

_pool: Optional[asyncpg.Pool] = None


async def connect() -> None:
    global _pool
    try:
        _pool = await asyncpg.create_pool(TIMESCALE_URL, min_size=2, max_size=10)
        await _ensure_schema()
        log.info("TimescaleDB conectado: %s", TIMESCALE_URL)
    except Exception as e:
        log.warning("TimescaleDB indisponível (modo degradado): %s", e)
        _pool = None


async def disconnect() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def is_connected() -> bool:
    return _pool is not None


async def _ensure_schema() -> None:
    """Cria as tabelas e hypertables se não existirem."""
    ddl = """
    -- Extensão TimescaleDB
    CREATE EXTENSION IF NOT EXISTS timescaledb;

    -- Frames recebidos (hypertable particionada por tempo)
    CREATE TABLE IF NOT EXISTS pose_frames (
        time          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        session_id    TEXT        NOT NULL,
        student_id    TEXT        NOT NULL,
        academy_id    TEXT        NOT NULL DEFAULT 'unknown',
        exercise_type TEXT        NOT NULL,
        frame_seq     INTEGER     NOT NULL,
        landmark_count INTEGER    NOT NULL DEFAULT 0,
        inference_ms  FLOAT       NOT NULL DEFAULT 0,
        frame_width   INTEGER,
        frame_height  INTEGER
    );
    SELECT create_hypertable('pose_frames', 'time', if_not_exists => TRUE);
    CREATE INDEX IF NOT EXISTS idx_pose_frames_session ON pose_frames (session_id, time DESC);

    -- Resultados do analyzer por frame
    CREATE TABLE IF NOT EXISTS analysis_results (
        time          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        session_id    TEXT        NOT NULL,
        student_id    TEXT        NOT NULL,
        academy_id    TEXT        NOT NULL DEFAULT 'unknown',
        exercise_type TEXT        NOT NULL,
        frame_seq     INTEGER     NOT NULL,
        phase         TEXT        NOT NULL,
        score         FLOAT       NOT NULL DEFAULT 0,
        has_alert     BOOLEAN     NOT NULL DEFAULT FALSE,
        errors        JSONB       NOT NULL DEFAULT '[]',
        joint_angles  JSONB       NOT NULL DEFAULT '{}',
        analysis_ms   FLOAT       NOT NULL DEFAULT 0
    );
    SELECT create_hypertable('analysis_results', 'time', if_not_exists => TRUE);
    CREATE INDEX IF NOT EXISTS idx_analysis_session ON analysis_results (session_id, time DESC);
    CREATE INDEX IF NOT EXISTS idx_analysis_alerts  ON analysis_results (session_id, has_alert, time DESC);

    -- Regras de exercício configuráveis (tabela normal, não hypertable)
    CREATE TABLE IF NOT EXISTS exercise_rules (
        exercise_type TEXT    NOT NULL,
        rule_name     TEXT    NOT NULL,
        threshold     FLOAT   NOT NULL,
        weight        FLOAT   NOT NULL DEFAULT 1.0,
        description   TEXT,
        updated_at    TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (exercise_type, rule_name)
    );
    -- Seed com valores padrão
    INSERT INTO exercise_rules (exercise_type, rule_name, threshold, weight, description)
    VALUES
      ('SQUAT',    'depth_angle_min',       90.0, 1.0, 'Angulo minimo do joelho no fundo'),
      ('SQUAT',    'knee_cave_threshold',   15.0, 1.0, 'Desvio lateral joelho pct'),
      ('SQUAT',    'back_angle_max',        45.0, 1.0, 'Angulo maximo do tronco'),
      ('SQUAT',    'knee_over_toe_max',      0.05,1.0, 'Joelho alem do pe pct'),
      ('DEADLIFT', 'back_angle_max',        30.0, 1.0, 'Angulo maximo lombar'),
      ('DEADLIFT', 'hip_angle_standing',   160.0, 1.0, 'Angulo quadril posicao em pe'),
      ('LUNGE',    'knee_front_min',        85.0, 1.0, 'Angulo minimo joelho dianteiro'),
      ('LUNGE',    'knee_front_max',       100.0, 1.0, 'Angulo maximo joelho dianteiro'),
      ('LUNGE',    'back_angle_max',        40.0, 1.0, 'Angulo maximo do tronco')
    ON CONFLICT DO NOTHING;
    """
    async with _pool.acquire() as conn:
        await conn.execute(ddl)
    log.info("Schema TimescaleDB verificado/criado.")


async def persist_frame(
    session_id: str,
    student_id: str,
    academy_id: str,
    exercise_type: str,
    frame_seq: int,
    landmark_count: int,
    inference_ms: float,
    frame_width: int = 0,
    frame_height: int = 0,
) -> None:
    """Persiste metadados do frame recebido (não salva a imagem)."""
    if not _pool:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO pose_frames
                   (session_id, student_id, academy_id, exercise_type, frame_seq,
                    landmark_count, inference_ms, frame_width, frame_height)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                session_id, student_id, academy_id, exercise_type, frame_seq,
                landmark_count, inference_ms, frame_width, frame_height,
            )
    except Exception as e:
        log.warning("Erro ao persistir frame: %s", e)


async def persist_analysis(
    session_id: str,
    student_id: str,
    academy_id: str,
    exercise_type: str,
    frame_seq: int,
    phase: str,
    score: float,
    has_alert: bool,
    errors: list,
    joint_angles: dict,
    analysis_ms: float,
) -> None:
    """Persiste resultado do analyzer para este frame."""
    if not _pool:
        return
    try:
        errors_json  = json.dumps([
            {"type": e.error_type.value, "risk": e.risk_level.value, "desc": e.description}
            for e in errors
        ])
        angles_json  = json.dumps({
            k: v for k, v in {
                "left_knee":  getattr(joint_angles, "left_knee",  None),
                "right_knee": getattr(joint_angles, "right_knee", None),
                "back_angle": getattr(joint_angles, "back_angle", None),
                "left_hip":   getattr(joint_angles, "left_hip",   None),
            }.items() if v is not None
        })
        async with _pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO analysis_results
                   (session_id, student_id, academy_id, exercise_type, frame_seq,
                    phase, score, has_alert, errors, joint_angles, analysis_ms)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11)""",
                session_id, student_id, academy_id, exercise_type, frame_seq,
                phase, score, has_alert, errors_json, angles_json, analysis_ms,
            )
    except Exception as e:
        log.warning("Erro ao persistir analysis: %s", e)


async def get_session_timeline(session_id: str) -> list[dict]:
    """Retorna timeline de score por frame de uma sessão."""
    if not _pool:
        return []
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT time, frame_seq, phase, score, has_alert, errors
                   FROM analysis_results
                   WHERE session_id = $1
                   ORDER BY time ASC""",
                session_id,
            )
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("Erro ao buscar timeline: %s", e)
        return []


async def get_session_stats(session_id: str) -> dict:
    """Estatísticas agregadas de uma sessão a partir das séries temporais."""
    if not _pool:
        return {}
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT
                     COUNT(*)            AS total_frames,
                     AVG(score)          AS avg_score,
                     MIN(score)          AS min_score,
                     MAX(score)          AS max_score,
                     SUM(CASE WHEN has_alert THEN 1 ELSE 0 END) AS alert_frames,
                     MIN(time)           AS started_at,
                     MAX(time)           AS ended_at
                   FROM analysis_results
                   WHERE session_id = $1""",
                session_id,
            )
        return dict(row) if row else {}
    except Exception as e:
        log.warning("Erro ao buscar stats: %s", e)
        return {}


async def get_exercise_rules(exercise_type: str) -> dict:
    """Lê thresholds do banco (sobrescreve defaults em memória)."""
    if not _pool:
        return {}
    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT rule_name, threshold FROM exercise_rules WHERE exercise_type = $1",
                exercise_type.upper(),
            )
        return {r["rule_name"]: r["threshold"] for r in rows}
    except Exception as e:
        log.warning("Erro ao buscar exercise_rules: %s", e)
        return {}


async def update_exercise_rule(exercise_type: str, rule_name: str, threshold: float) -> bool:
    """Atualiza um threshold via API (hot-reload sem reiniciar o serviço)."""
    if not _pool:
        return False
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """UPDATE exercise_rules SET threshold=$3, updated_at=NOW()
                   WHERE exercise_type=$1 AND rule_name=$2""",
                exercise_type.upper(), rule_name, threshold,
            )
        return True
    except Exception as e:
        log.warning("Erro ao atualizar rule: %s", e)
        return False
