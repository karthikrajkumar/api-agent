#!/usr/bin/env bash
# test_countries.sh — Test Countries GraphQL API via MCP
#
# Usage:
#   ./scripts/test_countries.sh
#
# Requires: API Agent running at http://localhost:3000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/mcp_helper.sh"

# ── Config ──────────────────────────────────────────────────────
GRAPHQL_URL="https://countries.trevorblades.com/graphql"
QUERY_TOOL="countries_trevorblades_query"
EXEC_TOOL="countries_trevorblades_execute"

# ── Setup ───────────────────────────────────────────────────────
check_health
init_session "$GRAPHQL_URL" "graphql"
list_tools

# ── Natural Language Queries ────────────────────────────────────

ask "$QUERY_TOOL" \
  "List all countries in Asia with their name, capital, and currency."

ask "$QUERY_TOOL" \
  "Which countries use the Euro (EUR) as currency? Just list their names."

ask "$QUERY_TOOL" \
  "What languages are spoken in India?"

ask "$QUERY_TOOL" \
  "How many countries are in Africa vs Europe vs Asia? Show continent name and count."

ask "$QUERY_TOOL" \
  "What country has the phone code +91? Show all details."

ask "$QUERY_TOOL" \
  "List all South American countries that speak Spanish."

# ── Direct Execute (raw GraphQL) ───────────────────────────────

echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Direct GraphQL Execution Tests${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
echo ""

execute "$EXEC_TOOL" \
  '{"query": "{ continents { name code } }"}'

execute "$EXEC_TOOL" \
  '{"query": "{ country(code: \"IN\") { name capital currency languages { name } } }"}'

execute "$EXEC_TOOL" \
  '{"query": "{ countries(filter: { continent: { eq: \"EU\" } }) { name emoji capital } }"}'

echo -e "${GREEN}${BOLD}✓ Countries test complete!${NC}"
