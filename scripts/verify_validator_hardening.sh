#!/usr/bin/env bash
set -euo pipefail

base=${BASE_URL:-http://localhost:3000}

echo "[1] Timeout test"
cat > /tmp/loop.py <<'PY'
i=0
while True: i+=1
PY
script_content=$(python3 -c 'import json; print(json.dumps(open("/tmp/loop.py").read()))')
time curl -s -X POST "$base/validate" -H 'Content-Type: application/json' \
  -d "{\"script\": $script_content}" | jq .

echo "[2] Memory cap test"
cat > /tmp/mem_bomb.py <<'PY'
X=[0]*50_000_000
PY
script_content=$(python3 -c 'import json; print(json.dumps(open("/tmp/mem_bomb.py").read()))')
curl -s -X POST "$base/validate" -H 'Content-Type: application/json' \
  -d "{\"script\": $script_content}" | jq .

echo "[3] Concurrency test"
seq 1 5 | xargs -I{} -P 5 curl -s -X POST "$base/validate" -H 'Content-Type: application/json' \
  -d '{"script":"RESULT={\"ok\":True}"}' >/dev/null && echo "OK"

echo "[4] Input bounds"
python3 - <<'P' > /tmp/big.txt
print("A"*200001)
P
script_content=$(python3 -c 'import json; print(json.dumps(open("/tmp/big.txt").read()))')
curl -s -X POST "$base/validate" -H 'Content-Type: application/json' \
  -d "{\"script\": $script_content}" | jq .