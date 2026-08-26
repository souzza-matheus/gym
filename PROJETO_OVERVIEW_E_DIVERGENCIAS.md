# GymVision — Visão Geral do Projeto e Divergências Encontradas

Documento de referência para uso na redação do TCC. Combina (1) uma
descrição completa da arquitetura e dos componentes do sistema e (2) as
divergências encontradas entre a fundamentação científica/documentação de
origem e o comportamento real do código, levantadas em sessão de validação
de 2026-08-26.

---

# PARTE 1 — Visão Geral do Projeto

## 1.1 O que é o GymVision

GymVision é uma plataforma de **visão computacional aplicada à biomecânica
do treinamento de força**: analisa, em tempo real ou por upload de vídeo, a
execução de exercícios de academia captados por câmera (celular do aluno),
estima os ângulos articulares via pose estimation, compara contra regras
biomecânicas por exercício e notifica o professor/personal quando detecta
um erro de postura com risco de lesão — com latência-alvo abaixo de 500ms
entre a captura do frame e a exibição do alerta no dashboard.

O sistema tem três frentes de uso:
- **Aluno** (app Android): grava/transmite o exercício, recebe feedback
  local (score, alertas) e pode treinar offline com sincronização posterior.
- **Professor/personal** (dashboard web): monitora em tempo real os alunos
  da academia (ou remotamente), recebe alertas via WebSocket, acompanha
  relatórios de sessão e evolução histórica.
- **Administração da academia**: gestão de planos de treino, leaderboard/
  gamificação, relatórios agregados.

## 1.2 Arquitetura — visão de alto nível

Arquitetura de **microsserviços poliglota**, orquestrada via
`docker-compose.yml`, com um API Gateway (Kong) como ponto único de entrada
HTTP/WebSocket e comunicação assíncrona entre serviços via RabbitMQ.

```
                         ┌─────────────────────┐
   App Android  ─HTTP──▶ │                     │
   (aluno)       WS◀──── │   API Gateway       │
                         │   (Kong 3.4)        │◀── Dashboard Web (React)
   Personal/           ─▶│   :8090 / :8001     │    (professor, navegador)
   Professor remoto      └─────────┬───────────┘
                                    │  roteia por path
        ┌───────────────┬──────────┼──────────┬──────────────┐
        ▼               ▼          ▼          ▼              ▼
  ┌───────────┐   ┌───────────┐ ┌────────┐ ┌────────────┐ ┌────────────┐
  │User Service│   │Pose+Anlyzr│ │Session │ │Notification│ │ Analytics  │
  │Spring/Kotlin│  │  FastAPI  │ │Service │ │  Service   │ │  Service   │
  │  :8081     │   │  :8083    │ │Spring/ │ │  NestJS    │ │  FastAPI   │
  │ Auth, JWT  │   │  MoveNet  │ │Kotlin  │ │  WebSocket │ │  Relatórios│
  │ Academias  │   │  ângulos  │ │ :8082  │ │  :8085     │ │  :8086     │
  └─────┬──────┘   └─────┬─────┘ └───┬────┘ └─────┬──────┘ └─────┬──────┘
        │                │           │            │              │
        ▼                ▼           ▼            ▼              ▼
   PostgreSQL      TF-Serving    PostgreSQL    RabbitMQ       MongoDB
   (users db)      (MoveNet)    (sessions db)  (event bus)   (summaries)
                   TimescaleDB                                  ▲
                   (séries temp.)                                │
                   Redis (cache)                          consome eventos
                   MinIO (vídeos)                          gym.session.ended
```

Todos os serviços de negócio publicam/consomem eventos via **RabbitMQ**
(fila `gymvision`), o que desacopla a análise de pose (pose-service) do
disparo de alertas (notification-service) e da agregação analítica
(analytics-service) — nenhum desses serviços chama o outro diretamente por
HTTP no caminho crítico de análise.

## 1.3 Serviços — detalhamento

### API Gateway — Kong 3.4 (porta 8090 proxy / 8001 admin)
Modo *DB-less* (config declarativa em `api-gateway/kong.yml`, sem banco
próprio). Responsável por: roteamento por path para cada microsserviço,
rate limiting por rota (ex.: 10/min para upload de vídeo, 300/min para
análise frame-a-frame), `request-size-limiting` (512MB para vídeo) e, desde
esta sessão, CORS global.

### User Service — Spring Boot + Kotlin (porta 8081)
Autenticação (login/refresh/logout via JWT), cadastro de usuários e
academias, controle de papéis (aluno/professor/admin), filtro de
multi-tenancy (`TenantFilter.kt`) para isolar dados por academia. Entidades
principais: `Academy`, `User`, `RefreshToken`. Persiste em PostgreSQL.

### Pose + Analyzer Service — FastAPI + Python (porta 8083)
O núcleo biomecânico do sistema. Dois modos de operação sobre o mesmo
pipeline (garantindo comportamento idêntico entre testes e produção):
- **Frame a frame**: `POST /api/v1/pose/analyze` — usado pelo app Android
  durante a captura ao vivo.
- **Vídeo completo**: `POST /api/v1/pose/analyze-video` — upload de um
  vídeo gravado, processado a uma taxa de amostragem configurável
  (`frame_interval_ms`).

Pipeline interno:
1. **Estimativa de pose**: MoveNet Thunder servido via **TensorFlow
   Serving**, retornando 33 landmarks 3D (compatíveis com o esquema
   BlazePose/MediaPipe).
2. **Detecção de orientação de câmera** (`orientation_detector.py`):
   classifica a cena como LATERAL, FRONTAL ou ANGLED a partir da geometria
   dos landmarks, produzindo um `frontal_weight` (0=lateral puro, 1=frontal
   puro) usado para habilitar/desabilitar regras perspectiva-dependentes.
3. **Cálculo de ângulos articulares** (`angle_calculator.py`): fórmula de
   produto escalar (arccos) entre vetores de segmentos corporais para
   joelho, quadril, tornozelo, cotovelo; `back_angle` (inclinação do
   tronco) calculado separadamente via `atan2` entre ombro e quadril,
   adaptando-se à orientação da câmera (LATERAL/FRONTAL/ANGLED, com blend
   ponderado na faixa intermediária).
4. **Análise por exercício** (`exercise_analyzer.py`): regras específicas
   por exercício (SQUAT, DEADLIFT, LUNGE, BENCH_PRESS, BENT_OVER_ROW) que
   comparam os ângulos/desvios calculados contra thresholds, com suavização
   EMA (média móvel exponencial) para evitar "piscar" de alarme por ruído
   de frame a frame, e interpolação de landmarks ausentes por até 3 frames
   (tolera oclusão momentânea, ex. barra cobrindo o ombro no fundo do
   agachamento).
5. **Score de qualidade**: 100 pontos base, com penalidades por erro
   detectado (HIGH −25, MEDIUM −15, LOW −5), piso em 0.
6. **Persistência e broadcast**: grava a análise em **TimescaleDB**
   (série temporal por sessão/frame), publica evento no **RabbitMQ** para
   o notification-service, cacheia estado de vídeo processado no **Redis**,
   armazena os vídeos originais no **MinIO** (S3-compatible).

Também aloja um pipeline de classificação de exercício por IA (`ai/`,
`ai_exercise_classifier.py`, `tf_serving_client.py`) — conforme registrado
em memória de sessões anteriores, esse caminho de ML foi tentado e
revertido para o motor baseado em regras (avisos gerados pela IA eram
brandos demais); o motor ativo em produção é o `exercise_analyzer.py`
baseado em regras descrito acima.

### Session Service — Spring Boot + Kotlin (porta 8082)
Gerencia sessões de treino, contagem de repetições, histórico e planos de
treino. Entidades: `Session`, `Rep`, `AlertRef` (referência a alertas
disparados durante a sessão), `WorkoutPlan`, `WorkoutPlanItem`. Persiste em
PostgreSQL, consome eventos do RabbitMQ.

### Notification Service — NestJS + Node.js (porta 8085)
Gateway WebSocket (Socket.IO, namespace `/ws`) que distribui alertas em
tempo real. Modelo de salas (rooms):
- `academy:{academyId}` — professor/admin recebem todos os alertas da
  academia.
- `student:{studentId}` — aluno recebe feedback da própria sessão.

Consome os eventos publicados pelo pose-service via RabbitMQ
(`alert.consumer.ts`) e faz o broadcast (`alert.gateway.ts`), medindo e
logando o tempo de dispatch (meta: <500ms desde a publicação no broker).

### Analytics Service — FastAPI + Python (porta 8086)
Consome o evento `gym.session.ended`, persiste resumos em **MongoDB**
(`sessions_summary`, `student_progress`, `academy_stats`), expõe consultas
históricas (evolução do aluno por semana, relatório de sessão,
gamificação/leaderboard da academia) e gera relatórios em PDF
(`reportlab`) com envio por e-mail agendado (`apscheduler`).

### Backup Service
Serviço de apoio para rotinas de backup dos dados (Postgres/Mongo/MinIO) —
sem exposição de porta HTTP, roda como job/daemon interno.

## 1.4 Infraestrutura de dados

| Componente | Uso |
|---|---|
| PostgreSQL | dados relacionais de `user-service` (usuários/academias) e `session-service` (sessões/reps/planos) |
| TimescaleDB | série temporal de análises de pose (ângulos, score, erros por frame) — extensão do Postgres otimizada para dados temporais de alta cardinalidade |
| MongoDB | resumos analíticos agregados (`analytics-service`) |
| Redis | cache (estado de vídeo processado, sessões) |
| RabbitMQ | barramento de eventos assíncronos entre todos os serviços de negócio |
| MinIO | armazenamento de objetos S3-compatible para os vídeos enviados |
| TF Serving | serve o modelo MoveNet Thunder (pose estimation) via gRPC |

## 1.5 App Android (Kotlin, Jetpack Compose)

Estrutura por pacote (`android-app/app/src/main/kotlin/com/gymvision/app/`):

- `api/` — interfaces Retrofit (`ApiInterfaces.kt`: Auth, Pose, Session,
  User, WorkoutPlan, Analytics) e `ApiClient.kt` (configuração HTTP,
  incluindo `API_HOST` configurável por propriedade Gradle —
  `-PapiHost=<IP>` — para funcionar tanto em emulador quanto em celular
  físico em redes diferentes, sem precisar de configuração em runtime).
- `offline/` — suporte a treino sem conexão: `ConnectivityObserver.kt`
  (detecção de conectividade real, não apenas link L2), `LocalFrameStore.kt`
  (persistência local de frames), `OfflinePoseAnalyzer.kt` (análise local
  quando sem rede), `SyncWorker.kt` (sincronização em background quando a
  conexão volta).
- `service/` — `GymWebSocketService.kt` (cliente WebSocket persistente para
  receber feedback em tempo real), `AlertNotificationHelper.kt`
  (notificações push locais).
- `model/` — modelos de domínio compartilhados com as camadas de API/UI.
- `ui/` — telas Compose organizadas por feature: `camera/` (captura e
  overlay de pose em tempo real), `auth/`, `navigation/` (navegação por
  papel — aluno/professor/admin), `notifications/`, `profile/`,
  `sessions/`, `progress/`, `achievements/` (gamificação),
  `manageplans/`/`workoutplan/`, `videotest/` (teste de upload de vídeo),
  `components/`, `theme/`.

## 1.6 Dashboard Web (React + TypeScript + Vite)

- `pages/`: `LoginPage`, `TeacherDashboard` (tela principal de
  monitoramento ao vivo), `StudentsPage`, `StudentProgressPage`,
  `AcademyPage`, `WorkoutPlanPage`, `LeaderboardPage`, `VideoTestPage`.
- `components/`: `AlertCard` (exibição de alerta individual),
  `VideoReportView` (relatório de vídeo processado), `ErrorHeatmap`
  (mapa de calor de erros por região/frequência).
- `hooks/`: `useAlerts` (conexão Socket.IO com o notification-service,
  entra na sala `academy:{id}` como TEACHER, recebe eventos `alert` e
  `analysis` em tempo real), `useVideoAnalysis`.

## 1.7 Fluxo de dados — exemplo ponta a ponta (modo frame a frame)

1. App Android captura frame da câmera → `POST /api/v1/pose/analyze`
   (multipart: frame, exercise_type, session_id, student_id, frame_seq,
   academy_id) via Kong.
2. Kong roteia para `pose-service`, aplicando rate limit e CORS.
3. `pose-service` chama TF Serving (MoveNet) → recebe 33 landmarks.
4. `orientation_detector` classifica a câmera; `angle_calculator` calcula
   os ângulos relevantes; `exercise_analyzer` aplica as regras do exercício
   e calcula o score.
5. Resultado é persistido em TimescaleDB e publicado no RabbitMQ.
6. `notification-service` consome o evento, distribui via Socket.IO para a
   sala `academy:{id}` (dashboard do professor) e `student:{id}` (o
   próprio app do aluno).
7. Dashboard (`useAlerts`) e app Android (`GymWebSocketService`) recebem o
   alerta e atualizam a UI — meta de latência total <500ms.
8. Ao final da sessão, `session-service` fecha a sessão e publica
   `gym.session.ended`; `analytics-service` consome e agrega o resumo em
   MongoDB para consulta posterior (evolução, relatórios, leaderboard).

## 1.8 Decisões de design relevantes para o TCC

- **Pipeline único para os dois modos de análise** (frame-a-frame e
  upload de vídeo) — evita divergência de comportamento entre o que é
  testado e o que roda em produção.
- **Regras por thresholds, não ML, no motor de análise ativo** — uma
  tentativa anterior de motor de IA para classificação de erro foi
  revertida por gerar avisos brandos demais; o sistema em produção usa
  regras biomecânicas explícitas e auditáveis.
- **Consciência de orientação de câmera**: as mesmas regras (ex. joelho
  valgo) só são avaliadas quando a geometria da câmera permite medi-las de
  forma confiável (frontal para valgo/varo, lateral para profundidade
  sagital), evitando falsos positivos/negativos por perspectiva errada.
- **Suavização temporal (EMA) e interpolação de landmarks** — mitigam
  ruído de frame a frame do modelo de pose e oclusão momentânea, sem
  mascarar indefinidamente uma oclusão real e prolongada.
- **Arquitetura orientada a eventos (RabbitMQ)** entre pose-service,
  notification-service e analytics-service — desacopla análise, alerta em
  tempo real e agregação histórica, permitindo que cada serviço escale e
  falhe independentemente.
- **Offline-first no app Android** — sessões continuam sendo analisadas
  localmente sem rede, com sincronização posterior.

## 1.9 Fundamentação científica dos cálculos biomecânicos

Resumo das referências usadas para embasar os cálculos do
`exercise_analyzer.py`/`angle_calculator.py` (ver `RELATORIO_CALCULOS_BIOMEDICOS.md`
em `pose-service/` para a validação numérica completa contra o código):

- **Fórmula de ângulo articular** (produto escalar/arccos, 3 pontos):
  Hamill, Knutzen & Derrick (2015); validação em visão computacional por
  Liao et al. (2021, *Journal of Biomechanics*) e Burdack et al. (2024,
  *Heliyon*). ✅ Base sólida.
- **Joelho valgo (knee cave)**: critério qualitativo de Padua et al.
  (2009, LESS — *The American Journal of Sports Medicine*); threshold
  quantitativo é adaptação operacional não publicada. ⚠️ Adaptado.
- **Profundidade do agachamento (90°)**: Escamilla (2001, *Medicine and
  Science in Sports and Exercise*). ✅ Base sólida.
- **Flexão lombar / tronco**: McGill (2015, livro-texto) +
  Cholewicki, McGill & Norman (1991); thresholds específicos (30°/45°/63°)
  são indicativos, não valores experimentalmente validados — Vigotsky et
  al. (2021) reporta variabilidade individual de 10°-40° mesmo com boa
  técnica. ⚠️ Adaptado.
- **Supino — abdução do ombro/cotovelo**: Fees et al. (1998, *AJSM*);
  evidência biomecânica mais recente e nuançada em Van Grinsven et al.
  (2024, *Frontiers in Physiology*). ⚠️ Adaptado.
- **Remada curvada — ângulo de tronco**: sem referência peer-reviewed
  específica identificada. ❌ Limitação a declarar no TCC.

---

# PARTE 2 — Divergências encontradas (prompt de origem vs. código real)

Confirmadas **executando o código real** (não por inspeção), via scripts de
apoio e `pose-service/tests/test_exercise_analyzer_extended.py`. Nenhuma
delas é um bug do sistema — são desalinhamentos entre uma especificação de
origem (aparentemente escrita para uma versão anterior/hipotética do
código) e o `exercise_analyzer.py`/`angle_calculator.py` atuais.

### 1. `back_angle` usa 2 pontos, não 3
A especificação assumia `ângulo(ombro, quadril, joelho)` (arccos, 3 pontos).
O código real (`angle_calculator._angles_lateral`, linhas 213-228) calcula
`atan2(|quadril.x-ombro.x|, |quadril.y-ombro.y|)` — só 2 pontos
(ombro→quadril vs. vertical); o joelho não entra no cálculo. Consequência:
landmarks sintéticos desenhados para a fórmula de 3 pontos não reproduzem
os erros esperados no pipeline real (ex.: cenário "BACK_NOT_STRAIGHT" do
prompt de origem dava 161.76° pela fórmula de 3 pontos, mas **12.53°** pela
fórmula real — abaixo do threshold de 45°, ou seja, sem erro).

### 2. `KNEE_CAVE` — threshold e métrica diferentes
Especificação: `desvio = (x_joelho - x_tornozelo)/(x_ombro_D - x_ombro_E)`,
threshold 4%. Código real (`_analyze_squat`, linha 252):
`(l_knee.x - l_ankle.x) * 100` — diferença bruta de coordenada normalizada,
sem dividir pela largura dos ombros. Threshold real = **2.0**, não 4.0.
Sempre `MEDIUM` (binário — não há 3 faixas de risco).

### 3. `BENT_OVER_ROW` não tem `TORSO_NOT_PARALLEL`
`ErrorType.TORSO_NOT_PARALLEL` não existe em `models.py`.
`_analyze_bent_over_row()` só verifica `BACK_ROUNDED` (>35° MEDIUM, >52.5°
HIGH) e `ROW_INCOMPLETE` (amplitude do cotovelo <120°) — não há checagem de
tronco vs. horizontal.

### 4. `LUNGE` não tem `KNEE_CAVE` nem `FRONT_KNEE_FORWARD`
`_analyze_lunge()` só verifica `DEPTH_INSUFFICIENT` (banda [85°,100°] no
joelho frontal, sempre LOW) e `BACK_NOT_STRAIGHT` (>40°, sempre MEDIUM, sem
escalonar para HIGH).

### 5. Supino — abertura do cotovelo medida diferente
Especificação: `abertura_E/D = |x_ombro-x_cotovelo|/largura_ombros`, por
lado, banda MEDIUM(20-35%)/HIGH(>35%). Código real (linhas 456-468, câmera
frontal `fw≥0.5`): `((largura_total_cotovelos - largura_ombros)/largura_ombros)*100`
— largura total, não por lado. Threshold 20%, mas **sempre dispara em
HIGH** (sem banda MEDIUM).

### 6. `SQUAT`/`BACK_NOT_STRAIGHT` só tem 2 faixas de risco
Especificação assumia 4 faixas (OK/LOW/MEDIUM/HIGH). Código real: 2 faixas
— MEDIUM (45°-63°), HIGH (>63°, onde 63=45×1.4).

### 7. Suíte de testes já estava muito além do assumido
Especificação assumia 34 testes/7 classes/0.13s. Estado real **antes**
deste trabalho: 53 testes em 12 classes só em `test_exercise_analyzer.py`
(83 testes na suíte completa do pose-service). `LUNGE` de fato não tinha
classe de teste dedicada — esse gap específico estava correto.

### 8. `MIN_VISIBILITY` real é 0.2, não o assumido
Especificação assumia que `visibility=0.3` seria filtrada como "baixa".
Código real (`_get()` em `angle_calculator.py`): filtra quando
`visibility <= MIN_VISIBILITY` e `MIN_VISIBILITY=0.2` — logo 0.3 **não**
seria filtrada. É preciso ≤0.2 para exercitar esse caminho.

### 9. `detect_phase(160.0)` não é STANDING
Threshold é `>160.0` estrito; 160° exato cai no ramo `else` (sem
`prev_angle` → DESCENDING), não STANDING.

### 10. Score mínimo real de um frame de SQUAT é 10.0, não 0.0
Máximo de erros simultâneos que `_analyze_squat` pode gerar num único frame
(com `frontal_weight=0.5`, faixa em que `knee_cave` e `knee_over_toe`
ficam ativos ao mesmo tempo): 6 erros, −90 pontos → score mínimo real de
**10.0** para um frame isolado de SQUAT. O piso de 0.0 em
`calculate_score()` existe e funciona, mas exige mais erros do que um
único frame de SQUAT produz sozinho.

### 11. Mecanismo de configuração de URL do Android já existe
A especificação pedia um `ConfigLoader.kt` + `assets/config.json` para
configurar a URL do backend em runtime. O projeto já tem mecanismo
equivalente e funcional: `API_HOST` via propriedade Gradle
(`-PapiHost=<IP>`, `build.gradle.kts:10`, exposto como
`BuildConfig.API_HOST`, consumido em `ApiClient.kt`). Não foi duplicado —
duas fontes de verdade concorrentes (build-time vs. runtime) criariam risco
de regressão.

### 12. Kong não tinha CORS configurado (gap real, não da especificação)
Diferente dos itens acima, este era um gap real corretamente identificado:
`api-gateway/kong.yml` não tinha nenhum plugin `cors` antes deste trabalho
— foi adicionado (plugin global, cobre todas as rotas).

## 2.1 O que foi feito a partir dessas divergências

- **Nenhuma lógica de negócio foi alterada** em `exercise_analyzer.py` ou
  `angle_calculator.py` — as divergências são entre a especificação de
  origem e o código, não bugs no código em si.
- **15 testes novos** adicionados (`test_exercise_analyzer_extended.py`)
  cobrindo os gaps reais identificados (LUNGE sem testes dedicados,
  condições de contorno, orientação de câmera, visibilidade baixa,
  extremos de score) — suíte completa: 83 → 98 testes, todos passando.
- **CORS cross-network** implementado de ponta a ponta: `pose-service`
  (`CORSMiddleware` configurável via `CORS_ORIGINS`), `notification-service`
  (HTTP + gateway Socket.IO), Kong (plugin global — gap real corrigido),
  `docker-compose.yml`/`.env.example` (variável propagada), dashboard
  (`useAlerts`: fallback `polling` + reconexão explícita).
- Documentos de apoio gerados: `pose-service/RELATORIO_CALCULOS_BIOMEDICOS.md`
  (validação numérica completa dos Blocos 1-3) e
  `pose-service/DIVERGENCIAS_PROMPT_VS_CODIGO.md` (este mesmo conteúdo da
  Parte 2, como referência isolada).

## 2.2 Recomendações para o TCC

1. Descrever no texto metodológico o que o sistema **realmente** calcula
   (fórmula de 2 pontos para `back_angle`, thresholds reais 2.0/20%/45°/
   30°/35°), não uma versão idealizada — isso é defensável e citável, só
   precisa estar alinhado ao código.
2. Declarar explicitamente as ressalvas ⚠️/❌ da fundamentação científica
   (thresholds adaptados operacionalmente, ausência de peer-review para
   remada curvada) — fortalece a seção de limitações do trabalho.
3. Se o TCC pretende reivindicar cobertura de `TORSO_NOT_PARALLEL`
   (remada) ou `KNEE_CAVE`/`FRONT_KNEE_FORWARD` (avanço/lunge), esses
   precisam ser implementados antes — atualmente não existem no código.
4. Citar a suíte de testes real (98 testes) e a cobertura por exercício ao
   descrever a estratégia de validação do sistema.
