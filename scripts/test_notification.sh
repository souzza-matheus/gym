#!/usr/bin/env bash
# test_notification.sh — Testa o pipeline completo de notificação do GymVision
# Uso: ./scripts/test_notification.sh

set -euo pipefail

BASE_URL="http://localhost:8090"
POSE_DIRECT="http://localhost:8083"
NOTIFY_URL="http://localhost:8085"
RABBITMQ_URL="http://localhost:15672"
IMAGE="/home/souzza-matheus/Downloads/download.jpeg"
EMAIL="teste@gymvision.com"
PASSWORD="senha123"
STUDENT_ID="776cc303-2a3b-47b7-b129-ce1f18a5d370"
ACADEMY_ID="00000000-0000-0000-0000-000000000001"
THRESHOLD_TEST=10
THRESHOLD_DEFAULT=45

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

sep() { echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }
header() { sep; echo -e "${BOLD}$1${NC}"; sep; }

# ── 0. Log de ações anteriores ────────────────────────────────────────────────
header "📋 HISTÓRICO DE AÇÕES (ACTIONS_LOG.md)"
LOG_FILE="$(dirname "$0")/../ACTIONS_LOG.md"
if [[ -f "$LOG_FILE" ]]; then
    cat "$LOG_FILE"
else
    echo "Arquivo ACTIONS_LOG.md não encontrado."
fi

echo ""
header "🚀 INICIANDO TESTE DE NOTIFICAÇÃO"
echo "Imagem   : $IMAGE"
echo "Threshold: ${THRESHOLD_TEST}° (padrão: ${THRESHOLD_DEFAULT}°)"
echo "back_angle detectada na imagem: ~11.64° → vai ultrapassar o threshold de ${THRESHOLD_TEST}°"
echo ""

# ── 1. Login ──────────────────────────────────────────────────────────────────
header "1️⃣  OBTENDO TOKEN JWT"
TOKEN=$(curl -sf -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['accessToken'])")

if [[ -z "$TOKEN" ]]; then
  echo -e "${RED}ERRO: Não foi possível obter token. Verifique se os serviços estão rodando.${NC}"
  exit 1
fi
echo -e "${GREEN}Token obtido.${NC}"

# ── 2. Threshold de teste ──────────────────────────────────────────────────────
header "2️⃣  APLICANDO THRESHOLD DE TESTE (${THRESHOLD_TEST}°)"
RULE_RESP=$(curl -sf -X PUT \
  "$POSE_DIRECT/api/v1/pose/rules/SQUAT/squat_back_angle_max?threshold=${THRESHOLD_TEST}" \
  -H "Authorization: Bearer $TOKEN")
echo "$RULE_RESP" | python3 -m json.tool
echo -e "${YELLOW}Threshold squat_back_angle_max → ${THRESHOLD_TEST}° (BACK_NOT_STRAIGHT dispara quando > ${THRESHOLD_TEST}°)${NC}"

# ── 3. Análise ────────────────────────────────────────────────────────────────
header "3️⃣  ENVIANDO FRAME PARA ANÁLISE"
SESSION="test-notif-$(date +%s)"
echo "session_id: $SESSION"
echo ""

ANALYSIS=$(curl -sf -X POST "$BASE_URL/api/v1/pose/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -F "frame=@$IMAGE" \
  -F "exercise_type=SQUAT" \
  -F "session_id=$SESSION" \
  -F "student_id=$STUDENT_ID" \
  -F "academy_id=$ACADEMY_ID" \
  -F "frame_seq=1")

echo "$ANALYSIS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
a = d['analysis']
angles = a['joint_angles']

print(f'  landmarks      : {d[\"landmark_count\"]}')
print(f'  inference_ms   : {d[\"inference_ms\"]}ms')
print(f'  fase           : {a[\"phase\"]}')
print(f'  score          : {a[\"score\"]}')
print(f'  back_angle     : {angles[\"back_angle\"]}°')
print(f'  left_knee      : {angles[\"left_knee\"]}°')
print()

if a['has_alert']:
    print('  \033[0;31m⚠ ALERTA DISPARADO:\033[0m')
    for e in a['errors']:
        risk_color = '\033[0;31m' if e['risk_level'] == 'HIGH' else '\033[1;33m'
        print(f'    {risk_color}[{e[\"risk_level\"]}]\033[0m {e[\"error_type\"]} — {e[\"description\"]}')
else:
    print('  \033[0;32m✓ Nenhum alerta.\033[0m')
"

HAS_ALERT=$(echo "$ANALYSIS" | python3 -c "import sys,json; print(json.load(sys.stdin)['analysis']['has_alert'])")

# ── 4. Verificação RabbitMQ ───────────────────────────────────────────────────
header "4️⃣  VERIFICANDO FILA RabbitMQ (gym.alert.created)"
sleep 1
QUEUE=$(curl -sf -u gymvision:gymvision123 \
  "$RABBITMQ_URL/api/queues/%2F/gym.alert.created" 2>/dev/null || echo "{}")

echo "$QUEUE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    msgs       = d.get('messages', 0)
    consumers  = d.get('consumers', 0)
    stats      = d.get('message_stats', {})
    published  = stats.get('publish', {})
    pub_total  = published if isinstance(published, int) else published.get('rate', 'N/A')
    print(f'  mensagens na fila : {msgs} (0 = consumido com sucesso)')
    print(f'  consumers ativos  : {consumers}')
except:
    print('  RabbitMQ management inacessível')
" 2>/dev/null || echo "  (sem dados)"

# ── 5. Logs notification-service ──────────────────────────────────────────────
header "5️⃣  LOGS DO NOTIFICATION-SERVICE (últimos 30s)"
sleep 1
NOTIF_LOGS=$(docker logs gymvision-notify-svc --since 30s 2>&1 | grep -E "broadcast|alerta|alert|ERROR|WARN" || true)
if [[ -n "$NOTIF_LOGS" ]]; then
    echo "$NOTIF_LOGS"
else
    echo "  (sem atividade nos últimos 30s)"
fi

# ── 6. Status notification-service ───────────────────────────────────────────
header "6️⃣  STATUS DO NOTIFICATION-SERVICE"
curl -sf "$NOTIFY_URL/api/v1/notify/status" | python3 -m json.tool || echo "  (serviço inacessível)"

# ── 7. Resultado final ────────────────────────────────────────────────────────
header "7️⃣  RESULTADO FINAL"
if [[ "$HAS_ALERT" == "True" ]]; then
    echo -e "${GREEN}✅ PIPELINE COMPLETO: alerta detectado → publicado no RabbitMQ → consumido pelo notification-service → broadcast via WebSocket.${NC}"
else
    echo -e "${YELLOW}⚠ Nenhum alerta disparado. Verifique se a imagem contém uma pessoa visível.${NC}"
fi

# ── 8. Resetar threshold ──────────────────────────────────────────────────────
header "8️⃣  RESETANDO THRESHOLD PARA PADRÃO (${THRESHOLD_DEFAULT}°)"
RESET_RESP=$(curl -sf -X PUT \
  "$POSE_DIRECT/api/v1/pose/rules/SQUAT/squat_back_angle_max?threshold=${THRESHOLD_DEFAULT}" \
  -H "Authorization: Bearer $TOKEN")
echo "$RESET_RESP" | python3 -m json.tool
echo -e "${GREEN}Threshold restaurado para ${THRESHOLD_DEFAULT}°.${NC}"

sep
echo -e "${BOLD}Teste concluído.${NC}"
sep
