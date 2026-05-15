# GymVision — Microservices Backend

Plataforma de visão computacional para academias. Analisa exercícios em tempo real
via câmera (app Android) ou upload de vídeo, detecta erros de postura e notifica
o professor via WebSocket em < 500ms.

## Serviços

| Serviço              | Porta | Tecnologia              | Responsabilidade                        |
|----------------------|-------|-------------------------|-----------------------------------------|
| API Gateway          | 8090  | Kong 3.4                | JWT, rate limit, roteamento             |
| User Service         | 8081  | Spring Boot + Kotlin    | Auth, perfis, JWT                       |
| Pose + Analyzer Svc  | 8083  | FastAPI + Python        | MoveNet, ângulos, score, vídeo          |
| Session Service      | 8082  | Spring Boot + Kotlin    | Sessões, reps, histórico                |
| Notification Service | 8085  | NestJS + Node.js        | WebSocket, alertas ao professor         |
| Analytics Service    | 8086  | FastAPI + Python        | Relatórios, evolução, leaderboard       |

## Análise de exercícios — dois modos

### Modo 1: Frame por frame (app Android)
```bash
curl -X POST http://localhost:8090/api/v1/pose/analyze \
  -H "Authorization: Bearer <JWT>" \
  -F "frame=@foto.jpg" \
  -F "exercise_type=SQUAT" \
  -F "session_id=<uuid>"
```

### Modo 2: Upload de vídeo completo
```bash
curl -X POST http://localhost:8090/api/v1/pose/analyze-video \
  -H "Authorization: Bearer <JWT>" \
  -F "video=@agachamento.mp4" \
  -F "exercise_type=SQUAT" \
  -F "frame_interval_ms=200"
```

Ambos os modos usam o mesmo pipeline (MoveNet → AngleCalc → Analyzer),
garantindo comportamento idêntico entre testes e produção.

## Quick Start

```bash
# 1. Copiar variáveis de ambiente
cp .env.example .env

# 2. Subir todos os serviços
docker compose up -d

# 3. Aguardar inicialização (~30s)
docker compose ps

# 4. Login e obter JWT
curl -X POST http://localhost:8090/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"joao@gymvision.com","password":"gymvision123"}'

# 5. Rodar testes unitários (sem dependências externas)
cd pose-service && python3 run_all_tests.py
```

## Analytics

```bash
# Evolução do aluno (últimas 8 semanas)
GET /api/v1/analytics/student/{id}

# Relatório de uma sessão
GET /api/v1/analytics/session/{id}/report

# Estatísticas da academia
GET /api/v1/analytics/academy/{id}/stats

# Ranking de alunos
GET /api/v1/analytics/academy/{id}/leaderboard
```

## TimescaleDB — Séries Temporais

```bash
# Timeline de score frame-a-frame de uma sessão
GET /api/v1/pose/sessions/{id}/timeline

# Estatísticas agregadas da sessão
GET /api/v1/pose/sessions/{id}/stats

# Thresholds de um exercício (configuráveis em tempo real)
GET  /api/v1/pose/rules/SQUAT
PUT  /api/v1/pose/rules/SQUAT/depth_angle_min?threshold=85
```

## Usuários seed

| E-mail                     | Senha        | Role    |
|----------------------------|--------------|---------|
| admin@gymvision.com        | gymvision123 | ADMIN   |
| professor@gymvision.com    | gymvision123 | TEACHER |
| joao@gymvision.com         | gymvision123 | STUDENT |
