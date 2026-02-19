#!/usr/bin/env bash
# test_petstore.sh — Test Petstore REST API (OpenAPI 3.0) via MCP
#
# Usage:
#   ./scripts/test_petstore.sh
#
# Requires: API Agent running at http://localhost:3000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/mcp_helper.sh"

# ── Config ──────────────────────────────────────────────────────
SPEC_URL="https://petstore3.swagger.io/api/v3/openapi.json"
API_BASE="https://petstore3.swagger.io/api/v3"
QUERY_TOOL="petstore3_swagger_query"
EXEC_TOOL="petstore3_swagger_execute"

# ── Setup ───────────────────────────────────────────────────────
check_health
init_session "$SPEC_URL" "rest" "$API_BASE"
list_tools

# ── Natural Language Queries ────────────────────────────────────

ask "$QUERY_TOOL" \
  "What endpoints are available in this API? List them grouped by category."

ask "$QUERY_TOOL" \
  "Get the current store inventory. Show all status codes and quantities."

ask "$QUERY_TOOL" \
  "Get me the details of pet with ID 1. Show name, status, category."

ask "$QUERY_TOOL" \
  "Look up the order with ID 3. Show the order details."

ask "$QUERY_TOOL" \
  "Get user info for username 'user1'."

# ── Direct Execute (bypasses LLM, calls API directly) ──────────

echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Direct API Execution Tests${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""

execute "$EXEC_TOOL" \
  '{"method": "GET", "path": "/store/inventory"}'

execute "$EXEC_TOOL" \
  '{"method": "GET", "path": "/pet/{petId}", "path_params": {"petId": 2}}'

execute "$EXEC_TOOL" \
  '{"method": "GET", "path": "/store/order/{orderId}", "path_params": {"orderId": 1}}'

echo -e "${GREEN}${BOLD}✓ Petstore test complete!${NC}"
