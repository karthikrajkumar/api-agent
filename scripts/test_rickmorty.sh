#!/usr/bin/env bash
# test_rickmorty.sh — Test Rick & Morty GraphQL API via MCP
#
# Usage:
#   ./scripts/test_rickmorty.sh
#
# Requires: API Agent running at http://localhost:3000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/mcp_helper.sh"

# ── Config ──────────────────────────────────────────────────────
GRAPHQL_URL="https://rickandmortyapi.com/graphql"
QUERY_TOOL="rickandmortyapi_query"
EXEC_TOOL="rickandmortyapi_execute"

# ── Setup ───────────────────────────────────────────────────────
check_health
init_session "$GRAPHQL_URL" "graphql"
list_tools

# ── Natural Language Queries ────────────────────────────────────

ask "$QUERY_TOOL" \
  "How many characters, episodes, and locations are there in total?"

ask "$QUERY_TOOL" \
  "List all dead human characters. Show name and last known location."

ask "$QUERY_TOOL" \
  "Which episodes aired in 2015? Show name and air date."

ask "$QUERY_TOOL" \
  "Show all locations of type Planet with their dimension."

ask "$QUERY_TOOL" \
  "Count characters by status (Alive, Dead, unknown). Show status and count."

# ── Direct Execute (raw GraphQL) ───────────────────────────────

echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Direct GraphQL Execution Tests${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""

execute "$EXEC_TOOL" \
  '{"query": "{ episodes { info { count } } }"}'

execute "$EXEC_TOOL" \
  '{"query": "{ characters(filter: { species: \"Human\", status: \"Dead\" }) { info { count } results { name } } }"}'

execute "$EXEC_TOOL" \
  '{"query": "{ locations(filter: { type: \"Planet\" }) { results { name dimension } } }"}'

echo -e "${GREEN}${BOLD}✓ Rick & Morty test complete!${NC}"
