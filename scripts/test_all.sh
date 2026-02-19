#!/usr/bin/env bash
# test_all.sh — Run all MCP API tests
#
# Usage:
#   ./scripts/test_all.sh           # Run all tests
#   ./scripts/test_all.sh petstore  # Run only petstore
#   ./scripts/test_all.sh countries # Run only countries
#   ./scripts/test_all.sh rickmorty # Run only rick & morty

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FILTER="${1:-all}"

BOLD='\033[1m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

run_test() {
  local name="$1"
  local script="$2"

  echo ""
  echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "${BOLD}║  Testing: $name${NC}"
  echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
  echo ""

  if bash "$script"; then
    echo -e "${GREEN}${BOLD}✓ $name — PASSED${NC}"
  else
    echo -e "${RED}${BOLD}✗ $name — FAILED (exit code: $?)${NC}"
  fi
  echo ""
}

# Health check first
echo -e "${CYAN}Checking server health...${NC}"
if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
  echo -e "${GREEN}✓ Server is healthy${NC}"
else
  echo -e "${RED}✗ Server not reachable. Start it first:${NC}"
  echo "  docker compose up  OR  uv run api-agent"
  exit 1
fi

case "$FILTER" in
  petstore)
    run_test "Petstore REST API (OpenAPI 3.0)" "$SCRIPT_DIR/test_petstore.sh"
    ;;
  countries)
    run_test "Countries GraphQL API" "$SCRIPT_DIR/test_countries.sh"
    ;;
  rickmorty)
    run_test "Rick & Morty GraphQL API" "$SCRIPT_DIR/test_rickmorty.sh"
    ;;
  all)
    run_test "Petstore REST API (OpenAPI 3.0)" "$SCRIPT_DIR/test_petstore.sh"
    run_test "Countries GraphQL API" "$SCRIPT_DIR/test_countries.sh"
    run_test "Rick & Morty GraphQL API" "$SCRIPT_DIR/test_rickmorty.sh"
    ;;
  *)
    echo "Usage: $0 [petstore|countries|rickmorty|all]"
    exit 1
    ;;
esac

echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  All tests complete!${NC}"
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════════════${NC}"
