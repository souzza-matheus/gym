-- V2: adiciona invite_code nas academias (código curto para alunos entrarem)
ALTER TABLE academies ADD COLUMN IF NOT EXISTS invite_code VARCHAR(12) UNIQUE;

-- Gera um código único para a academia de demonstração
UPDATE academies SET invite_code = 'GYMVISION01' WHERE id = '00000000-0000-0000-0000-000000000001';

-- Índice para lookup rápido por código
CREATE INDEX IF NOT EXISTS idx_academies_invite_code ON academies(invite_code);
