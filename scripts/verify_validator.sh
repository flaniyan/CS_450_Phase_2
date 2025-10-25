#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:3000}"

need() { command -v "$1" >/dev/null || { echo "Missing: $1"; exit 1; }; }
need curl
# jq is optional; we’ll fall back if missing
HAS_JQ=1; command -v jq >/dev/null || HAS_JQ=0

say() { echo -e "\n=== $* ==="; }
show() {
  if [ "$HAS_JQ" -eq 1 ]; then jq . <<<"$1"; else echo "$1"; fi
}

say "[0] Health"
HTTP=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/health" || true)
echo "health http=$HTTP"
if [ "$HTTP" != "200" ]; then
  echo "Health not 200 (got $HTTP). Check server/port/path."; exit 1
fi

say "[1] Timeout test (infinite loop)"
cat > /tmp/loop.py <<'PY'
i=0
while True: i+=1
# no RESULT set
PY
REQ=$(python - <<'P'
import json,sys
print(json.dumps({"script": open("/tmp/loop.py").read()}))
P
)
TIME_START=$(date +%s)
RESP=$(curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST "$BASE_URL/validate" \
  -H 'Content-Type: application/json' -d "$REQ" || true)
TIME_END=$(date +%s)
DUR=$((TIME_END - TIME_START))
BODY="${RESP%HTTP_STATUS=*}"
CODE="${RESP##*HTTP_STATUS=}"
echo "elapsed=${DUR}s code=${CODE}"
show "$BODY"

say "[2] Memory cap test"
cat > /tmp/mem_bomb.py <<'PY'
X=[0]*50_000_000
# no RESULT set
PY
REQ=$(python - <<'P'
import json
print(json.dumps({"script": open("/tmp/mem_bomb.py").read()}))
P
)
RESP=$(curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST "$BASE_URL/validate" \
  -H 'Content-Type: application/json' -d "$REQ" || true)
BODY="${RESP%HTTP_STATUS=*}"; CODE="${RESP##*HTTP_STATUS=}"
echo "code=${CODE}"
show "$BODY"

say "[3] Concurrency test (5 requests; expect queueing to your MAX_WORKERS)"
for i in 1 2 3 4 5; do
  {
    curl -sS -X POST "$BASE_URL/validate" -H 'Content-Type: application/json' \
      -d '{"script":"RESULT={\"ok\":True}"}' > /dev/null || true
  } &
done
wait
echo "concurrency burst finished"

say "[4] Oversized script should be rejected fast"
python - <<'P' > /tmp/big.txt
print("A"*200001)
P
REQ=$(python - <<'P'
import json
print(json.dumps({"script": open("/tmp/big.txt").read()}))
P
)
RESP=$(curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST "$BASE_URL/validate" \
  -H 'Content-Type: application/json' -d "$REQ" || true)
BODY="${RESP%HTTP_STATUS=*}"; CODE="${RESP##*HTTP_STATUS=}"
echo "code=${CODE}"
show "$BODY"