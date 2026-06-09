# Log de Ações do Claude

Este arquivo registra todas as ações realizadas pelo Claude no projeto `gymvision-complete`.

---

## 2026-06-09

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
