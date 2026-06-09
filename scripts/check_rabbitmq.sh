#!/usr/bin/env bash
# check_rabbitmq.sh — Verifica status das filas do GymVision no RabbitMQ
# Uso: bash scripts/check_rabbitmq.sh

RABBIT="http://localhost:15672"
AUTH="gymvision:gymvision123"

check_queue() {
  local queue=$1
  echo "─── $queue"
  curl -s -u "$AUTH" "$RABBIT/api/queues/%2F/$(python3 -c "import urllib.parse; print(urllib.parse.quote('$queue'))")" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    pub = d.get('message_stats', {}).get('publish', 0)
    dlv = d.get('message_stats', {}).get('deliver_get', 0)
    print(f'  mensagens na fila  : {d.get(\"messages\", 0)}  (0 = consumido com sucesso)')
    print(f'  consumers ativos   : {d.get(\"consumers\", 0)}')
    print(f'  total publicadas   : {pub}')
    print(f'  total consumidas   : {dlv}')
except Exception as e:
    print(f'  erro: {e}')
"
  echo ""
}

echo "=============================="
echo " RabbitMQ — Status das Filas"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================="
echo ""

check_queue "gym.alert.created"
check_queue "gym.exercise.result"
check_queue "gym.session.ended"

echo "────────────────────────────────"
echo "Management UI: http://localhost:15672"
echo "Login: gymvision / gymvision123"
