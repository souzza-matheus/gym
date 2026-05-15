-- V1__create_users_schema.sql
-- GymVision — User Service initial schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Academias ─────────────────────────────────────────────────────────────────
CREATE TABLE academies (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    address     VARCHAR(255),
    plan        VARCHAR(20) NOT NULL DEFAULT 'FREE' CHECK (plan IN ('FREE', 'BASIC', 'PRO')),
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Usuários ──────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    role        VARCHAR(20)  NOT NULL CHECK (role IN ('STUDENT', 'TEACHER', 'ADMIN')),
    academy_id  UUID REFERENCES academies(id) ON DELETE SET NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_academy ON users(academy_id);

-- ── Refresh Tokens ────────────────────────────────────────────────────────────
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- ── Seed: academia e usuários de teste ───────────────────────────────────────
INSERT INTO academies (id, name, address, plan)
VALUES ('00000000-0000-0000-0000-000000000001', 'Academia GymVision Demo', 'Rua Teste, 123', 'PRO');

-- Senha: gymvision123 (bcrypt)
INSERT INTO users (name, email, password, role, academy_id) VALUES
('Admin Demo',    'admin@gymvision.com',    '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWa', 'ADMIN',   '00000000-0000-0000-0000-000000000001'),
('Prof. Carlos',  'professor@gymvision.com','$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWa', 'TEACHER', '00000000-0000-0000-0000-000000000001'),
('João Aluno',    'joao@gymvision.com',     '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWa', 'STUDENT', '00000000-0000-0000-0000-000000000001');
