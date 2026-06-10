# Log de Ações do Claude

Este arquivo registra todas as ações realizadas pelo Claude no projeto `gymvision-complete`.

---

## 2026-06-09

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
