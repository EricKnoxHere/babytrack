#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# BabyTrack — Start API + UI + ngrok tunnel
# Usage: ./scripts/start_tunnel.sh
# URL fixe: https://primaeval-thurman-overgrievously.ngrok-free.dev
# ──────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NGROK_DOMAIN="primaeval-thurman-overgrievously.ngrok-free.dev"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${CYAN}Arrêt des services...${NC}"
    kill "$API_PID" 2>/dev/null || true
    kill "$UI_PID"  2>/dev/null || true
    kill "$TUN_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
    wait "$UI_PID"  2>/dev/null || true
    wait "$TUN_PID" 2>/dev/null || true
    echo -e "${GREEN}Tout est arrêté. À bientôt !${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Kill anything already on our ports ──
echo -e "${CYAN}Nettoyage des ports 8000 & 8501...${NC}"
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:8501 2>/dev/null | xargs kill -9 2>/dev/null || true
pkill -f "ngrok http" 2>/dev/null || true
sleep 1

# ── Use python -m to bypass stale shebangs ──
PYTHON="$ROOT/.venv/bin/python"
cd "$ROOT"

# ── Load .env ──
if [[ -f "$ROOT/.env" ]]; then
    set -a
    source "$ROOT/.env"
    set +a
fi

# ── Start API ──
echo -e "${GREEN}▶ Démarrage de l'API (port 8000)...${NC}"
"$PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo -e "${CYAN}  Attente de l'API...${NC}"
for i in {1..15}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ L'API n'a pas démarré. Vérifiez les logs."
    kill "$API_PID" 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✅ API OK${NC}"

# ── Start Streamlit UI ──
echo -e "${GREEN}▶ Démarrage de l'UI Streamlit (port 8501)...${NC}"
"$PYTHON" -m streamlit run ui/app.py --server.port 8501 --server.headless true &
UI_PID=$!

echo -e "${CYAN}  Attente de l'UI...${NC}"
for i in {1..10}; do
    if curl -sf http://localhost:8501 > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -sf http://localhost:8501 > /dev/null 2>&1; then
    echo "❌ L'UI n'a pas démarré. Vérifiez les logs."
    kill "$API_PID" 2>/dev/null || true
    kill "$UI_PID"  2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✅ UI OK${NC}"

# ── Start ngrok tunnel (static domain — URL never changes) ──
echo ""
echo -e "${CYAN}▶ Lancement du tunnel ngrok...${NC}"
ngrok http 8501 --domain="$NGROK_DOMAIN" --log=stdout > /tmp/babytrack_ngrok.log 2>&1 &
TUN_PID=$!
sleep 3

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  🌍 BabyTrack est accessible sur :${NC}"
echo -e "${GREEN}  https://$NGROK_DOMAIN${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}Ctrl+C pour tout arrêter${NC}"
echo ""

# Wait for all background processes
wait
