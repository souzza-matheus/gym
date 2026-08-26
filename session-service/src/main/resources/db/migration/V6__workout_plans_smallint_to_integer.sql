-- V6__workout_plans_smallint_to_integer.sql
-- Mesma classe de problema corrigida em V3/V5: Hibernate mapeia Kotlin Int ->
-- INTEGER (Types#INTEGER), mas as colunas abaixo foram criadas como SMALLINT
-- (Types#SMALLINT) em V4, causando falha na validação de schema
-- (ddl-auto: validate) e crash-loop do session-service.

ALTER TABLE workout_plans ALTER COLUMN day_of_week TYPE INTEGER USING day_of_week::integer;

ALTER TABLE workout_plan_items ALTER COLUMN sets         DROP DEFAULT;
ALTER TABLE workout_plan_items ALTER COLUMN sets         TYPE INTEGER USING sets::integer;
ALTER TABLE workout_plan_items ALTER COLUMN sets         SET DEFAULT 3;

ALTER TABLE workout_plan_items ALTER COLUMN reps_per_set DROP DEFAULT;
ALTER TABLE workout_plan_items ALTER COLUMN reps_per_set TYPE INTEGER USING reps_per_set::integer;
ALTER TABLE workout_plan_items ALTER COLUMN reps_per_set SET DEFAULT 10;

ALTER TABLE workout_plan_items ALTER COLUMN order_index  DROP DEFAULT;
ALTER TABLE workout_plan_items ALTER COLUMN order_index  TYPE INTEGER USING order_index::integer;
ALTER TABLE workout_plan_items ALTER COLUMN order_index  SET DEFAULT 0;
