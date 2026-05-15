-- V1__create_sessions_schema.sql
-- GymVision Session Service

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE sessions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id    UUID NOT NULL,
    academy_id    UUID NOT NULL,
    exercise_type VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
    status        VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    avg_score     DECIMAL(5,2) NOT NULL DEFAULT 0,
    total_reps    INTEGER NOT NULL DEFAULT 0,
    alert_count   INTEGER NOT NULL DEFAULT 0,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at      TIMESTAMPTZ
);

CREATE INDEX idx_sessions_student ON sessions(student_id);
CREATE INDEX idx_sessions_academy ON sessions(academy_id);
CREATE INDEX idx_sessions_status  ON sessions(status);

CREATE TABLE reps (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id   UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    rep_number   INTEGER NOT NULL,
    score        DECIMAL(5,2) NOT NULL,
    phase        VARCHAR(20) NOT NULL,
    errors       JSONB NOT NULL DEFAULT '[]',
    has_alert    BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reps_session ON reps(session_id);

CREATE TABLE alerts_ref (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id   UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    error_type   VARCHAR(50) NOT NULL,
    risk_level   VARCHAR(10) NOT NULL,
    description  TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_session ON alerts_ref(session_id);
