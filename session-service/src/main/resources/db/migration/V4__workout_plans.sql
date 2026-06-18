CREATE TABLE IF NOT EXISTS workout_plans (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    academy_id    UUID NOT NULL,
    student_id    UUID NOT NULL,
    professor_id  UUID NOT NULL,
    name          VARCHAR(120) NOT NULL,
    day_of_week   SMALLINT,     -- 1=Mon..7=Sun, NULL=qualquer dia
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON workout_plans (student_id, active);
CREATE INDEX ON workout_plans (academy_id);

CREATE TABLE IF NOT EXISTS workout_plan_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id       UUID NOT NULL REFERENCES workout_plans(id) ON DELETE CASCADE,
    exercise_type VARCHAR(40) NOT NULL,
    sets          SMALLINT NOT NULL DEFAULT 3,
    reps_per_set  SMALLINT NOT NULL DEFAULT 10,
    load_kg       NUMERIC(6,2),
    notes         TEXT,
    order_index   SMALLINT NOT NULL DEFAULT 0
);

CREATE INDEX ON workout_plan_items (plan_id, order_index);
