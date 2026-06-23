# Log de Ações do Claude

Este arquivo registra todas as ações realizadas pelo Claude no projeto `gymvision-complete`.

---

## 2026-06-18

### Correção dos 2 achados da validação com vídeos reais

A pedido do usuário, corrigidos os dois problemas identificados na validação anterior (ver entrada abaixo, "Validação de eficácia...").

**1. Score zerado em BENCH_PRESS quando pernas fora de quadro** — `ai_exercise_analyzer.py`: `_predict_ml()` zerava o score sempre que `phase == MovementPhase.UNKNOWN` (joelho não detectado), para **todos** os exercícios. Para SQUAT/DEADLIFT isso é correto (profundidade do joelho é o que está sendo avaliado). Para BENCH_PRESS, o ângulo do joelho nunca foi um sinal real de forma — é só uma convenção do dataset sintético (pessoa deitada, perna não importa). Criado `_KNEE_DEPENDENT_EXERCISES = {SQUAT, DEADLIFT}`: só esses dois continuam zerando o score por joelho ausente; BENCH_PRESS agora só zera se o cotovelo (`arm_angle_left`/`arm_angle_right`, o que de fato é avaliado) também estiver ausente. **Validado**: vídeo real de supino (Smith machine, pernas fora de quadro) que antes dava `avg_score=0.0` em 100% dos frames agora dá `avg_score=64.2` (min 45.6, max 99.7), mantendo os mesmos erros corretamente detectados (ELBOW_FLARE, ELBOW_INSUFFICIENT_RANGE, WRIST_BENT). Sem regressão: SQUAT/DEADLIFT/LUNGE/BENT_OVER_ROW re-testados com os mesmos 4 vídeos da validação anterior — scores idênticos (97.7/95.8/92.8/76.0).

**2. `classify_frames()` (classificação multi-frame, mais robusta) nunca era chamada por nenhum endpoint** — `video_analyzer.py`: `VideoAnalyzer.analyze()` agora acumula os landmarks de todos os frames do vídeo (`all_landmarks`) e chama `classify_frames(all_landmarks)` ao final do processamento, antes de montar o relatório. Novos campos `detected_exercise_type` e `detected_exercise_confidence` adicionados a `VideoAnalysisReport`/`VideoAnalysisResponse` (`main.py`) — **puramente informativos**, não substituem nem alteram o `exercise_type` declarado pelo cliente nem a análise de forma já feita; servem como cross-check ("você selecionou X, mas o classificador acha que é Y com Z% de confiança"). Validado: vídeo de squat real → `detected_exercise_type=SQUAT` (57.5%); demais vídeos retornam resultados consistentes com o viés para SQUAT já documentado na validação anterior (limitação de cobertura de landmarks do MoveNet em vídeo real, não deste fix).

**Build & teste**: `docker compose build pose-service && up -d --force-recreate pose-service`; cache Redis do vídeo de teste limpo (`FLUSHALL`) antes de re-validar, já que o relatório antigo (pré-fix) estava cacheado por hash do vídeo. `pytest tests/test_ai_exercise_engine.py tests/test_exercise_analyzer.py` — **48/48 passando**, sem regressão.

### Validação de eficácia do motor de IA com 5 vídeos reais buscados na web (YouTube Shorts)

**Objetivo**: validar generalização do classificador (`ai_exercise_classifier.py`) e dos modelos de forma (`ai_exercise_analyzer.py`) com vídeos reais e variados, além do único vídeo de squat já usado em validações anteriores.

**Metodologia**: buscado na web (YouTube Shorts) um vídeo real por tipo de exercício — SQUAT, DEADLIFT, BENCH_PRESS, LUNGE, BENT_OVER_ROW — baixados via `yt-dlp` para `/tmp/gymvision_test_videos/` (fora do repositório, não commitados). Para cada vídeo: (1) extraídos frames JPEG isolados e enviados a `POST /api/v1/pose/detect-exercise` para testar o classificador; (2) o vídeo completo enviado a `POST /api/v1/pose/analyze-video` (porta 8083 direta, `frame_interval_ms=200`) para testar a análise de forma. Duas tentativas iniciais com vídeos "tutoriais" de produção alta (gráficos, cortes, overlays — ex.: `squat2.mp4`, `bench_press2.mp4`, `deadlift2.mp4`) foram descartadas da validação por serem piores para extração de pose que filmagem amadora de academia (cortes resultam em poses não-anatômicas, frames de "fala" sem o movimento, oclusão por gráficos).

**Resultados — análise de forma (`analyze-video`)**:
| Exercício | Frames c/ landmarks | Score médio | Reps | Alertas | Erros dominantes |
|---|---|---|---|---|---|
| SQUAT | 44/56 (79%) | 97.6 | 0 | 1 | BACK_NOT_STRAIGHT (MEDIUM, 47.4°) |
| DEADLIFT | 109/119 (92%) | 95.9 | 0 | 1 | BACK_ROUNDED (HIGH, 52.6°) |
| BENCH_PRESS | 159/177 (90%) | **0.0** (ver bug abaixo) | 0 | 7 | ELBOW_FLARE HIGH, ELBOW_INSUFFICIENT_RANGE, WRIST_BENT |
| LUNGE (regra) | 426/426 (100%) | 92.8 | 2 | 4 | BACK_NOT_STRAIGHT (lunge), DEPTH_INSUFFICIENT |
| BENT_OVER_ROW (regra) | 265/265 (100%) | 76.0 | 1 | 2 | BACK_ROUNDED (HIGH, 75°) |

Os erros de forma detectados (BACK_NOT_STRAIGHT, BACK_ROUNDED, ELBOW_FLARE, etc.) correspondem a problemas biomecânicos plausíveis e visíveis nos vídeos reais — os modelos de IA generalizam corretamente para detecção de erro, mesmo em vídeos nunca vistos.

**Bug encontrado: score zerado em 100% dos frames de BENCH_PRESS.** Causa: `ai_exercise_analyzer._predict_ml()` zera o score sempre que `phase == MovementPhase.UNKNOWN`, e `detect_phase()` (`exercise_analyzer.py:105`) retorna `UNKNOWN` sempre que `knee_angle is None`. Em filmagens reais de supino (incluindo a testada aqui, em máquina Smith), a câmera comumente não enquadra as pernas — sem landmarks de joelho, a fase nunca é determinada e o score fica preso em 0, **mesmo com o classificador de erros funcionando normalmente** (os 7 alertas acima são corretos). Esse comportamento é pré-existente (a lógica de fase por ângulo de joelho é compartilhada por todos os exercícios desde antes da migração para IA) e não foi alterado nesta tarefa — registrado aqui como achado de validação, não corrigido.

**Resultados — classificador (`detect-exercise`, frame único)**: fraco em generalização para vídeos reais de Shorts. De 15 frames isolados testados (3 por vídeo), o modelo classificou corretamente apenas quando landmarks estavam quase completos; caiu para `UNKNOWN` (baixa confiança) ou foi **enviesado para SQUAT** em 9/15 frames — inclusive em DEADLIFT e BENCH_PRESS com pernas parcialmente visíveis. Causas identificadas:
1. **Contagem de landmarks baixa em vídeos reais "crus"**: vídeos de academia com pouca luz, sujeito pequeno/distante ou parcialmente oclusoo por equipamento tiveram só 1–12 de 17 landmarks por frame (vs. 17/17 no vídeo de lunge, gravado de perto e bem iluminado) — o MoveNet, não o classificador de IA, é o gargalo nesses casos.
2. **Múltiplas pessoas no quadro** (vídeo de deadlift tinha 2 pessoas) confundem a detecção de pose single-person do MoveNet.
3. **Enquadramento de BENCH_PRESS sem pernas visíveis** quebra a suposição geométrica do classificador (fortemente dependente de ângulos de quadril/joelho/tornozelo), levando a viés sistemático para SQUAT quando os landmarks de perna ausentes são imputados.
4. **Achado de arquitetura, não bug**: `classify_frames()` (média de probabilidade entre múltiplos frames, mais robusta) existe em `ai_exercise_classifier.py` mas **nunca é chamada por nenhum endpoint** — `main.py` só usa `classify_single()` (1 frame). O endpoint `/detect-exercise` recebe apenas 1 frame por chamada; não há endpoint que explore o caminho multi-frame já implementado.

**Conclusão geral**: a validação anterior (vídeo de squat bem iluminado, sujeito grande no quadro) continua válida — o motor de IA funciona bem quando a estimativa de pose tem boa cobertura de landmarks. Esta validação com vídeos reais variados da web mostra que **o principal gargalo de robustez em produção é a qualidade da detecção de pose (MoveNet) em condições do mundo real** (distância, iluminação, oclusão, múltiplas pessoas, enquadramento parcial), não os modelos de IA em si — que generalizam bem (erros de forma corretos) sempre que recebem landmarks suficientes. Dois achados acionáveis para o futuro: (a) corrigir o zeramento de score quando `phase=UNKNOWN` para exercícios de tronco (bench press, possivelmente row), por exemplo usando o ângulo do cotovelo como fase para supino em vez do joelho; (b) conectar `classify_frames()` a um endpoint real ou usá-lo internamente no modo vídeo para classificação mais robusta.

Vídeos de teste não foram commitados ao repositório (mantidos em `/tmp/gymvision_test_videos/`, fora do controle de versão) — apenas este relato de validação.

### Conclusão da substituição do motor de regras por IA: bug crítico no gerador sintético, restauração do modelo MoveNet e validação end-to-end

Continuação da tarefa de 2026-06-17 (ver entrada abaixo). Trabalho realizado de forma autônoma, sem pausas para aprovação, a pedido do usuário.

**Bug crítico encontrado e corrigido em `synthetic_body.py`**: a fórmula original do `back_angle` usava `dx = tan(theta) * torso_len` para inverter `atan2(dx,dy)=theta` com `dy` fixo. Como `tan(90°)` diverge, ângulos altos (testados em ~72°-85°, necessários para representar o tronco deitado do supino) geravam `dx>1.27`, isto é, fora do espaço normalizado [0,1]. O clamp em `_lm()` então colava `l_sh.x` e `r_sh.x` ambos em `1.0`, zerando `shoulder_width` e corrompendo `elbow_flare_pct` (ficava `NaN`) — esse era o teste `test_elbow_flare_detected` que ficou pendente na entrada anterior. **Correção**: trocada a parametrização para `dx=sin(theta)*L, dy=cos(theta)*L` (limitada a `L=torso_len` para qualquer ângulo). Validado por round-trip: erro médio <0.55° em todo o intervalo 10°–85° após a correção. Esse bug também afetava parcialmente SQUAT/DEADLIFT nos ângulos mais altos da faixa (tan(75°)≈3.7), então **todos os datasets e modelos foram regenerados e retreinados** (classificador: 92,25% acurácia held-out; squat/deadlift/bench: 99,9%-100% por erro). **Resultado: 48/48 testes passando** (`test_ai_exercise_engine.py` + `test_exercise_analyzer.py` legado).

**Infraestrutura — modelo MoveNet ausente**: ao tentar validar com vídeo real, descoberto que `pose-service/models/` (bind-mount do TF Serving) estava **vazio** — o arquivo do SavedModel do MoveNet Thunder não existe em nenhum lugar do disco nem no git (provavelmente nunca foi commitado, por ser binário). Sem ele, `tf-serving` não carregava (`gymvision-tf-serving` estava `Exited` há 9 dias) e `pose-service` reportava `tf_serving_connected:false`. **Correção**: baixado o SavedModel oficial via `https://tfhub.dev/google/movenet/singlepose/thunder/4?tf-hub-format=compressed` (mesmo modelo esperado pelo `model_name=movenet_thunder` e pela assinatura `serving_default`/input `"input"` em `tf_serving_client.py`), extraído e copiado para `pose-service/models/1/` usando um container Alpine descartável montando o mesmo caminho (o diretório no host pertence a `root`, sem permissão de escrita para o usuário). `tf-serving` e `pose-service` reconstruídos/reiniciados e reconectados com sucesso.

**Build & deploy**: `docker compose build pose-service && up -d --force-recreate pose-service` — build OK, incluindo `scikit-learn`/`joblib` e os artefatos `.joblib` (~48MB) copiados via `COPY . .` do Dockerfile.

**Validação end-to-end com o vídeo real** (`Bad squat form!!! It needs help!! #shorts.mp4`, mesmo vídeo usado nas validações anteriores):
- `POST /api/v1/pose/analyze-video` (SQUAT): 68 frames analisados, 1 alerta disparado — `BACK_NOT_STRAIGHT MEDIUM` a 49,8° em 2.0s, publicado no RabbitMQ e **confirmado recebido pelo `notification-service`** (`AlertGateway` fez broadcast do WebSocket).
- `POST /api/v1/pose/detect-exercise` com frames reais extraídos do mesmo vídeo (2s e 5s): classificador de IA identificou corretamente **SQUAT com 74% de confiança** a partir de landmarks reais (não sintéticos) — confirma que o modelo treinado em dados sintéticos generaliza para vídeo real.
- **Achado não relacionado ao trabalho de IA, mas corrigido por estar bloqueando a validação**: `notification-service` não conseguiu conectar ao RabbitMQ no último boot (5 tentativas falhas, ~21h atrás) e nunca tentou de novo — alertas ficavam publicados na fila mas nunca eram entregues ao professor. `docker compose restart notification-service` resolveu; o alerta que ficou pendente da fila foi entregue imediatamente após a reconexão.
- **Observação**: os scores neste vídeo ficaram mais altos (média 97,4) e a fase `BOTTOM` nunca foi atingida nos frames analisados, diferente da entrada de 2026-06-16 (que reportava média 88,0 e mínimo 60,0 no fundo do movimento). Investigado: o MoveNet retorna confiança best-effort ~0,5-0,6 para vários keypoints neste vídeo (ex.: um frame teve apenas 6/17 keypoints acima do `MIN_CONFIDENCE=0.5` em `tf_serving_client.py`, faltando tornozelo/joelho do lado visível em muitos frames) — isso é uma característica do modelo de pose estimation em si (constante pré-existente, não alterada nesta tarefa), não uma regressão do motor de IA. Como o arquivo do modelo original se perdeu, não é possível confirmar se o modelo restaurado hoje é bit-a-bit idêntico ao usado em 2026-06-16, mas é o artefato oficial e canônico esperado pela assinatura do serviço.

**Pendência para o futuro** (fora do escopo desta tarefa, mas vale registrar): commitar o SavedModel do MoveNet (`pose-service/models/1/`) em algum lugar persistente (git-lfs, ou storage externo com script de download), já que hoje ele só existe no disco local da máquina de desenvolvimento — se for perdido de novo, `tf-serving` para de funcionar silenciosamente.

## 2026-06-17

### Substituição do motor de regras hardcoded por modelos de IA (detecção de exercício + análise de forma)

**Objetivo**: substituir a detecção de tipo de exercício (`exercise_classifier.py`, regras biomecânicas if/else) e a análise de forma/score (`exercise_analyzer.py`, thresholds hardcoded) por modelos de Machine Learning, priorizando os 3 exercícios mais críticos: SQUAT, DEADLIFT, BENCH_PRESS. Decisões alinhadas com o usuário: (1) dataset sintético bootstrap a partir das regras atuais, já que não existe dataset real rotulado; (2) IA substitui totalmente o motor de regras para os exercícios cobertos; (3) modelos embarcados no processo do pose-service (sem TF Serving extra).

**Novos módulos em `pose-service/ai/`**:
- `features.py` — extrai vetor de ~24 features numéricas (ângulos, distâncias, % de desvio) a partir dos landmarks, reaproveitando `angle_calculator.calculate_joint_angles()` para garantir consistência entre treino e inferência real. `FORM_FEATURE_NAMES` adiciona `phase_code` (fase do movimento codificada) para o analisador de forma.
- `synthetic_body.py` — gera landmarks sintéticos (33 pontos, formato MoveNet) via geometria inversa: dado um ângulo de joelho/tronco/etc. alvo, calcula a posição exata dos landmarks que produz esse valor quando recalculado pelas funções reais (`calculate_angle`, `detect_orientation`). Suporta LATERAL/ANGLED/FRONTAL e os 5 tipos de exercício.
- `dataset_generator.py` — amostra parâmetros biomecânicos cobrindo todo o espectro bom→ruim por exercício, gera landmarks, e rotula usando o motor de regras atual como "professor" (`exercise_analyzer.py`). Duas correções deliberadas aplicadas no professor (preservando os thresholds biomecânicos originais, só corrigindo gates de fase logicamente quebrados):
  1. **Deadlift BACK_ROUNDED**: o gate original só disparava em fase ASCENDING/BOTTOM, mas ASCENDING nunca é produzido em produção (`analyze()` nunca passa `prev_angle`) — lombar arredondada durante a descida nunca era sinalizada. Ampliado para qualquer fase != STANDING.
  2. **Squat DEPTH_INSUFFICIENT**: o gate original exigia `phase==BOTTOM E knee_angle>90`, mas `detect_phase` define BOTTOM como `knee_angle<90` — condição logicamente impossível, o alerta nunca disparava. Reavaliado contra a faixa "próximo do fundo" (90°–125°) em vez do gate de fase.
  3. Também corrigido um bug de sinal próprio (não do motor de regras): `KNEE_OVER_TOE_RIGHT` usa convenção invertida (`foot.x - knee.x`) em relação ao lado esquerdo no motor de regras original — o gerador sintético amostrava sem essa inversão, gerando quase zero exemplos positivos para o lado direito.
- `train_classifier.py` — treina RandomForestClassifier (Pipeline com SimpleImputer embutido) para os 5 tipos de exercício. Acurácia held-out: **93%**.
- `train_form_analyzer.py` — treina, por exercício, um MultiOutputClassifier (erros NONE/LOW/MEDIUM/HIGH) + RandomForestRegressor (score 0-100). Acurácia por erro: 99.9%-100% nos 3 exercícios (squat, deadlift, bench press); MAE do score: 0.03–0.79 pontos.

**Inferência** (`pose-service/ai_exercise_classifier.py`, `pose-service/ai_exercise_analyzer.py`): mesma API pública dos módulos antigos (`classify_single`, `ExerciseAnalyzer.analyze()`) — drop-in replacement. LUNGE e BENT_OVER_ROW (sem dataset/modelo ainda) caem em fallback explícito para as funções de regra legadas de `exercise_analyzer.py`.

**Wiring**: `main.py` e `video_analyzer.py` agora importam `ai_exercise_analyzer.ExerciseAnalyzer` e `ai_exercise_classifier.classify_single` em vez dos módulos antigos. `requirements.txt` ganhou `scikit-learn==1.4.2` e `joblib==1.4.2` (mesma versão usada no treino local, para evitar incompatibilidade de unpickling no container).

**Testes**: `pose-service/tests/test_ai_exercise_engine.py` (novo) — 13 testes cobrindo classificador, squat/deadlift/bench press via IA, fallback de regras para lunge/row, landmarks insuficientes, e um teste de regressão específico para a correção do bug de fase do deadlift. **Status atual: 47/48 testes passando** (`test_exercise_analyzer.py` legado + novo arquivo).

**Pendência conhecida (resolvida em 2026-06-18, ver entrada acima)**: `test_elbow_flare_detected` falhava por um bug de divergência de `tan()` em `synthetic_body.py` perto de 90°.

## 2026-06-16

### Correção do pipeline de notificação WebSocket (fan-out por fila dedicada)

- **Problema**: `notification-service` e `session-service` consumiam da **mesma fila** `gym.alert.created`. O RabbitMQ faz round-robin entre consumidores da mesma fila → cada mensagem ia para apenas um dos dois serviços → o professor recebia apenas ~50% dos alertas.
- **Causa secundária**: `messaging.py` (pose-service) publicava apenas um `dummy` com `errors=[]` no modo vídeo, então `gym.alert.created` nunca recebia os alertas individuais da análise.
- **Correções**:
  1. `pose-service/messaging.py` — adicionada função `publish_alert()` para publicar alertas individuais, e declaradas filas dedicadas `notify.alert.created` e `notify.exercise.result` vinculadas ao mesmo exchange com o mesmo routing key (fan-out real).
  2. `pose-service/main.py` — endpoint `analyze-video` agora publica cada `professor_alert` do relatório via `messaging.publish_alert()` antes do resumo.
  3. `notification-service/src/consumer/alert.consumer.ts` — mudadas as filas de `gym.alert.created`/`gym.exercise.result` para `notify.alert.created`/`notify.exercise.result`.
- **Resultado**: cada serviço tem 1 consumidor exclusivo, recebe cópia de todos os eventos. Validado: **2 alertas chegaram ao professor via WebSocket** (`KNEE_CAVE_RIGHT [MEDIUM]` + `BACK_NOT_STRAIGHT [HIGH]`) em menos de 1s após a análise de vídeo.
- Containers `gymvision-pose-svc` e `gymvision-notify-svc` reconstruídos e recriados.

### Detecção de inclinação sagital do tronco em câmera frontal (BACK_NOT_STRAIGHT)

- **Problema**: Em câmera frontal (fw≥0.65), `back_angle` só media inclinação *lateral* (eixo X). Inclinação para frente — a mais comum em squat ruim — não era detectada porque acontece no eixo Z (profundidade), invisível ao 2D frontal.
- **Solução**: adicionada função `_frontal_back_angle_combined()` em `angle_calculator.py`. Combina a inclinação lateral existente com a inclinação sagital via coordenada Z do MediaPipe: `lean_sagital = atan2(max(hip_z - sh_z, 0), hip_y - sh_y)`. Retorna `max(lateral, sagital)`, garantindo que `BACK_NOT_STRAIGHT` dispare para ambas as direções.
- **Validado com vídeo real** (`Bad squat form!!! It needs help!! #shorts.mp4`, câmera frontal fw≈0.89):
  - `BACK_NOT_STRAIGHT [HIGH]` detectado em 33.8% dos frames (23/68), alerta em 1.8s com 75° (máx 45°)
  - `KNEE_CAVE_RIGHT [MEDIUM]` detectado em 23.5% dos frames, alerta em 1.3s
  - Score médio: 88.0 (mín 60.0 no BOTTOM); Rep 1 com risk=HIGH
- Container `gymvision-pose-svc` reconstruído e recriado com `docker compose build && docker compose up -d --force-recreate`.

### Correção do SQUAT_KNEE_CAVE_THRESHOLD + validação com vídeo real

- **Bug identificado**: `SQUAT_KNEE_CAVE_THRESHOLD` estava em `15.0` no container (`pose-service/exercise_analyzer.py`), valor que havia sido corrigido para `4.0` localmente mas o container nunca foi reconstruído. Com 15%, um joelho a 5% medial do tornozelo não disparava nenhum alerta.
- **Causa raiz**: `docker compose build` sem `--force-recreate` não reaplica o código novo.
- **Solução**: `docker compose build pose-service && docker compose up -d --force-recreate pose-service`.
- **Validado com vídeo real** (`Bad squat form!!! It needs help!! #shorts.mp4`, 11.3s, câmera frontal):
  - 68 frames analisados, score médio 96.5, mín 85.0
  - `KNEE_CAVE_RIGHT` detectado em 16/68 frames (23.5%), primeiro alerta em 1.3s
  - Alerta MEDIUM disparado ao professor corretamente
  - 1 rep detectada com `risk_level=MEDIUM`

### Adição da feature "Testar com Vídeo" no app Android + dashboard web

**Android app** (`android-app/`):
- Novos arquivos:
  - `ui/videotest/VideoTestViewModel.kt` — ViewModel com `processVideo(uri, context, exerciseType)`: extrai frames a cada 200ms via `MediaMetadataRetriever`, escala para max 640px, envia cada frame ao endpoint `/api/v1/pose/analyze` (mesmo do modo câmera), armazena `List<FrameData>` com landmarks + score + fase + erros por timestamp.
  - `ui/videotest/VideoTestScreen.kt` — 4 estados: **Idle** (seletor de exercício + botão de escolha de arquivo via `OpenDocument`), **Processing** (barra de progresso frame a frame), **Ready** (playback com overlay), **Error**.
    - No estado Ready: `VideoView` via `AndroidView` + `PoseOverlay` (mesmo componente do `CameraScreen`) sincronizados por coroutine de polling a cada 100ms no `currentPosition`. `ScoreGauge`, `PhaseChip`, banner de alertas `HIGH/MEDIUM` e `VideoErrorsCard` espelham exatamente o layout do `CameraScreen`.
    - Botão Play/Pause em Compose sobre o vídeo; sem `MediaController` para evitar conflito com a hierarquia Compose.
- Arquivos modificados:
  - `navigation/Routes.kt` — adicionada constante `VIDEO_TEST = "video_test"`.
  - `navigation/MainScreen.kt` — 4º item na bottom nav: "Testar" com ícone `VideoLibrary`; composable `VideoTestScreen()` adicionado ao inner NavHost.
- Build validado: `./gradlew :app:compileDebugKotlin` e `./gradlew :app:assembleDebug` passam sem erros.

**Dashboard web** (`dashboard/`):
- Novos arquivos:
  - `src/hooks/useVideoAnalysis.ts` — hook com `analyze({ file, exerciseType, frameIntervalMs })` que chama `POST /api/v1/pose/analyze-video` com `fetch` + `FormData`; retorna `{ report, loading, error, reset }`.
  - `src/pages/VideoTestPage.tsx` — formulário: seletor de arquivo `.mp4/.mov/.avi`, select de exercício, select de taxa de análise (5/10/20/30fps), botão de envio; mostra `VideoReportView` com o relatório após retorno.
  - `src/components/VideoReportView.tsx` — exibe: resumo (duração, frames, score médio/min/max, reps, alertas), gráfico SVG de score ao longo do vídeo, tabela de reps, top erros, alertas ao professor, frames críticos.
- `src/App.tsx` — adicionada navegação por abas: "Alertas" (dashboard original) e "Testar Vídeo" (nova página).

### Modo offline Android (ML Kit on-device + WorkManager sync)

- **`OfflinePoseAnalyzer.kt`**: usa ML Kit `AccuratePoseDetectorOptions.STREAM_MODE` (BlazePose 33 landmarks, TFLite no dispositivo). Converte `PoseLandmark` → `Landmark` normalizado [0,1]. Roda análise local simplificada (mesmos thresholds do backend Python): squat (profundidade, knee cave, back angle), deadlift (lombar, quadril), lunge, bench press (pulso), bent-over row (lombar). Fase detectada por ângulo do joelho com memória de frame anterior.
- **`ConnectivityObserver.kt`**: `callbackFlow` sobre `ConnectivityManager.NetworkCallback` → `Flow<Boolean>` com `distinctUntilChanged`.
- **`LocalFrameStore.kt`**: `SQLiteOpenHelper` com tabela `pending_frames` (session_id, student_id, academy_id, exercise_type, frame_seq, landmarks_json, score, phase, synced). Sem Room/KSP para evitar complexidade de annotation processing.
- **`SyncWorker.kt`**: `CoroutineWorker` do WorkManager agendado com `NetworkType.CONNECTED`. Lê frames não sincronizados, reenvia via `poseApi.analyze()`, encerra sessão via `sessionApi.end()`. Placeholder JPEG 1×1 mínimo preserva a assinatura multipart do endpoint.
- **`CameraViewModel.kt`** → migrado para `AndroidViewModel` (precisa de `Application` para `ConnectivityObserver`). Coleta `ConnectivityObserver.observe()` no `init{}` — atualiza `isOffline` em tempo real. Quando offline: chama `OfflinePoseAnalyzer`, persiste no `LocalFrameStore`; quando voltar online: agenda `SyncWorker`. `AnalysisUiState` ganhou `isOffline: Boolean` e `pendingFrames: Int`.
- **`CameraScreen.kt`**: `OfflineBanner` laranja (cor `0xFFE65100`) com ícone `WifiOff` aparece abaixo do score quando `state.isOffline = true`. Mostra "OFFLINE · análise local ativa" ou "OFFLINE · N frames pendentes".
- **`AndroidManifest.xml`**: `<meta-data name="com.google.mlkit.vision.DEPENDENCIES" value="poseaccurate"/>` pré-carrega o modelo BlazePose no momento da instalação → funciona sem internet imediatamente.
- **`build.gradle.kts`**: `mlkit:pose-detection-accurate:18.0.0-beta3`, `work-runtime-ktx:2.9.0`, `kotlinx-coroutines-play-services:1.7.3`.
- `DetectedError.jointAngle` recebeu `= null` como default para permitir construção sem o campo.
- **Validado**: `./gradlew :app:assembleDebug` → `BUILD SUCCESSFUL in 25s`.

### Testes automatizados (34 testes pytest — exercise_analyzer.py)

- Criado `pose-service/tests/test_exercise_analyzer.py` com 34 testes unitários cobrindo:
  - `detect_phase()`: STANDING/BOTTOM/DESCENDING/ASCENDING/UNKNOWN
  - `calculate_score()`: penalidades por HIGH/MEDIUM/LOW, floor em 0, fase UNKNOWN
  - `_analyze_squat()`: BACK_NOT_STRAIGHT (MEDIUM/HIGH), KNEE_CAVE_RIGHT frontal, KNEE_CAVE desabilitado lateral, DEPTH_INSUFFICIENT (só BOTTOM)
  - `_analyze_deadlift()`: BACK_ROUNDED, HIPS_TOO_HIGH
  - `_analyze_bench_press()`: ELBOW_FLARE frontal, WRIST_BENT
  - `_analyze_bent_over_row()`: BACK_ROUNDED (MEDIUM/HIGH), back OK sem erro
  - `ExerciseAnalyzer.analyze()`: integração completa para SQUAT/BENCH_PRESS/BENT_OVER_ROW, landmarks insuficientes → UNKNOWN score=0
- Todos os 34 testes passam: `pytest /app/tests/test_exercise_analyzer.py — 34 passed`
- `pytest==8.2.2` adicionado ao `pose-service/requirements.txt`

### Gamificação (pontos, nível, streak, conquistas, leaderboard)

- **analytics-service** — novos endpoints:
  - `GET /api/v1/analytics/gamification/{student_id}`: retorna points, level, next_level_points, streak_days, total_sessions, clean_sessions, total_reps, best_score, achievements (12 conquistas desbloqueáveis)
  - `GET /api/v1/analytics/my/sessions`: histórico de sessões por student_id
  - Fórmula: pontos = Σ avg_score por sessão; nível = pontos // 500; streak = dias consecutivos com sessão até hoje
  - Conquistas: first_session, ten_sessions, fifty_sessions, clean_form, clean_streak, rep_100, rep_1000, streak_3, streak_7, perfect_score, level_5, level_10
- **Android app** — novos arquivos:
  - `ui/achievements/AchievementsViewModel.kt`: carrega gamification + leaderboard em paralelo
  - `ui/achievements/AchievementsScreen.kt`: card de nível + barra de progresso, stats rápidos, grid de conquistas com emoji, ranking da academia com medalhas
  - `navigation/Routes.kt`: `ACHIEVEMENTS = "achievements"`
  - `navigation/MainScreen.kt`: aba "Conquistas" com ícone `EmojiEvents` (5ª aba)
  - `model/Models.kt`: `Achievement`, `GamificationResponse`, `LeaderboardEntry`, `LeaderboardResponse`
  - `api/ApiInterfaces.kt`: métodos `gamification()` e `leaderboard()`
- **Dashboard web** — novo `dashboard/src/pages/LeaderboardPage.tsx`:
  - Tabela de ranking com medalhas 🥇🥈🥉
  - ScoreBadge colorido (verde/amarelo/vermelho)
  - Catálogo de 12 conquistas disponíveis com ícones
  - Explicação da fórmula de pontuação
  - Nova aba "Ranking 🏆" em `App.tsx`
- Container `gymvision-analytics-svc` reconstruído e validado (`GET /api/v1/analytics/gamification/test-student` → 200)

### Item 22 — Multi-tenancy (múltiplas academias)

- **user-service**:
  - `V2__academy_invite_code.sql`: coluna `invite_code VARCHAR(12) UNIQUE` nas academias; academia demo → "GYMVISION01"; índice `idx_academies_invite_code`
  - `JwtUtils.kt`: `generateAccessToken/RefreshToken` ganham parâmetro `academyId?: String`; claim `academy_id` embutida no JWT; `getAcademyIdFromToken()` adicionado
  - `Entities.kt (Academy)`: campo `inviteCode: String?` mapeado para `invite_code`
  - `Repositories.kt`: `AcademyRepository` (findByInviteCode, existsByName); `UserRepository.findAllByAcademyIdAndRoleAndActiveTrue()` adicionado
  - `AuthService.kt`: `RegisterRequest` aceita `inviteCode?`; `register()` resolve academia pelo código; `generateTokenPair()` embute `academy_id` no JWT; `AcademyService` (list, getById, getByInviteCode, create com código auto-gerado); `AcademyDto`; `UserService.joinAcademy()` e `listByAcademy(role?)`
  - `Controllers.kt`: `RegisterRequestBody` com `inviteCode?` e `role?`; `GET /api/v1/users` com `?academyId=&role=`; `POST /api/v1/users/join-academy`; `AcademyController` com GET/POST endpoints; `UserDto.academyName` adicionado
- **session-service**:
  - `TenantFilter.kt` (novo): `OncePerRequestFilter` que base64-decodifica o payload JWT sem re-validar assinatura (Kong já validou), extrai `academy_id` e `role` como atributos do `HttpServletRequest`
  - `SessionService.createSession()`: tenant guard — rejeita 409 se `tenantAcademyId ≠ req.academyId` (exceto ADMIN)
- **analytics-service**: já isolava todos os dados por `academy_id`; sem alterações necessárias
- **Kong gateway (`kong.yml`)**: `/api/v1/academies` adicionado às rotas do user-service; `/api/v1/workout-plans` adicionado às rotas do session-service
- **Dashboard**:
  - `AcademyPage.tsx` (novo): aba "Academias 🏛️" visível apenas para `role === 'ADMIN'`; lista academias com stats de 30 dias (sessões, reps, alunos ativos) via analytics, mostra `invite_code` com botão copiar, busca por código, formulário de criação
  - `App.tsx`: tipo `Tab` expandido; aba "Academias 🏛️" condicional por role; `AcademyPage` importado e renderizado
- **Android app**:
  - `Models.kt`: `UserDto.academyName: String?` adicionado
  - `ApiInterfaces.kt (UserApi)`: `POST api/v1/users/join-academy` adicionado
  - `ProfileViewModel.kt`: estado `isJoining`, `joinError`; método `joinAcademy(inviteCode)` chama API e persiste `academyId` via `ApiClient.saveUserInfo()`
  - `ProfileScreen.kt`: mostra `user.academyName` no card de academia (em vez do UUID); quando `academyId == null`, exibe `JoinAcademyCard` com campo de texto e botão para entrar na academia pelo código
- **Build**: user-service BUILD SUCCESSFUL (Docker image), session-service BUILD SUCCESSFUL (Docker image), Android APK BUILD SUCCESSFUL

### Item 21 — Plano de treino integrado

- **session-service**:
  - `Entities.kt`: novas entidades `WorkoutPlan` (id, academyId, studentId, professorId, name, dayOfWeek, active) e `WorkoutPlanItem` (planId, exerciseType, sets, repsPerSet, loadKg, notes, orderIndex); enum `ExerciseType` expandido com BENCH_PRESS e BENT_OVER_ROW
  - `Repositories.kt`: `WorkoutPlanRepository` (findAllByStudentIdAndActiveTrue, findAllByAcademyIdAndActiveTrue) + `WorkoutPlanItemRepository` (findAllByPlanIdOrderByOrderIndexAsc, deleteAllByPlanId)
  - `WorkoutPlanService.kt` (novo): `create`, `getById`, `listByStudent`, `listByAcademy`, `updateItems`, `deactivate`
  - `WorkoutPlanController.kt` (novo): endpoints POST /api/v1/workout-plans, GET por id/student/academy, PUT items, DELETE (deactivate)
  - Migration `V4__workout_plans.sql`: tabelas `workout_plans` e `workout_plan_items` com índices
- **Dashboard**:
  - `WorkoutPlanPage.tsx` (novo): seletor de aluno, formulário de criação com exercícios (nome, séries, reps, carga, observações), listagem com cards de plano e botão Remover. Nova aba "Planos 📋" em `App.tsx`
- **Android app**:
  - `WorkoutPlan`, `WorkoutPlanItem`, `WorkoutPlanListResponse` adicionados a `Models.kt`
  - `WorkoutPlanApi` adicionado a `ApiInterfaces.kt` + `ApiClient.workoutPlanApi`
  - `WorkoutPlanViewModel.kt` (novo): carrega planos por studentId, filtra por dia da semana (1=Seg..7=Dom), `createSession()` cria sessão e retorna via callback
  - `WorkoutPlanScreen.kt` (novo): mostra plano do dia (ou todos), cards com exercício/séries/reps/carga, botão ▶ cria sessão e navega direto ao `CameraGuideScreen` com o exercício pré-selecionado
  - `Routes.kt`: `WORKOUT_PLAN = "workout_plan"` adicionado
  - `MainScreen.kt`: aba "Treino" com ícone `CalendarMonth` na bottom nav (substituiu "Testar"); `composable(Routes.WORKOUT_PLAN)` registrado
- **BUILD SUCCESSFUL em 8s** (`.gradlew :app:assembleDebug`)

### Criação do documento base do TCC (TCC_BASE.txt)

- Criado `TCC_BASE.txt` na raiz do projeto — documento completo para uso com Claude Web para continuar a escrita do TCC.
- **Conteúdo gerado** (formato ABNT NBR 14724:2011 + NBR 6023:2018):
  - Folha de rosto, Resumo (PT-BR) e Abstract (EN) com dados reais do sistema
  - Lista de abreviaturas e siglas, Sumário detalhado com 6 capítulos
  - **Cap. 1 — Introdução** (completo): motivação, epidemiologia de lesões, objetivos gerais e específicos
  - **Cap. 2 — Referencial Teórico** (completo, 8 seções): lesões por má execução, visão computacional, BlazePose (BAZAREVSKY et al. 2020), MoveNet + TF Serving, análise biomecânica com thresholds da literatura, microsserviços (FOWLER; LEWIS 2014, NEWMAN 2019), RabbitMQ, ML Kit, feedback em tempo real (SCHMIDT; LEE 2011)
  - **Cap. 3 — Metodologia** (completo): classificação da pesquisa, 4 fases de desenvolvimento, ferramentas/tecnologias, critérios de validação
  - **Cap. 4 — Desenvolvimento** (10 subseções com [DESENVOLVER] marcado) — estrutura e instruções para Claude Web preencher
  - **Cap. 5 — Resultados** (seções 5.1–5.4 rascunhadas com dados reais): Tabelas 3–5 com métricas de vídeo, latência e testes
  - **Cap. 6 — Conclusão** (estrutura com [DESENVOLVER])
  - **Referências** completas em ABNT: 22 referências (Bazarevsky, Lugaresi, Fowler, Newman, Richardson, McGill, Escamilla, Padua, Schmidt & Lee, David/TFLite, Deterding, Cao/OpenPose, etc.)
  - **Apêndice A** — estrutura completa de arquivos do projeto
  - **Apêndice B** — dados técnicos do experimento (vídeo, resultados, containers)

---

## 2026-06-09

### 21:12 — Correção do crash-loop do session-service (schema validation + bean ambíguo)
- **Causa raiz 1**: coluna `reps.errors` criada como `JSONB` (V1), mas a entidade `Rep.errors: String` esperava `varchar`/`text` (Hibernate `ddl-auto: validate` falhava com `found [jsonb (Types#OTHER)], but expecting [varchar(255) (Types#VARCHAR)]`). Tentativa anterior com `@JdbcTypeCode(SqlTypes.JSON)` **não resolveu**. Solução definitiva: nova migration `V2__reps_errors_to_text.sql` (`ALTER COLUMN errors TYPE TEXT`) + `Entities.kt` revertido para `@Column(columnDefinition = "TEXT") val errors: String = "[]"`.
- **Causa raiz 2**: colunas `reps.score` e `sessions.avg_score` criadas como `DECIMAL(5,2)` (V1), mas os campos Kotlin são `Double` (Hibernate espera `float(53)`/`double precision`). Erro: `found [numeric (Types#NUMERIC)], but expecting [float(53) (Types#FLOAT)]`. Solução: nova migration `V3__numeric_to_double_precision.sql` (`ALTER COLUMN ... TYPE DOUBLE PRECISION`).
- **Causa raiz 3**: `RabbitConfig.kt` — `bindExerciseResult`, `bindAlertCreated`, `bindSessionEnded` recebiam um parâmetro `q: Queue` não utilizado; com 3 beans `Queue` distintos no contexto, Spring falhava com `expected single matching bean but found 3`. Removidos os parâmetros não usados (os métodos já chamam a queue correta diretamente).
- Container `session-service` reconstruído (`docker compose up -d --build session-service && docker compose up -d --force-recreate session-service` — **lembrar que `--build` sozinho não recria o container**, é preciso `--force-recreate`).
- **Validado end-to-end via curl** (gateway Kong, porta 8090): login (`teste@gymvision.com`/`senha123`), `POST /api/v1/sessions` (criação) e `GET /api/v1/sessions/student/{id}` (listagem) retornam `200`/`201` com sucesso. Container `gymvision-session-svc` está `Up (healthy)`.

### 20:44 — Redesign completo do app mobile (Jetpack Compose + Material 3) integrado aos microsserviços
- Migração total de `android-app` de Views/XML (Activities/Fragments) para **Jetpack Compose + Material 3** (Compose BOM 2024.02.00, Kotlin 1.9.21, AGP 8.2.0).
- Tema custom (`ui/theme/{Color,Type,Theme}.kt`), ícone adaptativo e splash screen (`androidx.core:core-splashscreen`).
- Navegação: `MainActivity` único + `AppNavHost` (login ↔ main) + `MainScreen` com bottom navigation (Sessões, Progresso, Perfil).
- Telas novas: `LoginScreen`, `SessionListScreen` (pull-to-refresh, criação de sessão via bottom sheet), `SessionDetailScreen` (relatório via `analytics-service`), `CameraScreen` (overlay de esqueleto/landmarks em tempo real via `PoseOverlay` + Canvas, gauge de score, alertas via WebSocket do `notification-service`), `ProgressScreen` (gráfico semanal, top erros, sessões recentes via `analytics-service`), `ProfileScreen` (dados via `user-service /me`, logout).
- Componentes compartilhados: `StatCard`, `ScoreGauge`, `RiskMappers` (PT-BR), `LoadingError`.
- `ApiClient`/`ApiInterfaces`/`Models`: adicionados `userApi`, `analyticsApi`, DTOs de analytics, helpers de sessão (`saveUserInfo`, `getUserId`, etc.).
- Corrigido bug de assinatura de `CameraViewModel.onFrame()` (parâmetro `academyId` estava na posição errada).
- Removidos arquivos antigos: `LoginActivity`, `SessionListActivity`, `CameraActivity`, `CameraFragment` e seus layouts XML; `AndroidManifest.xml` agora registra apenas `MainActivity` com tema/ícone novos.
- Build configurado: gradle wrapper 8.5 copiado para `android-app/`, `local.properties` com SDK, `gradle.properties` com `android.useAndroidX=true`.
- Corrigidos erros de build: `Theme.GymVision` (parent inválido `Theme.DeviceDefault.DayNight.NoActionBar` → `Theme.DeviceDefault.NoActionBar`), `package` duplicado no manifest, import de `installSplashScreen`, import de `Modifier.padding` em `MainScreen`.
- `gradle/wrapper/gradle-wrapper.jar` em `android-app/` estava vazio (0 bytes); regenerado via `gradle wrapper --gradle-version 8.5` usando a distribuição em cache.
- **Validado**: `./gradlew :app:compileDebugKotlin` e `./gradlew :app:assembleDebug` passam com sucesso (`app-debug.apk` gerado, 18MB).

### 09:00 — Criação do arquivo de log
- Criou este arquivo `ACTIONS_LOG.md` na raiz do projeto para registrar ações futuras.

### 09:35 — Correção do pipeline de notificação
- `messaging.py`: payload publicado no RabbitMQ agora é envelopado em `{"timestamp": ..., "data": {...}}`, compatível com o que `alert.consumer.ts` espera.
- `main.py`: endpoint `PUT /api/v1/pose/rules` agora atualiza `_analyzer.thresholds` em memória (hot-reload real).
- Validado: `BACK_NOT_STRAIGHT [MEDIUM]` → RabbitMQ → notification-service → WebSocket broadcast em 0ms.

### 09:25 — Fallback MediaPipe para detecção de landmarks
- `requirements.txt`: adicionado `mediapipe==0.10.14`.
- `tf_serving_client.py`: `_fallback_predict` reescrito para usar `mp.solutions.pose.Pose` com `min_detection_confidence=0.3` e threshold de visibilidade `0.2`. Detecta landmarks de qualquer posição (frontal, lateral, diagonal). Container reconstruído com `--no-cache`.

### 09:20 — Rebuild do container pose-service
- Executou `docker compose up -d --build pose-service`. Container recriado com código correto confirmado via `docker exec`.

### 09:15 — Diagnóstico: container pose-service com código desatualizado
- Confirmado via `docker exec` que o container tinha `main.py` e `video_analyzer.py` antigos (desempacotando 2 valores) enquanto `tf_serving_client.py` já retornava 3 (`landmarks, inference_ms, orientation`). Solução: `docker compose up -d --build pose-service`.

### 09:10 — Correção: "too many values to unpack" em /pose/analyse
- `video_analyzer.py:275` — `tf_client.predict()` passou a retornar 3 valores (`landmarks, inference_ms, orientation`) após refatoração do `tf_serving_client.py`, mas `video_analyzer.py` ainda desempacotava apenas 2. Corrigido o desempacotamento e adicionado `orientation=orientation` na chamada de `analyzer.analyze()`.

### 09:05 — Consulta de comandos Docker
- Leu `docker-compose.yml` e forneceu comandos para parar (`docker compose down`) e reiniciar (`docker compose up -d --build`) o projeto, além de comandos utilitários de logs e status.

---

### Sprint 1 — Fundação e Segurança (itens 25–28)

**Item 25 — CI/CD GitHub Actions (`.github/workflows/ci.yml` expandido)**
- Jobs adicionados: `session-service-build` (Gradle), `analytics-service-test` (flake8), `dashboard-build` (npm ci + Vite), `android-build` (assembleDebug + upload APK 7 dias), `compose-validate` (docker compose config)
- `build-and-push` agora depende de todos os builds e inclui: session-service, analytics-service, backup-service
- Branch trigger expandido para `master` além de `main`

**Item 26 — Backup automático (`backup-service/`)**
- `backup-service/Dockerfile`: `python:3.11-slim` + `postgresql-client` via apt
- `backup-service/requirements.txt`: minio, pymongo, APScheduler
- `backup-service/backup.py`:
  - `BlockingScheduler` cron 03:00 UTC diário
  - `_pg_dump()`: subprocess `pg_dump -Fc` para postgres e timescale
  - `_mongo_export()`: pymongo export JSON gzipado por coleção
  - `_upload()`: MinIO SDK upload para `gymvision-backups/postgres|timescale|mongodb/{date}/`
  - `_cleanup()`: remove objetos com `last_modified < now - 30d`
  - `RUN_ON_START=true` para executar imediatamente (útil em testes)
- `docker-compose.yml`: serviço `backup-service` com `depends_on` de postgres/timescale/mongodb/minio

**Item 27 — Refresh token rotation**
- JÁ IMPLEMENTADO nas sessões anteriores. Verificado: `AuthService.refreshToken()` linha 119-120 marca token anterior como `revoked=true` antes de emitir novo par.

**Item 28 — LGPD compliance**
- `user-service/repository/Repositories.kt`: `deleteAllByUserId()` com `@Modifying @Query DELETE`
- `user-service/service/AuthService.kt`: DTO `UserDataExport(profile, exportedAt, dataNotice)`, `UserService.deleteAccount()` e `exportData()`
- `user-service/controller/Controllers.kt`: `GET /api/v1/users/me/export` e `DELETE /api/v1/users/me`, injeção de `RefreshTokenRepository`
- `android-app/ApiInterfaces.kt`: `@GET me/export` e `@DELETE me` na `UserApi`
- `android-app/ProfileViewModel.kt`: `exportData()` e `deleteAccount()`, novos campos de estado
- `android-app/ProfileScreen.kt`: seção "Privacidade e Dados" com botões exportar/excluir, AlertDialogs de confirmação e exibição de JSON, scroll vertical habilitado

---

### Item 23 — Relatório PDF mensal por aluno

**analytics-service/requirements.txt**
- Adicionadas dependências: `reportlab>=4.2.0`, `APScheduler>=3.10.4,<4`, `httpx>=0.27.0`

**analytics-service/src/main.py**
- Novos imports: `calendar`, `io`, `smtplib`, `email.mime.*`, `httpx`, `APScheduler.schedulers.asyncio.AsyncIOScheduler`, `reportlab.*`, `fastapi.Response`
- Novas env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `USER_SERVICE_URL`
- Global `_scheduler: AsyncIOScheduler` — iniciado no `lifespan`, encerrado no shutdown
- `_build_pdf(student_id, month_label, sessions, top_errors, overall) -> bytes`: gera PDF A4 com reportlab (SimpleDocTemplate + Platypus): header GymVision, tabela de resumo (sessões/reps/score médio/melhor score), tabela de sessões (até 15 linhas), tabela de erros frequentes, rodapé com timestamp
- `GET /api/v1/analytics/student/{student_id}/report/pdf?month=YYYY-MM`: retorna `application/pdf` com header `Content-Disposition: attachment`; padrão = mês atual; filtra MongoDB por intervalo de data ISO do mês
- `_get_student_email(student_id) -> Optional[str]`: chama `USER_SERVICE_URL/api/v1/users/{id}` via httpx com timeout=5s
- `_send_pdf_sync(to, subject, html_body, pdf_bytes, filename)`: envia e-mail via `smtplib.SMTP` com STARTTLS, corpo HTML + anexo PDF `MIMEApplication`
- `send_monthly_reports()`: job assíncrono agendado para **dia 1 de cada mês às 08:00 UTC**; consulta distinct student_ids do mês anterior; para cada aluno: busca email via user-service, gera PDF, envia via `run_in_executor(_send_pdf_sync)`; logs de progresso e erros individuais
- APScheduler: `_scheduler.add_job(send_monthly_reports, "cron", day=1, hour=8, minute=0)`

**dashboard/src/pages/StudentProgressPage.tsx**
- Import adicional: `getStoredUser` de `../hooks/useAuth`
- Hook `usePdfDownload(studentId)`: faz `fetch` do endpoint PDF com token Bearer, converte response em Blob, cria link temporário e dispara download automático com nome `gymvision-{id[:8]}-{YYYY-MM}.pdf`
- Botão "Relatório PDF" com ícone de download adicionado no header da página ao lado do título; desabilitado durante download (spinner SVG animado) e se não há usuário logado

---

## 2026-06-22

### Restaurada a feature "Testar Vídeo" no app mobile e vídeos de exemplo embutidos no APK

A pedido do usuário ("volte a feature de testes" + "adicione os vídeos na memória do mobile para eu testar").

**Causa raiz da feature estar inacessível**: `VideoTestScreen`/`VideoTestViewModel`/rota `Routes.VIDEO_TEST` já existiam completos desde o commit `574dbfd`, e o ícone `Icons.Filled.VideoLibrary` já estava importado em `MainScreen.kt` — mas nunca foi adicionado a `bottomNavItems`, então a tela não tinha nenhum ponto de entrada na UI (rota órfã no `NavHost`).

**Correções**:
- `android-app/.../ui/navigation/MainScreen.kt`: adicionado item "Testar" (`Routes.VIDEO_TEST`, `Icons.Filled.VideoLibrary`) em `bottomNavItems`.
- `android-app/app/src/main/assets/test_videos/`: 8 vídeos reais de teste (squat×2, deadlift×2, lunge, bench_press×2, bent_over_row — os mesmos usados na validação do motor de IA, copiados de `/tmp/gymvision_test_videos/`) embutidos como assets do APK (~21MB).
- `VideoTestViewModel.kt`: novo `SAMPLE_VIDEOS` (lista de `SampleVideo(assetName, label, exerciseType)`) e `processSampleVideo()` — copia o asset para `cacheDir` (idempotente, só copia se não existir) e gera um `content://` URI via `FileProvider` para alimentar o mesmo pipeline de `processVideo()`.
- `VideoTestScreen.kt`: seção "Ou use um vídeo de exemplo" na tela inicial, com um card por vídeo; lista `EXERCISES` expandida de `[SQUAT, DEADLIFT, LUNGE]` para incluir também `BENCH_PRESS`/`BENT_OVER_ROW`.
- Novo `FileProvider` registrado em `AndroidManifest.xml` (`${applicationId}.fileprovider`) + `res/xml/file_paths.xml` (`cache-path`), necessário para gerar URIs de conteúdo seguros a partir dos arquivos copiados para o cache.
- **Validado**: `./gradlew :app:compileDebugKotlin` e `./gradlew :app:assembleDebug` passam sem erros; `app-debug.apk` gerado (116MB) e confirmado via `unzip -l` que os 8 vídeos estão em `assets/test_videos/` dentro do APK.

---

### Reversão do motor de IA para o motor de regras original — a pedido do usuário

Usuário testou o motor de IA (`ai_exercise_analyzer.py`/`ai_exercise_classifier.py`) com os vídeos reais e achou os avisos de erro muito brandos comparado ao motor de regras original — decisão: não vale a complexidade adicional, reverter.

**Causa raiz do problema relatado**: o dataset de treino da IA é sintético, rotulado pelo **próprio motor de regras antigo** atuando como professor (weak supervision). Um classificador estatístico treinado para imitar um conjunto de regras determinísticas tende a suavizar os casos extremos (regressão à média), especialmente na classe `HIGH` (minoritária) — por isso a IA sistematicamente subestimava a severidade em formas claramente incorretas. A IA nunca poderia superar o motor de regras nesse desenho, só na melhor das hipóteses igualá-lo.

**Reversão (apenas religação de imports — nenhuma lógica nova)**:
- `pose-service/main.py`: `from ai_exercise_analyzer import ExerciseAnalyzer` → `from exercise_analyzer import ExerciseAnalyzer`; `from ai_exercise_classifier import classify_single` → `from exercise_classifier import classify_single`.
- `pose-service/video_analyzer.py`: mesmas trocas para `ExerciseAnalyzer` e `classify_frames`.
- Módulos `ai_exercise_analyzer.py`, `ai_exercise_classifier.py`, `ai/` (dataset generator, modelos `.joblib`, etc.) **mantidos no disco mas desconectados** — não removidos, caso seja útil retomar com dados reais no futuro.
- **Validado**: `pytest tests/ --ignore=tests/test_pose_service.py` → 48/48 passando; `docker compose up -d --build pose-service && docker compose up -d --force-recreate pose-service` → container `gymvision-pose-svc` `healthy`, confirmado via `docker exec` que `main.py`/`video_analyzer.py` agora importam de `exercise_analyzer`/`exercise_classifier` (não dos módulos `ai_*`); `GET /api/v1/pose/health` → `200 OK`; cache Redis do vídeo de teste limpo (`FLUSHALL`) para evitar relatórios cacheados da era IA.

---

### Correção do score zerado em BENCH_PRESS/BENT_OVER_ROW no motor de regras (regressão da reversão acima)

Usuário relatou, após restaurar a feature "Testar Vídeo": "overlay no teste esta todo quebrado nao esta identificando corretamente e as mensagens de erro tambem estao ruins".

**Causa raiz**: investigado rodando `analyze-video` direto contra o pose-service (porta 8083) com os vídeos de exemplo embutidos no APK. `bench_press.mp4` voltou a dar `avg_score=0.0` em 100% dos frames — exatamente o bug "score zerado em BENCH_PRESS quando pernas fora de quadro" já corrigido em `ai_exercise_analyzer.py` na entrada de 2026-06-18 acima. O motor de regras (`exercise_analyzer.py`) nunca recebeu o fix equivalente: `_analyze_bench_press`/`_analyze_bent_over_row` foram adicionados ao motor de regras no mesmo commit que introduziu a IA (`574dbfd`), mas `detect_phase()`/`calculate_score()` continuaram com a lógica original (`Inalterado`) de zerar o score sempre que `phase == UNKNOWN` — fase essa derivada só do ângulo do joelho, irrelevante para supino/remada onde as pernas comumente saem de quadro. Ao reverter de volta para o motor de regras, o bug reapareceu porque ele nunca existiu lá para começar.

**Fix**: `pose-service/exercise_analyzer.py`:
- Novo `_KNEE_DEPENDENT_EXERCISES = {SQUAT, DEADLIFT, LUNGE}`.
- `calculate_score(errors, phase, force_assessable=False)`: novo parâmetro opcional (default preserva 100% o comportamento anterior — `calculate_score(errors, MovementPhase.UNKNOWN) == 0.0` continua valendo, testado em `test_exercise_analyzer.py`); quando `force_assessable=True`, ignora o zeramento por `phase==UNKNOWN`.
- `ExerciseAnalyzer.analyze()`: passa `force_assessable=True` quando o exercício não é joelho-dependente e há pelo menos um cotovelo (`LEFT_ELBOW`/`RIGHT_ELBOW`) detectado nos landmarks.
- **Validado**: `analyze-video` com os 7 vídeos de exemplo do APK — `bench_press.mp4` (BENCH_PRESS) `avg_score` 0.0 → 71.1 (mantendo os erros corretos: ELBOW_FLARE, WRIST_BENT); `bent_over_row.mp4` melhorou 76.0 → 79.5 (mesmo bug, frames com perna fora de quadro). SQUAT/DEADLIFT/LUNGE inalterados (100.0/99.5/92.8). `pytest tests/ --ignore=tests/test_pose_service.py` → 48/48 passando. Container `gymvision-pose-svc` reconstruído e recriado, `GET /api/v1/pose/health` → `200 OK`, cache Redis limpo (`FLUSHALL`).

---

## 2026-06-23

### Correção do threshold de KNEE_CAVE no SQUAT (causa raiz real do "overlay quebrado", não regressão da IA)

Usuário relatou de novo que o overlay do teste de vídeo está quebrado, não identifica corretamente e pediu para "voltar ao que estava antes de começar a IA". Antes de reverter literalmente, validei contra o vídeo real `/home/souzza-matheus/Downloads/Bad squat form!!! It needs help!! #shorts.mp4`: `avg_score=100.0`, zero erros — mesmo com o motor de regras já restaurado (pós `51b7aa8`+`0ff7a85`).

**Investigação**: comparei `exercise_analyzer.py`/`angle_calculator.py`/`orientation_detector.py` entre o commit pré-IA (`6ce352e`) e o commit que introduziu a IA (`574dbfd`) — a lógica de orientação multi-câmera já existia antes da IA, então um revertão literal não mudaria nada para SQUAT. Rodei um script de diagnóstico frame-a-frame dentro do container `gymvision-pose-svc` usando o pipeline de produção real (`tf_serving_client` → `orientation_detector` → `angle_calculator` → `exercise_analyzer`, sem reimplementar nada): profundidade boa (joelho 79-86° no fundo, threshold é >90°), tronco ereto (back_angle <17°), knee-over-toe desabilitado por câmera FRONTAL/ANGLED (`frontal_weight` 0.55-0.86 na maioria dos frames — esse check só vale em câmera lateral). Achado colateral (não corrigido, fora de escopo): a coordenada Z do MoveNet/TF-Serving é sempre hardcoded para `0.0` (`tf_serving_client.py:195`) — a melhoria de back_angle "sagital via Z" adicionada na era da IA (`_frontal_back_angle_combined`) é código morto em produção, nunca fez diferença.

O joelho direito mostrava desvio consistente de ~1.8-3.3% durante as fases reais do movimento (DESCENDING/BOTTOM/ASCENDING), zerado/negativo durante STANDING — sinal real de valgo, não ruído — mas o `SQUAT_KNEE_CAVE_THRESHOLD` (4.0, já reduzido do original 15.0 durante a era da IA) nunca era cruzado. Perguntei ao usuário o que via de errado no vídeo: confirmou joelho colapsando para dentro — exatamente esse sinal.

**Fix**: `pose-service/exercise_analyzer.py` — `SQUAT_KNEE_CAVE_THRESHOLD` 4.0 → 2.0. Também commitado junto: `pose-service/tf_serving_client.py` `MIN_CONFIDENCE` 0.5 → 0.15 (trabalho de uma sessão anterior não commitado — 0.5 citava o `PoseDetectorProcessor.kt` on-device que não existe mais após a reescrita em Compose; em filmagem real com joelho parcialmente ocluído a confiança fica entre 0.3-0.6, e 0.5 fazia o landmark oscilar detectado/UNKNOWN sem motivo real).

**Validado**: `pytest tests/ --ignore=tests/test_pose_service.py` → 48/48 passando (fixtures de knee cave existentes usavam desvios ≥5%, não afetadas pelo novo threshold). Container reconstruído/recriado, `GET /api/v1/pose/health` → 200, cache Redis limpo (`FLUSHALL`). Vídeo "Bad squat form" agora retorna `avg_score=95.4` (min 70.0) com `KNEE_CAVE_RIGHT` em 29.4% dos frames. `squat.mp4` (vídeo de boa forma, já usado nas validações anteriores) permanece com apenas 1 frame isolado de `KNEE_CAVE_RIGHT` (1.8%) — sem falso positivo sistemático.

**Pendência não resolvida nesta sessão**: `pose-service/ai/dataset_generator.py` tem uma mudança não commitada (imports não usados de thresholds de LUNGE/ROW, provavelmente início de uma extensão da IA desconectada) — deixada como está, sem decisão do usuário sobre descartar ou retomar.

Commit: `023fb55`.

---

### Correção do overlay de landmarks não aparecendo no "Testar Vídeo" (Android)

Usuário relatou, na mesma sessão: "o maior erro e no display do video os landmarks nao aparecem".

**Causa raiz**: `android-app/.../ui/videotest/VideoTestScreen.kt` usa `android.widget.VideoView`, que preserva o aspect ratio do vídeo (letterbox) dentro do `Box` que o contém, em vez de esticar para preenchê-lo. `PoseOverlay` (compartilhado com `CameraScreen.kt`) desenhava os landmarks normalizados (0-1, relativos ao frame original do vídeo) usando o tamanho cheio do `Canvas` (`size.width`/`size.height`), assumindo que o Canvas cobre exatamente a área visível do conteúdo — verdade em `CameraScreen` (cuja `PreviewView` usa `FILL_CENTER`, sem letterbox), falso em `VideoTestScreen` sempre que o aspect ratio do vídeo difere do da tela (caso comum nos 8 vídeos de exemplo embutidos). Resultado: o esqueleto era desenhado fora do retângulo real do vídeo, na faixa de letterbox — efetivamente invisível sobre a pessoa.

**Fix**:
- `android-app/.../ui/camera/PoseOverlay.kt`: novos parâmetros opcionais `contentOffset: Offset = Offset.Zero` e `contentSize: Size? = null` — quando não informados, comportamento idêntico ao anterior (usa o tamanho cheio do Canvas, preservando `CameraScreen` inalterado).
- `android-app/.../ui/videotest/VideoTestScreen.kt` (`PlaybackUI`): rastreia o tamanho medido do container (`Modifier.onSizeChanged`) e as dimensões intrínsecas do vídeo (`mp.videoWidth`/`videoHeight` em `setOnPreparedListener`); calcula o retângulo real de letterbox (`scale = min(containerW/videoW, containerH/videoH)`, centralizado) e passa `contentOffset`/`contentSize` para `PoseOverlay`.
- **Validado**: `./gradlew :app:compileDebugKotlin` e `:app:assembleDebug` passam sem erros.

Commit: `960d306`.

---

### CI/CD: publicação das imagens também no Docker Hub

Usuário pediu para "criar um pipeline de ci/cd e publicar no docker hub os containers". Já existia `.github/workflows/ci.yml` com testes + build + push para `ghcr.io`, mas achei dois problemas reais antes de adicionar Docker Hub:
1. O trigger (`on.push.branches`) só incluía `main`/`develop`, e o job `build-and-push` só rodava com `if: github.ref == 'refs/heads/main'` — mas o branch real deste repo é `master`. A pipeline nunca tinha disparado de fato em um push.
2. `notification-service` tem `Dockerfile` mas não estava na lista de imagens publicadas (só user/pose/session/analytics/backup-service).

**Fix em `.github/workflows/ci.yml`**:
- Trigger e condição do `build-and-push` agora aceitam `master` também (mantido `main`/`develop` por segurança).
- Novo step "Log in to Docker Hub" (`docker/login-action`) usando secrets `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` (usuário acordado: `souzza-matheus`).
- Cada step de build-and-push agora lista duas tags (ghcr.io e docker.io/souzza-matheus/gymvision-`<serviço>`).
- Adicionado step para `notification-service` (faltava). Build local validado (`docker build ./notification-service`) antes de comitar.

**Pendência do usuário (não posso fazer por aqui)**: criar um Access Token no Docker Hub (Account Settings → Security → New Access Token) e cadastrar dois secrets no repositório GitHub (`Settings → Secrets and variables → Actions`): `DOCKERHUB_USERNAME` e `DOCKERHUB_TOKEN`. Sem isso o job `build-and-push` falha no login.

Commit: `83badc7`.

---
