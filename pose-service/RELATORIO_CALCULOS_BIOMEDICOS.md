# GymVision — Relatório de Cálculos Biomecânicos e Validação
### Data: 2026-08-26

## Aviso metodológico (leia antes do restante)

O prompt de origem deste relatório foi escrito com base em um **modelo hipotético/
anterior** de `exercise_analyzer.py` e `angle_calculator.py`. O código atual
(versão "v2 — suporte a múltiplos ângulos de câmera", com suavização EMA,
interpolação de landmarks e classificação de severidade de alerta) diverge dele
em vários pontos estruturais — não apenas em valores numéricos. Todas as
divergências foram verificadas **executando o código real** (não por inspeção
visual), via `pose-service/tests/test_exercise_analyzer_extended.py` e scripts
de apoio. Cada divergência é sinalizada explicitamente abaixo, conforme exigido
pelo prompt original ("Não altere exercise_analyzer.py sem antes documentar a
divergência encontrada").

---

## 1. Ângulos calculados vs. implementados (Bloco 1)

### 1.1 Fórmula genérica de ângulo (REF 1 — ✅ Sólido)

`angle_calculator.calculate_angle(a, b, c)` implementa exatamente
θ = arccos((BA·BC)/(|BA||BC|)) em 2D (x,y), com `round(...,2)` e clamp de
`cos_angle` em [-1,1]. Usada para joelho, quadril (hip-hinge), tornozelo e
cotovelo. **Confirma REF 1 (Hamill 2015 + Liao 2021 + Burdack 2024).**

### 1.2 Divergência crítica: `back_angle` NÃO usa a fórmula de 3 pontos

O prompt pede o ângulo de inclinação do tronco como
`calculate_angle(ombro, quadril, joelho)` (3 pontos, vértice no quadril).
**O código real não faz isso.** Em `angle_calculator._angles_lateral()`
(linhas 213-228), `back_angle` é:

```
dy = quadril.y - ombro.y
dx = quadril.x - ombro.x
back_angle = atan2(|dx|, |dy|)     # SÓ 2 pontos: ombro→quadril vs. vertical
```

O joelho não entra nesse cálculo. É este `back_angle` (não o ângulo de
3 pontos) que é comparado a `SQUAT_BACK_ANGLE_MAX`, `DEADLIFT_BACK_ANGLE_MAX` e
`ROW_BACK_ANGLE_MAX` em todo o sistema.

**Consequência prática**: os conjuntos de landmarks sintéticos fornecidos no
prompt (desenhados assumindo a fórmula de 3 pontos) **não produzem os ângulos
esperados** quando processados pela fórmula real. Tabela comparativa:

| Cenário (landmarks do prompt) | Ângulo 3 pontos (fórmula do prompt) | `back_angle` REAL (2 pontos, o que o sistema realmente usa) | Erro disparado? |
|---|---|---|---|
| Squat correto (bottom) | 167.45° | 6.84° | Não (esperado) |
| Squat BACK_NOT_STRAIGHT | 161.76° | **12.53°** | **Não** — landmarks do prompt não violam o threshold real de 45° |
| Deadlift BACK_TOO_CURVED | 159.67° | **14.62°** | **Não** — abaixo do threshold real de 30° |
| Row tronco ereto | 167.68° | 9.46° | N/A (ver 1.4) |

Os testes já existentes em `test_exercise_analyzer.py` (ex.:
`test_back_not_straight_high_risk`, com `back=70.0`) contornam esse problema
construindo `JointAngles(back_angle=...)` diretamente, sem depender de
geometria de landmarks — por isso passam. Mas os conjuntos de landmarks
crus do prompt, se usados literalmente contra o pipeline completo
(`ExerciseAnalyzer.analyze()`), **não reproduziriam os erros descritos**.

### 1.3 Joelho valgo (KNEE_CAVE) — fórmula diverge de "% da largura corporal"

Prompt: `desvio = (x_joelho - x_tornozelo) / (x_ombro_D - x_ombro_E)`.
Código real (`_analyze_squat`, linha 252): `(l_knee.x - l_ankle.x) * 100` —
**pontos percentuais da coordenada normalizada bruta, sem dividir pela
largura dos ombros.** Threshold real: `SQUAT_KNEE_CAVE_THRESHOLD = 2.0`, não
4.0 como o prompt assume a partir de Padua et al. (2009).

Landmarks do cenário KNEE_CAVE_LEFT do prompt: métrica real =
`(0.52-0.47)*100 = 5.00` → **dispara erro** (5.0 > 2.0), risk_level sempre
`MEDIUM` (o código não tem 3 faixas LOW/MEDIUM/HIGH para knee cave — é
binário: dispara ou não, sempre MEDIUM).

⚠️ **ADAPTADO**: o threshold de 2.0 (pontos percentuais de coordenada
normalizada) é uma adaptação operacional do critério qualitativo de Padua et
al. (2009), mas **diverge do threshold de 4% descrito no prompt de origem** —
o valor real implementado é mais sensível (2.0, não 4.0) e usa uma métrica
geometricamente diferente (diferença bruta de coordenada, não normalizada
pela largura do corpo).

### 1.4 Bent-over Row — `TORSO_NOT_PARALLEL` não existe no código

❌ **Divergência estrutural**: `ErrorType.TORSO_NOT_PARALLEL` **não existe**
em `models.py`. `_analyze_bent_over_row()` não calcula ângulo do tronco vs.
horizontal, nem aplica banda de 30°-60°. A remada curvada só verifica:
`BACK_ROUNDED` (mesmo critério/threshold do deadlift-style, `ROW_BACK_ANGLE_MAX=35°`)
e `ROW_INCOMPLETE` (amplitude do cotovelo < 120°). A ressalva ❌ do prompt
("ausência de referência peer-reviewed para thresholds de tronco na remada")
permanece válida, mas o erro específico descrito (`TORSO_NOT_PARALLEL`)
**não está implementado** — é uma lacuna de funcionalidade, não apenas de
referência.

### 1.5 Supino — abertura do cotovelo é medida diferente do prompt

Prompt: `abertura_E/D = |x_ombro - x_cotovelo| / largura_ombros`, por lado,
threshold 20%. Código real (linha 456-468, ramo frontal `fw≥0.5`):
`flare_pct = ((largura_cotovelos - largura_ombros) / largura_ombros) * 100`
— largura total cotovelo-a-cotovelo vs. largura total ombro-a-ombro, não por
lado. Com os landmarks do prompt: `flare_pct = 83.33%` (threshold=20%) →
dispara `ELBOW_FLARE`, mas **sempre com `risk_level=HIGH`** — não existe
banda MEDIUM (20-35%) como o prompt descreve; é binário (dispara em HIGH ou
não dispara).

### Tabela consolidada do Bloco 1

| Exercício | Postura | Articulação/métrica | Valor calculado (fórmula do prompt) | Valor REAL usado pelo sistema | Threshold real | Classificação real |
|---|---|---|---|---|---|---|
| SQUAT | Correto (bottom) | joelho (3pt) | 170.92° | 170.92° (mesma fórmula) | ≥90° BOTTOM | sem erro |
| SQUAT | Correto (bottom) | back_angle | 167.45° (3pt) | **6.84°** (2pt real) | >45°/>63° | sem erro |
| SQUAT | KNEE_CAVE_LEFT | desvio joelho | 50.0% (÷largura ombro) | **5.0 pp** (métrica real, sem ÷ombro) | >2.0 | **dispara, MEDIUM** |
| SQUAT | BACK_NOT_STRAIGHT | back_angle | 161.76° (3pt) | **12.53°** (2pt real) | >45°/>63° | **sem erro** (landmarks do prompt não violam o threshold real) |
| DEADLIFT | BACK_TOO_CURVED | back_angle | 159.67° (3pt) | **14.62°** (2pt real) | >30°/>45° | **sem erro** (idem) |
| BENCH | ELBOW_TOO_WIDE | flare | 41.67%/lado (÷ombro) | **83.33%** (largura total, real) | >20% (só HIGH) | **dispara, HIGH** |
| ROW | TORSO_NOT_PARALLEL | tronco vs horizontal | 167.68°/77.68°(90-x) | **ErrorType não existe no código** | N/A | N/A |

---

## 2. Conformidade dos thresholds com a literatura científica

| Threshold implementado | Valor REAL no código | Referência | Status |
|---|---|---|---|
| SQUAT `DEPTH_INSUFFICIENT` | 90° | Escamilla, 2001 | ✅ Sólido |
| SQUAT `KNEE_CAVE_*` | **2.0** (pontos percentuais, coordenada bruta) | Padua et al., 2009 | ⚠️ Adaptado — "Limiar operacional adaptado do critério qualitativo de joelho valgo de Padua et al. (2009); o valor implementado (2.0) e a métrica (diferença bruta de coordenada normalizada) divergem do valor de 4% descrito na documentação original do projeto." |
| SQUAT `BACK_NOT_STRAIGHT` | 45° (MEDIUM), 63° = 45×1.4 (HIGH) | McGill, 2015 | ⚠️ Adaptado — "Limiar de 45°/63° derivado de McGill (2015); a literatura peer-reviewed (Vigotsky et al., 2021) indica variabilidade individual de 10°-40° mesmo em praticantes com boa técnica, o que pode implicar especificidade reduzida." Nota adicional: apenas 2 faixas (MEDIUM/HIGH) existem no código, não as 4 faixas (OK/LOW/MEDIUM/HIGH) descritas no prompt de origem. |
| SQUAT `KNEE_OVER_TOE_*` | 0.05 | — (não citado nas refs do prompt) | ❌ Fraco — sem referência peer-reviewed específica no código-fonte ou comentários. |
| DEADLIFT `BACK_ROUNDED` | 30° (MEDIUM), 45° = 30×1.5 (HIGH) | McGill + Cholewicki 1991 | ⚠️ Adaptado — mesma ressalva do squat. **Único bloco de thresholds cujas bandas OK/MEDIUM/HIGH batem exatamente com o descrito no prompt de origem.** |
| DEADLIFT `HIPS_TOO_HIGH` | 160° (STANDING) | — | ❌ Fraco |
| LUNGE `DEPTH_INSUFFICIENT` (via ângulo joelho) | banda [85°,100°] | — | ❌ Fraco — sem referência citada; **`LUNGE` não implementa `KNEE_CAVE` nem `FRONT_KNEE_FORWARD`** como o prompt assume — só depth (via banda de ângulo) e back_angle. |
| LUNGE `BACK_NOT_STRAIGHT` | 40°, sempre MEDIUM (sem escalonamento p/ HIGH) | McGill, 2015 (por analogia) | ⚠️ Adaptado |
| BENCH `ELBOW_FLARE` (frontal) | 20% (largura cotovelo vs. ombro, total, não por lado), sempre HIGH | Fees et al., 1998 | ⚠️ Adaptado — "Limiar operacional de 20%, adaptado das recomendações de abdução glenoumeral <45° de Fees et al. (1998); evidência biomecânica recente (Van Grinsven et al., 2024) é mais nuançada. Métrica usa largura total cotovelo-a-cotovelo, não deslocamento por lado." |
| BENCH `ELBOW_FLARE` (lateral) | 80° (ângulo XZ ombro-cotovelo) | Fees et al., 1998 | ⚠️ Adaptado — fórmula geométrica adicional não descrita no prompt (usa profundidade Z do MediaPipe) |
| BENCH `ELBOW_INSUFFICIENT_RANGE` | 70° | — | ❌ Fraco |
| BENCH `WRIST_BENT` | 0.04 (desvio X normalizado) | — | ❌ Fraco |
| ROW `BACK_ROUNDED` | 35° (MEDIUM), 52.5°=35×1.5 (HIGH) | McGill + Cholewicki 1991 (por analogia) | ⚠️ Adaptado |
| ROW `ROW_INCOMPLETE` | 120° (ângulo cotovelo) | — | ❌ Fraco |
| ROW `TORSO_NOT_PARALLEL` | **não implementado** | Sem peer-review (conforme o prompt já reconhecia) | ❌ Fraco / não existe no código |

**Referências novas do prompt de origem a incluir na lista de referências do
TCC** (citadas na fundamentação, mas não verificadas contra código pois não
há artefato correspondente a validar numericamente): Liao et al. (2021),
Vigotsky et al. (2021), Van Grinsven et al. (2024), Cholewicki, McGill e
Norman (1991).

### 2B. Cenários de score (`calculate_score`, verificado por execução real)

Fórmula: score=100; HIGH −25; MEDIUM −15; LOW −5; piso 0 (`max(0, round(score,1))`).
Além disso: se `phase == UNKNOWN` e `not force_assessable`, score = 0 **antes** de
aplicar qualquer penalidade (checado primeiro).

| Cenário | Resultado (executado) |
|---|---|
| 1 — nenhum erro | 100.0 |
| 2 — 1 LOW | 95.0 |
| 3 — 1 MEDIUM | 85.0 |
| 4 — 1 HIGH | 75.0 |
| 5 — 1 HIGH + 1 MEDIUM | 60.0 |
| 6 — reprodução do experimento (`back_angle=70°` → HIGH automaticamente via `_analyze_squat`, + `KNEE_CAVE_RIGHT` MEDIUM injetado) | **60.0** — bate exatamente com o score mínimo relatado no experimento (100−25−15=60) |

### 2C. Detecção de fase (`detect_phase`, verificado por execução real)

| Ângulo joelho | Fase (executado) |
|---|---|
| 175° | STANDING |
| 120° | DESCENDING (sem histórico prévio) |
| 82° | BOTTOM |
| 95° | DESCENDING (sem histórico prévio) |
| 160° | **DESCENDING**, não STANDING — a condição é `> 160.0` estrita; 160° exato cai no ramo `else` (sem `prev_angle`, retorna DESCENDING). Isto é um caso de contorno relevante não mencionado no prompt de origem. |

---

## 3. Consistência dos dados experimentais (Bloco 3)

| Métrica | Valor reportado | Valor calculado | Consistente? |
|---|---|---|---|
| fps de análise | ~6,7 fps (esperado de 1000/150) | 68/11.3 = **6.018 fps** | **N** — diverge do esperado teórico (6.67) em ~10%; duração real do vídeo provavelmente inclui frames descartados ou o intervalo efetivo de captura variou. Não é possível confirmar sem os frames brutos. |
| taxa BACK_NOT_STRAIGHT | 33,8% | 23/68 = 33.82% | **S** |
| taxa KNEE_CAVE_RIGHT | 23,5% | 16/68 = 23.53% | **S** |
| frame do 1º alerta (t=1,8s) | — | 1.8/0.15 = frame **12** | **S** (consistente com interval_ms=150) |
| frame do 2º alerta (t=2,1s) | — | 2.1/0.15 = frame **14** | **S** |
| frames com sobreposição (BACK+KNEE simultâneos) | implícito no score mín=60 | **Indeterminado** a partir dos dados agregados — ver nota abaixo | **Lacuna de dados**, não inconsistência |
| score médio | 88,0 | ver decomposição abaixo | **S** (compatível, com ressalva matemática) |

**Nota sobre sobreposição de erros**: o score médio é **matematicamente
invariante** à distribuição de sobreposição entre os 23 frames BACK e 16
frames KNEE, dado que os totais (23, 16, 68) são fixos — testado
algebricamente para x=0, 5, 10, 16 frames de sobreposição, todos resultam
em score médio = 88.015 (arredonda para 88,0, reportado). Isto ocorre porque
a penalidade é aditiva e linear: distribuir os erros em frames separados ou
concentrá-los no mesmo frame não muda a soma total de penalidades sobre os
68 frames. **Portanto, o valor de 88,0 não prova nem refuta a existência de
sobreposição** — apenas o score mínimo de 60,0 (que exige HIGH+MEDIUM no
mesmo frame) estabelece que houve ao menos 1 frame com ambos os erros
simultâneos.

### 3C. Latência

| Cálculo | Resultado |
|---|---|
| latência de rede implícita = 420−85−5−10 | **320 ms** |
| margem vs. Schmidt & Lee (2000ms) = 2000−420 | **1580 ms (79% de folga)** |
| latência máxima teórica (p95) = 140+5+10+320 | **475 ms** — ainda dentro do limiar de 2000ms (76,25% de folga) |
| throughput pose-service = 1000/85 | **11,76 fps** — suporta os 5 fps enviados pelo app (200ms/frame) sem acumular fila (11,76 > 5) |

### 3D. Cobertura de testes (ANTES da geração do Bloco 4)

⚠️ **Divergência relevante**: o prompt assume 34 testes em 7 classes,
0,13s. **O estado real do repositório já tinha 53 testes em 12 classes** em
`test_exercise_analyzer.py` (mais 30 testes adicionais em
`test_ai_exercise_engine.py` e `test_pose_service.py` — 83 testes no total
da suíte antes deste trabalho). O arquivo evoluiu além do estado assumido
pelo prompt de origem — provavelmente uma versão desatualizada da
documentação em relação ao código. `LUNGE` de fato não tinha nenhuma classe
de teste dedicada (confirmado por grep), apenas uma menção incidental em
`test_lunge_descriptions_clean`.

---

## 4. Testes gerados (Bloco 4)

Arquivo: `pose-service/tests/test_exercise_analyzer_extended.py` — **15 testes
novos**, todos verificados contra o comportamento real do código (não contra
suposições do prompt de origem):

- `TestLungeAnalysis` (3 testes) — cobre o gap real de LUNGE: forma correta,
  profundidade fora da banda [85°,100°] (LOW), tronco >40° (MEDIUM, sem
  escalonamento a HIGH — diferente de squat/deadlift/row).
- `TestBoundaryConditions` (6 testes) — knee cave logo abaixo/acima de 2.0;
  back_angle=63.0 exato (achado: cai em HIGH por imprecisão de ponto
  flutuante de `45.0*1.4=62.99999999999999`); deadlift back=30.0 exato (sem
  erro, operador estritamente `>`).
- `TestCameraOrientationRules` (2 testes) — câmera lateral desabilita knee
  cave; back_angle independe de `frontal_weight`.
- `TestLowVisibilityLandmarks` (1 teste) — **corrige suposição do prompt de
  origem**: `visibility=0.3` NÃO seria filtrado (threshold real é
  `MIN_VISIBILITY=0.2`, comparação `<=`); o teste usa `visibility=0.1`, que
  de fato é filtrado. Resultado real: fase UNKNOWN, score 0.0, sem exceção.
- `TestScoreExtremes` (3 testes) — descoberta: o máximo de erros
  simultâneos que `_analyze_squat` pode gerar num único frame é 6 (com
  `frontal_weight=0.5`, banda onde knee_cave e knee_over_toe ficam ativos ao
  mesmo tempo), totalizando −90 pontos → score mínimo real de **10.0**, não
  0.0, para um frame de SQUAT isolado. O piso de 0.0 só é exercitado
  agregando mais erros do que um frame de SQUAT produz sozinho.

### Execução

1 teste falhou na primeira tentativa por um `NameError` (import faltando de
`LEFT_FOOT_INDEX`/`RIGHT_FOOT_INDEX` no próprio arquivo de teste gerado —
**erro do teste, não do código**, corrigido). Após a correção:

```
pytest tests/ -v --tb=short
======================== 98 passed, 3 warnings in 4.55s ========================
```

**Nenhum bug real foi encontrado em `exercise_analyzer.py` ou
`angle_calculator.py`** durante a geração destes testes — todas as
divergências identificadas foram entre o **prompt de origem e o código**, não
entre o código e seu próprio comportamento esperado. Por isso,
`exercise_analyzer.py` não foi modificado.

**Cobertura**: antes = 83 testes (34 assumidos pelo prompt de origem já
estavam desatualizados); depois = **98 testes** (83 + 15 novos).

---

## 5. Configuração cross-network (Bloco 5)

### Estado encontrado ANTES das alterações

CORS já existia, de forma básica (`allow_origins=["*"]` / `origin: '*'`) em
`pose-service/main.py` e `notification-service/src/main.ts` +
`alert.gateway.ts`. **Kong não tinha nenhum plugin CORS configurado.**
`.env.example` não tinha `CORS_ORIGINS`. Dashboard usava só transporte
`websocket` (sem fallback `polling`, sem reconexão explícita — embora
Socket.IO reconecte por padrão).

### Divergência deliberadamente NÃO aplicada: `ConfigLoader.kt` / `config.json`

O prompt de origem pede um mecanismo de configuração de URL em runtime via
`assets/config.json` + `ConfigLoader.kt`. **Isto não foi implementado.** O
projeto já tem um mecanismo equivalente e funcional: `API_HOST` configurável
via propriedade Gradle (`./gradlew assembleDebug -PapiHost=<IP>`,
`android-app/app/build.gradle.kts:10`, exposto como `BuildConfig.API_HOST`,
consumido em `ApiClient.kt`). Introduzir um segundo mecanismo de
configuração de URL concorrente (runtime, via assets) sem remover o
existente (build-time, via Gradle) criaria duas fontes de verdade
divergentes e risco de regressão em um app já funcional — por isso a
alteração foi **documentada como divergência, não aplicada**. Da mesma
forma, `network_security_config.xml` não foi adicionado: o
`AndroidManifest.xml` já tem `android:usesCleartextTraffic="true"`
globalmente (mais permissivo que a config por domínio sugerida, mas já
resolve o problema de tráfego HTTP em rede local/academia sem exigir
recompilação para testar).

### Alterações aplicadas

| Arquivo | Alteração |
|---|---|
| `pose-service/main.py` | `CORSMiddleware` passa a ler `CORS_ORIGINS` do ambiente (default `*`); adiciona `expose_headers`, `max_age=3600`; `allow_credentials` só é `True` quando origens não são `*` (combinação `origins=*` + `credentials=true` é inválida pela spec CORS) |
| `notification-service/src/main.ts` | `enableCors()` lê `CORS_ORIGINS`, adiciona `credentials` condicional |
| `notification-service/src/gateway/alert.gateway.ts` | `@WebSocketGateway` cors lê `CORS_ORIGINS` do ambiente |
| `api-gateway/kong.yml` | Plugin `cors` global adicionado (cobre todas as rotas de uma vez) — **gap real, não existia nenhum CORS no Kong antes** |
| `docker-compose.yml` | `CORS_ORIGINS: ${CORS_ORIGINS:-*}` adicionado a `pose-service` e `notification-service` |
| `.env.example` | Seção `CORS_ORIGINS` adicionada |
| `dashboard/src/hooks/useAlerts.ts` | Socket.IO client: adiciona fallback `polling`, `reconnectionAttempts`, `reconnectionDelay`, `timeout` |

Verificações realizadas: `main.py` — sintaxe Python válida (`ast.parse`).
Suíte pytest completa roda sem erro após as mudanças (98 passed). **Os
arquivos `.ts` não foram compilados localmente** — não há `node_modules`
instalado neste ambiente para `notification-service` nem `dashboard`; as
edições seguem padrões NestJS/Socket.IO padrão, mas recomenda-se rodar
`npm run build` antes do deploy. Os testes `curl`/WebSocket cross-network
descritos na seção 5G do prompt de origem **não foram executados** — exigem
os containers Docker rodando (`docker compose up`), o que não foi
iniciado nesta sessão; ver recomendações.

---

## 6. Divergências encontradas (resumo)

1. `back_angle` usa fórmula de 2 pontos (ombro-quadril vs. vertical), não a
   fórmula de 3 pontos (ombro-quadril-joelho) que o prompt de origem assume
   para todos os ângulos de tronco — os conjuntos de landmarks sintéticos do
   prompt não reproduzem os erros descritos quando passados pelo pipeline real.
2. Threshold de `KNEE_CAVE` é 2.0 (não 4.0) e usa diferença bruta de
   coordenada normalizada (não dividida pela largura dos ombros).
3. `BENT_OVER_ROW` não implementa `TORSO_NOT_PARALLEL` nem checagem de
   tronco vs. horizontal — só `BACK_ROUNDED` (mesmo padrão do deadlift) e
   `ROW_INCOMPLETE`.
4. `LUNGE` não implementa `KNEE_CAVE` nem `FRONT_KNEE_FORWARD` — só
   `DEPTH_INSUFFICIENT` (banda de ângulo) e `BACK_NOT_STRAIGHT` (sem
   escalonamento para HIGH).
5. `BENCH_PRESS` flare do cotovelo é binário (dispara sempre em HIGH), não
   tem banda MEDIUM/HIGH como descrito; métrica é largura total
   cotovelo-a-cotovelo, não por lado.
6. `SQUAT`/`BACK_NOT_STRAIGHT` tem só 2 faixas de risco (MEDIUM/HIGH), não
   as 4 faixas (OK/LOW_RISK/MEDIUM_RISK/HIGH_RISK) descritas no prompt.
7. Suíte de testes já tinha 83 testes (53 em `test_exercise_analyzer.py`, 12
   classes) antes deste trabalho, não 34 testes/7 classes como assumido.
8. `visibility=0.3` não seria filtrada pelo `MIN_VISIBILITY=0.2` real
   (comparação é `<=`) — o exemplo do prompt de origem para "landmarks
   insuficientes" precisaria de um valor menor (ex. 0.1 ou 0.2) para
   realmente disparar o filtro.
9. Mecanismo de configuração de URL do Android já existe (Gradle
   `-PapiHost`) e não foi duplicado por um `ConfigLoader.kt`/`config.json`
   concorrente, como o prompt de origem sugeria.

## 7. Recomendações

1. **Atualizar a documentação de referência do TCC** (a fonte deste prompt)
   para refletir o código atual — especialmente a fórmula de `back_angle`
   (2 pontos, não 3) e os thresholds reais (`2.0`/`20%`/`45°`/`30°`/`35°`).
   O texto do TCC sobre metodologia deve descrever o que o sistema realmente
   calcula, não uma versão idealizada.
2. Considerar implementar `TORSO_NOT_PARALLEL` para `BENT_OVER_ROW` e
   `KNEE_CAVE`/`FRONT_KNEE_FORWARD` para `LUNGE` como trabalho futuro, se o
   TCC pretende reivindicar cobertura desses erros — atualmente não existem.
3. Adicionar banda MEDIUM/HIGH ao `ELBOW_FLARE` do supino em vez do
   comportamento binário atual, para consistência com os demais exercícios.
4. Rodar os testes `curl`/WebSocket cross-network (seção 5G do prompt de
   origem) com os containers ativos (`docker compose up -d`) antes de
   considerar o Bloco 5 totalmente validado — não executado nesta sessão.
5. Verificar compilação TypeScript (`npm run build` em
   `notification-service` e `dashboard`) antes de deploy — não verificado
   localmente por ausência de `node_modules`.
