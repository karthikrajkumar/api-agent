# MCP Server Scripts

Ready-to-run scripts for calling natural language queries over API Agent MCP servers.

> **Prerequisites:** API Agent running at `http://localhost:3000` (via `uv run api-agent` or `docker compose up`)

---

## Table of Contents

1. [Petstore REST API](#1-petstore-rest-api)
2. [Rick & Morty GraphQL API](#2-rick--morty-graphql-api)
3. [Countries GraphQL API](#3-countries-graphql-api)
4. [Python Helper Script](#4-python-helper-script)
5. [Node.js Helper Script](#5-nodejs-helper-script)

---

## 1. Petstore REST API

**MCP Client Config:**
```json
{
  "mcpServers": {
    "petstore": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://petstore3.swagger.io/api/v3/openapi.json",
        "X-API-Type": "rest",
        "X-Base-URL": "https://petstore3.swagger.io/api/v3"
      }
    }
  }
}
```

### Bash — Initialize + Query

```bash
#!/usr/bin/env bash
# petstore_query.sh — Query the Petstore REST API via API Agent
set -euo pipefail

MCP_URL="http://localhost:3000/mcp"
TARGET_URL="https://petstore3.swagger.io/api/v3/openapi.json"
API_TYPE="rest"
BASE_URL="https://petstore3.swagger.io/api/v3"

# ── Initialize session ──────────────────────────────────────────
echo "Initializing session..."
SESSION=$(curl -s -D - -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Target-URL: $TARGET_URL" \
  -H "X-API-Type: $API_TYPE" \
  -H "X-Base-URL: $BASE_URL" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "petstore-script", "version": "1.0"}
    }
  }' 2>/dev/null | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r')

echo "Session: $SESSION"

# ── Helper function ─────────────────────────────────────────────
ask() {
  local question="$1"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Q: $question"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  curl -s -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $SESSION" \
    -H "X-Target-URL: $TARGET_URL" \
    -H "X-API-Type: $API_TYPE" \
    -H "X-Base-URL: $BASE_URL" \
    -d "$(printf '{
      "jsonrpc": "2.0",
      "id": %d,
      "method": "tools/call",
      "params": {
        "name": "petstore3_swagger_query",
        "arguments": {
          "question": "%s"
        }
      }
    }' "$RANDOM" "$question")" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        data = json.loads(line[5:])
        sc = data.get('result', {}).get('structuredContent')
        content = data.get('result', {}).get('content', [])
        if sc:
            print(json.dumps(sc, indent=2, ensure_ascii=False)[:2000])
        elif content:
            for c in content:
                print(c.get('text', '')[:2000])
"
}

# ── Ask questions ───────────────────────────────────────────────
ask "What endpoints are available in this API?"
ask "What pets are available for sale?"
ask "Show me pet with ID 1"
ask "What are the different pet statuses?"
ask "Show me the store inventory"
```

### Bash — Direct REST Execute

```bash
#!/usr/bin/env bash
# petstore_execute.sh — Execute specific REST calls on Petstore
set -euo pipefail

MCP_URL="http://localhost:3000/mcp"
TARGET_URL="https://petstore3.swagger.io/api/v3/openapi.json"

# Reuse session from above, or initialize a new one
SESSION="$1"  # Pass session ID as argument

if [ -z "$SESSION" ]; then
  echo "Usage: ./petstore_execute.sh <session-id>"
  echo "Run petstore_query.sh first to get a session ID."
  exit 1
fi

# ── GET /pet/findByStatus?status=available ──────────────────────
echo "Fetching available pets..."
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "X-Target-URL: $TARGET_URL" \
  -H "X-API-Type: rest" \
  -H "X-Base-URL: https://petstore3.swagger.io/api/v3" \
  -d '{
    "jsonrpc": "2.0",
    "id": 10,
    "method": "tools/call",
    "params": {
      "name": "petstore3_swagger_execute",
      "arguments": {
        "method": "GET",
        "path": "/pet/findByStatus",
        "query_params": {"status": "available"}
      }
    }
  }' 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    if line.strip().startswith('data:'):
        data = json.loads(line.strip()[5:])
        sc = data.get('result',{}).get('structuredContent',{})
        print(json.dumps(sc, indent=2, ensure_ascii=False)[:3000])
"

echo ""
echo "Fetching store inventory..."
# ── GET /store/inventory ────────────────────────────────────────
curl -s -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "X-Target-URL: $TARGET_URL" \
  -H "X-API-Type: rest" \
  -H "X-Base-URL: https://petstore3.swagger.io/api/v3" \
  -d '{
    "jsonrpc": "2.0",
    "id": 11,
    "method": "tools/call",
    "params": {
      "name": "petstore3_swagger_execute",
      "arguments": {
        "method": "GET",
        "path": "/store/inventory"
      }
    }
  }' 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    if line.strip().startswith('data:'):
        data = json.loads(line.strip()[5:])
        sc = data.get('result',{}).get('structuredContent',{})
        print(json.dumps(sc, indent=2, ensure_ascii=False)[:3000])
"
```

---

## 2. Rick & Morty GraphQL API

**MCP Client Config:**
```json
{
  "mcpServers": {
    "rickandmorty": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://rickandmortyapi.com/graphql",
        "X-API-Type": "graphql"
      }
    }
  }
}
```

### Bash — Initialize + Query

```bash
#!/usr/bin/env bash
# rickandmorty_query.sh — Query Rick & Morty GraphQL API via API Agent
set -euo pipefail

MCP_URL="http://localhost:3000/mcp"
TARGET_URL="https://rickandmortyapi.com/graphql"
API_TYPE="graphql"

# ── Initialize session ──────────────────────────────────────────
echo "Initializing session..."
SESSION=$(curl -s -D - -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Target-URL: $TARGET_URL" \
  -H "X-API-Type: $API_TYPE" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "rickmorty-script", "version": "1.0"}
    }
  }' 2>/dev/null | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r')

echo "Session: $SESSION"

# ── Helper function ─────────────────────────────────────────────
ask() {
  local question="$1"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Q: $question"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  curl -s -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $SESSION" \
    -H "X-Target-URL: $TARGET_URL" \
    -H "X-API-Type: $API_TYPE" \
    -d "$(printf '{
      "jsonrpc": "2.0",
      "id": %d,
      "method": "tools/call",
      "params": {
        "name": "rickandmortyapi_query",
        "arguments": {
          "question": "%s"
        }
      }
    }' "$RANDOM" "$question")" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        data = json.loads(line[5:])
        sc = data.get('result', {}).get('structuredContent')
        content = data.get('result', {}).get('content', [])
        if sc:
            print(json.dumps(sc, indent=2, ensure_ascii=False)[:2000])
        elif content:
            for c in content:
                print(c.get('text', '')[:2000])
"
}

# ── Ask questions ───────────────────────────────────────────────
ask "How many episodes are there in total?"
ask "List all dead human characters with their name and species"
ask "Count characters by species, show top 5"
ask "Show locations of type Planet with their dimension"
ask "Which episodes aired in 2015? Show name and air date"
```

### Bash — Direct GraphQL Execute

```bash
#!/usr/bin/env bash
# rickandmorty_execute.sh — Execute raw GraphQL queries
set -euo pipefail

MCP_URL="http://localhost:3000/mcp"
TARGET_URL="https://rickandmortyapi.com/graphql"
SESSION="$1"

if [ -z "$SESSION" ]; then
  echo "Usage: ./rickandmorty_execute.sh <session-id>"
  exit 1
fi

run_query() {
  local gql_query="$1"
  local desc="$2"
  echo ""
  echo "━━━ $desc ━━━"
  curl -s -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $SESSION" \
    -H "X-Target-URL: $TARGET_URL" \
    -H "X-API-Type: graphql" \
    -d "$(printf '{
      "jsonrpc": "2.0",
      "id": %d,
      "method": "tools/call",
      "params": {
        "name": "rickandmortyapi_execute",
        "arguments": {
          "query": "%s"
        }
      }
    }' "$RANDOM" "$gql_query")" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    if line.strip().startswith('data:'):
        data = json.loads(line.strip()[5:])
        sc = data.get('result',{}).get('structuredContent',{})
        print(json.dumps(sc, indent=2, ensure_ascii=False)[:2000])
"
}

run_query "{ episodes { info { count } } }" "Episode count"
run_query "{ characters(filter: {status: \\\"Dead\\\"}) { results { name species } } }" "Dead characters"
run_query "{ locations(filter: {type: \\\"Planet\\\"}) { results { name dimension } } }" "Planet locations"
```

---

## 3. Countries GraphQL API

**MCP Client Config:**
```json
{
  "mcpServers": {
    "countries": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://countries.trevorblades.com/graphql",
        "X-API-Type": "graphql"
      }
    }
  }
}
```

### Bash — Initialize + Query

```bash
#!/usr/bin/env bash
# countries_query.sh — Query Countries GraphQL API via API Agent
set -euo pipefail

MCP_URL="http://localhost:3000/mcp"
TARGET_URL="https://countries.trevorblades.com/graphql"
API_TYPE="graphql"

# ── Initialize session ──────────────────────────────────────────
echo "Initializing session..."
SESSION=$(curl -s -D - -X POST "$MCP_URL" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Target-URL: $TARGET_URL" \
  -H "X-API-Type: $API_TYPE" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-03-26",
      "capabilities": {},
      "clientInfo": {"name": "countries-script", "version": "1.0"}
    }
  }' 2>/dev/null | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r')

echo "Session: $SESSION"

# ── Helper function ─────────────────────────────────────────────
ask() {
  local question="$1"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Q: $question"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  curl -s -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -H "Mcp-Session-Id: $SESSION" \
    -H "X-Target-URL: $TARGET_URL" \
    -H "X-API-Type: $API_TYPE" \
    -d "$(printf '{
      "jsonrpc": "2.0",
      "id": %d,
      "method": "tools/call",
      "params": {
        "name": "countries_trevorblades_query",
        "arguments": {
          "question": "%s"
        }
      }
    }' "$RANDOM" "$question")" 2>&1 | python3 -c "
import sys, json
for line in sys.stdin:
    line = line.strip()
    if line.startswith('data:'):
        data = json.loads(line[5:])
        sc = data.get('result', {}).get('structuredContent')
        content = data.get('result', {}).get('content', [])
        if sc:
            print(json.dumps(sc, indent=2, ensure_ascii=False)[:2000])
        elif content:
            for c in content:
                print(c.get('text', '')[:2000])
"
}

# ── Ask questions ───────────────────────────────────────────────
ask "List all countries in Asia with their name, capital, and currency"
ask "Which countries use the Euro (EUR) as currency?"
ask "What languages are spoken in India?"
ask "How many countries are in Africa vs Europe vs Asia?"
ask "What country has phone code +91?"
ask "List South American countries that speak Spanish"
```

---

## 4. Python Helper Script

A reusable Python script that can query **any** API Agent server:

```python
#!/usr/bin/env python3
"""
mcp_query.py — Universal MCP natural language query script.

Usage:
  python mcp_query.py --target-url https://rickandmortyapi.com/graphql \
                      --api-type graphql \
                      --question "How many episodes exist?"

  python mcp_query.py --target-url https://petstore3.swagger.io/api/v3/openapi.json \
                      --api-type rest \
                      --base-url https://petstore3.swagger.io/api/v3 \
                      --question "What pets are available?"

  # Interactive mode (keep asking questions)
  python mcp_query.py --target-url https://countries.trevorblades.com/graphql \
                      --api-type graphql \
                      --interactive
"""

import argparse
import json
import sys
import re

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)


def parse_sse(text: str) -> dict | None:
    for line in text.strip().splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    try:
        return json.loads(text)
    except Exception:
        return None


class MCPSession:
    def __init__(self, mcp_url: str, target_url: str, api_type: str,
                 base_url: str = "", target_headers: str = ""):
        self.mcp_url = mcp_url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "X-Target-URL": target_url,
            "X-API-Type": api_type,
        }
        if base_url:
            self.headers["X-Base-URL"] = base_url
        if target_headers:
            self.headers["X-Target-Headers"] = target_headers
        self.session_id = None
        self.tool_prefix = None
        self._req_id = 0
        self.client = httpx.Client(timeout=120.0)

    def _request(self, method: str, params: dict = None) -> dict:
        self._req_id += 1
        headers = {**self.headers}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {"jsonrpc": "2.0", "id": self._req_id, "method": method}
        if params:
            payload["params"] = params

        resp = self.client.post(self.mcp_url, json=payload, headers=headers)
        resp.raise_for_status()
        self.session_id = resp.headers.get("mcp-session-id", self.session_id)
        return parse_sse(resp.text) or {}

    def initialize(self):
        result = self._request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcp-query-script", "version": "1.0"},
        })
        server = result.get("result", {}).get("serverInfo", {})
        print(f"✓ Connected to {server.get('name', 'API Agent')}")
        print(f"  Session: {self.session_id}")

    def discover_tools(self):
        result = self._request("tools/list")
        tools = result.get("result", {}).get("tools", [])
        print(f"✓ Tools discovered: {len(tools)}")
        for t in tools:
            name = t["name"]
            print(f"  • {name}")
            if name.endswith("_query") and not name.startswith("r_"):
                self.tool_prefix = name.removesuffix("_query")
        if self.tool_prefix:
            print(f"  Tool prefix: {self.tool_prefix}")
        return tools

    def query(self, question: str) -> str:
        if not self.tool_prefix:
            raise RuntimeError("Call discover_tools() first")

        tool_name = f"{self.tool_prefix}_query"
        result = self._request("tools/call", {
            "name": tool_name,
            "arguments": {"question": question},
        })

        sc = result.get("result", {}).get("structuredContent")
        if sc:
            return json.dumps(sc, indent=2, ensure_ascii=False)

        content = result.get("result", {}).get("content", [])
        parts = []
        for c in content:
            parts.append(c.get("text", ""))
        return "\n".join(parts) if parts else json.dumps(result, indent=2)

    def execute(self, **kwargs) -> str:
        if not self.tool_prefix:
            raise RuntimeError("Call discover_tools() first")

        tool_name = f"{self.tool_prefix}_execute"
        result = self._request("tools/call", {
            "name": tool_name,
            "arguments": kwargs,
        })

        sc = result.get("result", {}).get("structuredContent")
        if sc:
            return json.dumps(sc, indent=2, ensure_ascii=False)

        content = result.get("result", {}).get("content", [])
        parts = [c.get("text", "") for c in content]
        return "\n".join(parts) if parts else json.dumps(result, indent=2)

    def close(self):
        self.client.close()


def main():
    parser = argparse.ArgumentParser(description="Query APIs via API Agent MCP server")
    parser.add_argument("--mcp-url", default="http://localhost:3000/mcp", help="MCP server URL")
    parser.add_argument("--target-url", required=True, help="Target API URL")
    parser.add_argument("--api-type", required=True, choices=["graphql", "rest"], help="API type")
    parser.add_argument("--base-url", default="", help="Base URL override (REST only)")
    parser.add_argument("--target-headers", default="", help="JSON auth headers")
    parser.add_argument("--question", default="", help="Question to ask")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    args = parser.parse_args()

    session = MCPSession(
        mcp_url=args.mcp_url,
        target_url=args.target_url,
        api_type=args.api_type,
        base_url=args.base_url,
        target_headers=args.target_headers,
    )

    try:
        session.initialize()
        session.discover_tools()

        if args.question:
            print(f"\nQ: {args.question}")
            print("─" * 50)
            answer = session.query(args.question)
            print(answer[:5000])

        if args.interactive:
            print("\n📝 Interactive mode (type 'quit' to exit)")
            while True:
                try:
                    question = input("\nQ: ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if question.lower() in ("quit", "exit", "q"):
                    break
                if not question:
                    continue
                print("─" * 50)
                answer = session.query(question)
                print(answer[:5000])

    finally:
        session.close()

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
```

### Usage

```bash
# Single question — GraphQL
python mcp_query.py \
  --target-url https://rickandmortyapi.com/graphql \
  --api-type graphql \
  --question "How many episodes are there?"

# Single question — REST with base URL
python mcp_query.py \
  --target-url https://petstore3.swagger.io/api/v3/openapi.json \
  --api-type rest \
  --base-url https://petstore3.swagger.io/api/v3 \
  --question "What pets are available?"

# Interactive mode — keep asking questions
python mcp_query.py \
  --target-url https://countries.trevorblades.com/graphql \
  --api-type graphql \
  --interactive

# With authentication
python mcp_query.py \
  --target-url https://api.example.com/graphql \
  --api-type graphql \
  --target-headers '{"Authorization": "Bearer YOUR_TOKEN"}' \
  --interactive
```

---

## 5. Node.js Helper Script

```javascript
#!/usr/bin/env node
/**
 * mcp_query.js — Universal MCP natural language query script.
 *
 * Usage:
 *   node mcp_query.js \
 *     --target-url https://rickandmortyapi.com/graphql \
 *     --api-type graphql \
 *     --question "How many episodes exist?"
 *
 *   node mcp_query.js \
 *     --target-url https://countries.trevorblades.com/graphql \
 *     --api-type graphql \
 *     --interactive
 */

const readline = require("readline");

// ── Parse CLI args ─────────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    mcpUrl: "http://localhost:3000/mcp",
    targetUrl: "",
    apiType: "",
    baseUrl: "",
    targetHeaders: "",
    question: "",
    interactive: false,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--mcp-url":       opts.mcpUrl = args[++i]; break;
      case "--target-url":    opts.targetUrl = args[++i]; break;
      case "--api-type":      opts.apiType = args[++i]; break;
      case "--base-url":      opts.baseUrl = args[++i]; break;
      case "--target-headers":opts.targetHeaders = args[++i]; break;
      case "--question":      opts.question = args[++i]; break;
      case "--interactive":   opts.interactive = true; break;
    }
  }

  if (!opts.targetUrl || !opts.apiType) {
    console.error("Usage: node mcp_query.js --target-url <url> --api-type <graphql|rest> [--question <q>] [--interactive]");
    process.exit(1);
  }

  return opts;
}

// ── MCP Session ────────────────────────────────────────────────
class MCPSession {
  constructor(opts) {
    this.mcpUrl = opts.mcpUrl;
    this.headers = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "X-Target-URL": opts.targetUrl,
      "X-API-Type": opts.apiType,
    };
    if (opts.baseUrl) this.headers["X-Base-URL"] = opts.baseUrl;
    if (opts.targetHeaders) this.headers["X-Target-Headers"] = opts.targetHeaders;
    this.sessionId = null;
    this.toolPrefix = null;
    this.reqId = 0;
  }

  async _request(method, params) {
    this.reqId++;
    const headers = { ...this.headers };
    if (this.sessionId) headers["Mcp-Session-Id"] = this.sessionId;

    const payload = { jsonrpc: "2.0", id: this.reqId, method };
    if (params) payload.params = params;

    const resp = await fetch(this.mcpUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
    this.sessionId = resp.headers.get("mcp-session-id") || this.sessionId;

    const body = await resp.text();
    for (const line of body.split("\n")) {
      if (line.startsWith("data:")) return JSON.parse(line.slice(5));
    }
    return JSON.parse(body);
  }

  async initialize() {
    const result = await this._request("initialize", {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: { name: "node-mcp-script", version: "1.0" },
    });
    const server = result?.result?.serverInfo || {};
    console.log(`✓ Connected to ${server.name || "API Agent"}`);
    console.log(`  Session: ${this.sessionId}`);
  }

  async discoverTools() {
    const result = await this._request("tools/list");
    const tools = result?.result?.tools || [];
    console.log(`✓ Tools discovered: ${tools.length}`);
    for (const t of tools) {
      console.log(`  • ${t.name}`);
      if (t.name.endsWith("_query") && !t.name.startsWith("r_")) {
        this.toolPrefix = t.name.replace(/_query$/, "");
      }
    }
    if (this.toolPrefix) console.log(`  Tool prefix: ${this.toolPrefix}`);
    return tools;
  }

  async query(question) {
    if (!this.toolPrefix) throw new Error("Call discoverTools() first");
    const result = await this._request("tools/call", {
      name: `${this.toolPrefix}_query`,
      arguments: { question },
    });
    const sc = result?.result?.structuredContent;
    if (sc) return JSON.stringify(sc, null, 2);
    const content = result?.result?.content || [];
    return content.map((c) => c.text).join("\n") || JSON.stringify(result, null, 2);
  }
}

// ── Main ───────────────────────────────────────────────────────
async function main() {
  const opts = parseArgs();
  const session = new MCPSession(opts);

  await session.initialize();
  await session.discoverTools();

  if (opts.question) {
    console.log(`\nQ: ${opts.question}`);
    console.log("─".repeat(50));
    const answer = await session.query(opts.question);
    console.log(answer.slice(0, 5000));
  }

  if (opts.interactive) {
    console.log("\n📝 Interactive mode (type 'quit' to exit)");
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

    const askQuestion = () => {
      rl.question("\nQ: ", async (question) => {
        question = question.trim();
        if (["quit", "exit", "q"].includes(question.toLowerCase())) {
          rl.close();
          console.log("\n✓ Done!");
          return;
        }
        if (!question) { askQuestion(); return; }

        console.log("─".repeat(50));
        try {
          const answer = await session.query(question);
          console.log(answer.slice(0, 5000));
        } catch (err) {
          console.error(`Error: ${err.message}`);
        }
        askQuestion();
      });
    };

    askQuestion();
  }
}

main().catch(console.error);
```

### Usage

```bash
# Single question
node mcp_query.js \
  --target-url https://rickandmortyapi.com/graphql \
  --api-type graphql \
  --question "List all dead characters"

# Interactive mode
node mcp_query.js \
  --target-url https://countries.trevorblades.com/graphql \
  --api-type graphql \
  --interactive

# REST API
node mcp_query.js \
  --target-url https://petstore3.swagger.io/api/v3/openapi.json \
  --api-type rest \
  --base-url https://petstore3.swagger.io/api/v3 \
  --question "Show store inventory"
```

---

## Quick Reference — Tool Names by API

| API | `X-Target-URL` | Query Tool | Execute Tool |
|-----|----------------|------------|--------------|
| Petstore | `https://petstore3.swagger.io/api/v3/openapi.json` | `petstore3_swagger_query` | `petstore3_swagger_execute` |
| Rick & Morty | `https://rickandmortyapi.com/graphql` | `rickandmortyapi_query` | `rickandmortyapi_execute` |
| Countries | `https://countries.trevorblades.com/graphql` | `countries_trevorblades_query` | `countries_trevorblades_execute` |
