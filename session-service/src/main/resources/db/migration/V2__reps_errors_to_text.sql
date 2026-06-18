-- V2__reps_errors_to_text.sql
-- Corrige incompatibilidade de schema: Hibernate mapeia String -> VARCHAR/TEXT,
-- mas a coluna foi criada como JSONB (Types#OTHER), causando falha na
-- validação de schema (ddl-auto: validate) ao iniciar o session-service.

ALTER TABLE reps ALTER COLUMN errors DROP DEFAULT;
ALTER TABLE reps ALTER COLUMN errors TYPE TEXT USING errors::text;
ALTER TABLE reps ALTER COLUMN errors SET DEFAULT '[]';
