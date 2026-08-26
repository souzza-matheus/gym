-- V5__workout_plan_items_load_kg_double.sql
-- Mesmo problema corrigido em V3: Hibernate mapeia Kotlin Double ->
-- DOUBLE PRECISION (Types#FLOAT/float(53)), mas workout_plan_items.load_kg
-- foi criada como NUMERIC(6,2) (Types#NUMERIC) em V4, causando falha na
-- validação de schema (ddl-auto: validate) e crash-loop do session-service.

ALTER TABLE workout_plan_items ALTER COLUMN load_kg TYPE DOUBLE PRECISION USING load_kg::double precision;
