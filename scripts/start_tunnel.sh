#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# BabyTrack — Start API + UI + Cloudflare Tunnel
# Usage: ./scripts/start_tunnel.sh
# ──────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${CYAN}Arrêt des services...${NC}"
    # Kill child processes
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

# Wait for API with retries (Supabase connection can be slow)
echo -e "${CYAN}  Attente de l'API...${NC}"
for i in {1..15}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Check API is alive
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

# Wait for UI with retries
echo -e "${CYAN}  Attente de l'UI...${NC}"
for i in {1..10}; do
    if curl -sf http://localhost:8501 > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Check UI is alive
if ! curl -sf http://localhost:8501 > /dev/null 2>&1; then
    echo "❌ L'UI n'a pas démarré. Vérifiez les logs."
    kill "$API_PID" 2>/dev/null || true
    kill "$UI_PID"  2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✅ UI OK${NC}"

# ── Start Cloudflare Tunnel (quick tunnel — no account needed) ──
echo ""
echo -e "${CYAN}▶ Lancement du tunnel Cloudflare...${NC}"

TUNNEL_LOG="/tmp/babytrack_tunnel.log"
cloudflared tunnel --url http://localhost:8501 2>"$TUNNEL_LOG" &
TUN_PID=$!

# Wait for tunnel URL
echo -e "${CYAN}  Attente de l'URL publique...${NC}"
for i in {1..15}; do
    URL=$(grep -o 'https://[^ ]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
    if [[ -n "$URL" ]]; then
        break
    fi
    sleep 1
done

if [[ -n "$URL" ]]; then
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  🌍 BabyTrack est accessible sur :${NC}"
    echo -e "${GREEN}  $URL${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
else
    echo -e "${CYAN}  URL non détectée. Vérifiez $TUNNEL_LOG${NC}"
fi

echo -e "${CYAN}Ctrl+C pour tout arrêter${NC}"
echo ""

# Wait for all background processes
wait
