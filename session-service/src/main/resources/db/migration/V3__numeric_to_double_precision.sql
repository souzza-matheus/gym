-- V3__numeric_to_double_precision.sql
-- Hibernate mapeia Kotlin Double -> DOUBLE PRECISION (Types#FLOAT/float(53)),
-- mas reps.score e sessions.avg_score foram criadas como DECIMAL(5,2)
-- (Types#NUMERIC), causando falha na validação de schema (ddl-auto: validate).

ALTER TABLE reps ALTER COLUMN score TYPE DOUBLE PRECISION USING score::double precision;

ALTER TABLE sessions ALTER COLUMN avg_score DROP DEFAULT;
ALTER TABLE sessions ALTER COLUMN avg_score TYPE DOUBLE PRECISION USING avg_score::double precision;
ALTER TABLE sessions ALTER COLUMN avg_score SET DEFAULT 0;
