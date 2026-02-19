#!/usr/bin/env bash
# mcp_helper.sh — Shared functions for MCP test scripts
# Source this file: source "$(dirname "$0")/mcp_helper.sh"

set -euo pipefail

MCP_URL="${MCP_URL:-http://localhost:3000/mcp}"
_REQ_ID=0

# ── Colors ──────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Health check ────────────────────────────────────────────────
check_health() {
  echo -e "${CYAN}Checking server health...${NC}"
  if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Server is healthy${NC}"
  else
    echo -e "${RED}✗ Server not reachable at http://localhost:3000${NC}"
    echo "  Start it with: docker compose up  OR  uv run api-agent"
    exit 1
  fi
}

# ── Initialize MCP session ──────────────────────────────────────
# Usage: init_session <TARGET_URL> <API_TYPE> [BASE_URL]
init_session() {
  local target_url="$1"
  local api_type="$2"
  local base_url="${3:-}"

  _REQ_ID=$((_REQ_ID + 1))

  local extra_headers=""
  if [ -n "$base_url" ]; then
    extra_headers="-H \"X-Base-URL: $base_url\""
  fi

  echo -e "${CYAN}Initializing MCP session...${NC}"
  echo -e "  Target: ${BOLD}$target_url${NC}"
  echo -e "  Type:   ${BOLD}$api_type${NC}"
  [ -n "$base_url" ] && echo -e "  Base:   ${BOLD}$base_url${NC}"

  local tmp_headers
  tmp_headers=$(mktemp)

  local cmd="curl -s -D '$tmp_headers' -X POST '$MCP_URL' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H 'X-Target-URL: $target_url' \
    -H 'X-API-Type: $api_type'"
  [ -n "$base_url" ] && cmd="$cmd -H 'X-Base-URL: $base_url'"
  cmd="$cmd -d '{
    \"jsonrpc\": \"2.0\",
    \"id\": $_REQ_ID,
    \"method\": \"initialize\",
    \"params\": {
      \"protocolVersion\": \"2025-03-26\",
      \"capabilities\": {},
      \"clientInfo\": {\"name\": \"test-script\", \"version\": \"1.0\"}
    }
  }'"

  eval "$cmd" > /dev/null

  SESSION_ID=$(grep -i "mcp-session-id" "$tmp_headers" | awk '{print $2}' | tr -d '\r')
  rm -f "$tmp_headers"

  if [ -z "$SESSION_ID" ]; then
    echo -e "${RED}✗ Failed to get session ID${NC}"
    exit 1
  fi

  echo -e "${GREEN}✓ Session: ${SESSION_ID}${NC}"
  echo ""

  # Export for use in caller
  export SESSION_ID
  export TARGET_URL="$target_url"
  export API_TYPE="$api_type"
  export BASE_URL="${base_url:-}"
}

# ── List tools ──────────────────────────────────────────────────
list_tools() {
  _REQ_ID=$((_REQ_ID + 1))

  local cmd="curl -s -X POST '$MCP_URL' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H 'Mcp-Session-Id: $SESSION_ID' \
    -H 'X-Target-URL: $TARGET_URL' \
    -H 'X-API-Type: $API_TYPE'"
  [ -n "${BASE_URL:-}" ] && cmd="$cmd -H 'X-Base-URL: $BASE_URL'"
  cmd="$cmd -d '{
    \"jsonrpc\": \"2.0\",
    \"id\": $_REQ_ID,
    \"method\": \"tools/list\"
  }'"

  echo -e "${CYAN}Discovering tools...${NC}"
  eval "$cmd" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        data = json.loads(line[5:])
        tools = data.get('result', {}).get('tools', [])
        print(f'Found {len(tools)} tool(s):')
        for t in tools:
            print(f'  • {t[\"name\"]}')
"
  echo ""
}

# ── Ask a natural language question ─────────────────────────────
# Usage: ask <tool_name> <question>
ask() {
  local tool_name="$1"
  local question="$2"
  _REQ_ID=$((_REQ_ID + 1))

  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}Q: $question${NC}"
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  # Escape double quotes in question for JSON
  local escaped_q
  escaped_q=$(echo "$question" | sed 's/"/\\"/g')

  local cmd="curl -s -X POST '$MCP_URL' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H 'Mcp-Session-Id: $SESSION_ID' \
    -H 'X-Target-URL: $TARGET_URL' \
    -H 'X-API-Type: $API_TYPE'"
  [ -n "${BASE_URL:-}" ] && cmd="$cmd -H 'X-Base-URL: $BASE_URL'"
  cmd="$cmd -d '{
    \"jsonrpc\": \"2.0\",
    \"id\": $_REQ_ID,
    \"method\": \"tools/call\",
    \"params\": {
      \"name\": \"$tool_name\",
      \"arguments\": {
        \"question\": \"$escaped_q\"
      }
    }
  }'"

  eval "$cmd" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            data = json.loads(line[5:])
            result = data.get('result', {})
            sc = result.get('structuredContent')
            content = result.get('content', [])
            if sc:
                # Pretty-print structured content
                d = sc.get('result', sc)
                if isinstance(d, dict):
                    answer = d.get('data', '')
                    calls = d.get('api_calls', d.get('queries', []))
                    error = d.get('error')
                    if answer:
                        print(f'\n\033[0;32m{answer[:3000]}\033[0m')
                    if calls:
                        print(f'\n\033[0;36mAPI calls made: {len(calls)}\033[0m')
                        for c in calls[:5]:
                            if isinstance(c, dict):
                                m = c.get('method', c.get('query','')[:60])
                                p = c.get('path', '')
                                ok = c.get('success', '?')
                                print(f'  → {m} {p} (success={ok})')
                    if error:
                        print(f'\n\033[0;31mError: {error}\033[0m')
                else:
                    print(str(d)[:3000])
            elif content:
                for c in content:
                    txt = c.get('text', '')
                    print(f'\n\033[0;32m{txt[:3000]}\033[0m')
        except Exception as e:
            print(f'Parse error: {e}')
"
  echo ""
}

# ── Execute a direct API call ───────────────────────────────────
# Usage: execute <tool_name> <json_arguments>
execute() {
  local tool_name="$1"
  local arguments="$2"
  _REQ_ID=$((_REQ_ID + 1))

  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}Execute: $tool_name${NC}"
  echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

  local payload
  payload=$(echo "$arguments" | python3 -c "
import sys, json
args = json.load(sys.stdin)
payload = {
    'jsonrpc': '2.0',
    'id': $_REQ_ID,
    'method': 'tools/call',
    'params': {
        'name': '$tool_name',
        'arguments': args
    }
}
print(json.dumps(payload))
")

  local cmd="curl -s -X POST '$MCP_URL' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -H 'Mcp-Session-Id: $SESSION_ID' \
    -H 'X-Target-URL: $TARGET_URL' \
    -H 'X-API-Type: $API_TYPE'"
  [ -n "${BASE_URL:-}" ] && cmd="$cmd -H 'X-Base-URL: $BASE_URL'"
  cmd="$cmd -d '$payload'"

  eval "$cmd" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        try:
            data = json.loads(line[5:])
            sc = data.get('result', {}).get('structuredContent', {})
            content = data.get('result', {}).get('content', [])
            if sc:
                print(json.dumps(sc, indent=2, ensure_ascii=False)[:3000])
            elif content:
                for c in content:
                    print(c.get('text', '')[:3000])
        except Exception as e:
            print(f'Parse error: {e}')
"
  echo ""
}
