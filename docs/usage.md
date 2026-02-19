# API Agent — Complete Usage Guide

> **Turn any API into an MCP server. Query in English. Get results—even when the API can't.**

API Agent is a universal [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that wraps any GraphQL or REST API into intelligent, queryable tools. Users ask questions in plain English; the agent reads the API schema, generates the right queries, executes them, and post-processes results using DuckDB SQL — all automatically.

---

## Table of Contents

1. [Supported API Specifications](#1-supported-api-specifications)
2. [Does the API Need to Be Online?](#2-does-the-api-need-to-be-online)
3. [How It Works — End to End](#3-how-it-works--end-to-end)
4. [Installation & Deployment](#4-installation--deployment)
5. [Connecting Your API (MCP Client Configuration)](#5-connecting-your-api-mcp-client-configuration)
6. [Headers Reference](#6-headers-reference)
7. [Setting the Base URL](#7-setting-the-base-url)
8. [Authentication](#8-authentication)
9. [MCP Tools Exposed](#9-mcp-tools-exposed)
10. [DuckDB SQL Post-Processing](#10-duckdb-sql-post-processing)
11. [Recipe Learning System](#11-recipe-learning-system)
12. [Polling (Async APIs)](#12-polling-async-apis)
13. [Safety & Read-Only Mode](#13-safety--read-only-mode)
14. [LLM Provider Configuration](#14-llm-provider-configuration)
15. [Environment Variables Reference](#15-environment-variables-reference)
16. [Observability & Tracing](#16-observability--tracing)
17. [Dynamic Tool Naming](#17-dynamic-tool-naming)
18. [Troubleshooting](#18-troubleshooting)
19. [Architecture Overview](#19-architecture-overview)
20. [Examples](#20-examples)
21. [Programmatic Client Examples](#21-programmatic-client-examples)
    - [Python](#211-python)
    - [Node.js / TypeScript](#212-nodejs--typescript)
    - [Java](#213-java)
    - [REST API Adaptation](#214-rest-api-example-all-languages)
    - [cURL Quick Reference](#215-curl-quick-reference)

---

## 1. Supported API Specifications

### GraphQL APIs

- **Any GraphQL endpoint** with introspection enabled (the standard `__schema` query).
- No specification file needed — the schema is auto-discovered at runtime.
- The server sends an introspection query to the endpoint and builds a compact type DSL for the LLM agent.
- If the endpoint enforces a **depth limit** (e.g., returns 413 or "depth exceeded"), the server automatically falls back to a shallower introspection query. This is a normal behavior logged at INFO level, not an error.

### REST APIs

- **OpenAPI 3.x** specifications (both `3.0.x` and `3.1.x`).
- The spec can be in **JSON** or **YAML** format.
- The spec must be accessible via a URL (not a local file path — see below).
- OpenAPI 2.0 (Swagger) is **not supported** — convert it to 3.x first.

### What's NOT Supported

| Format | Status |
|--------|--------|
| OpenAPI 2.0 (Swagger) | ❌ Not supported (convert to 3.x) |
| RAML | ❌ Not supported |
| gRPC / Protobuf | ❌ Not supported |
| SOAP / WSDL | ❌ Not supported |
| GraphQL without introspection | ❌ Cannot discover schema |

---

## 2. Does the API Need to Be Online?

**Yes, the target API must be reachable from the machine running API Agent.**

The server needs network access to:

1. **At startup / first request for a session:**
   - **GraphQL**: Send an introspection query to the endpoint to discover the schema.
   - **REST**: Fetch the OpenAPI spec from the provided URL to understand available endpoints.

2. **At query time:**
   - Execute actual API calls (GraphQL queries, REST requests) against the target API.

There is **no offline mode** — the server acts as a live proxy between the MCP client and the target API.

> **Note**: The OpenAPI spec URL and the actual API base URL can be different hosts. For example, the spec might be at `https://docs.example.com/openapi.json` while the API itself is at `https://api.example.com/v2`. See [Setting the Base URL](#7-setting-the-base-url).

---

## 3. How It Works — End to End

```
┌──────────────┐     ┌─────────────────┐     ┌───────────┐     ┌────────────┐
│  MCP Client  │────▶│  API Agent MCP  │────▶│  LLM      │────▶│ Target API │
│  (Claude,    │◀────│  Server         │◀────│  (GPT-4o) │◀────│ (GraphQL/  │
│   Cursor)    │     │  :3000          │     │           │     │  REST)     │
└──────────────┘     └─────────────────┘     └───────────┘     └────────────┘
                           │
                           ▼
                     ┌───────────┐
                     │  DuckDB   │
                     │  (SQL     │
                     │  engine)  │
                     └───────────┘
```

### Step-by-step flow:

1. **MCP Client sends a request** with HTTP headers specifying the target API URL and type.

2. **Schema discovery** (happens automatically on the first request per session):
   - GraphQL: Introspection query → compact type DSL
   - REST: Fetch OpenAPI spec → compact endpoint/schema DSL

3. **Tool listing**: The middleware transforms internal tools (`_query`, `_execute`) into session-specific named tools (e.g., `rickandmortyapi_query`, `rickandmortyapi_execute`) and attaches any learned recipe tools (`r_*`).

4. **Natural language query** (`{prefix}_query`):
   - The schema DSL + user question are sent to the LLM agent.
   - The agent has internal tools: `graphql_query` / `rest_call`, `sql_query`, `search_schema`, and optionally `poll_until_done`.
   - The agent reads the schema, builds the right API call(s), executes them, optionally runs SQL post-processing via DuckDB, and returns results.

5. **Direct execution** (`{prefix}_execute`):
   - Bypass the LLM agent — execute a known query/endpoint directly.
   - Useful for re-running queries discovered via the query tool.

6. **Recipe extraction** (automatic, in the background):
   - After a successful query, the system extracts a parameterized "recipe" (API calls + SQL template).
   - The recipe appears as a new MCP tool (`r_{name}`) that can be called directly without LLM reasoning.

---

## 4. Installation & Deployment

### Prerequisites

- **Python 3.11+**
- An Azure OpenAI API key (or OpenAI API key)

### Option A: Direct Run (no clone)

```bash
# Set Azure OpenAI credentials as env vars and run directly
LLM_PROVIDER=azure \
AZURE_OPENAI_API_KEY=your-key \
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/ \
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o \
uvx --from git+https://github.com/Accenture-NEU/312826_api-agent api-agent
```

> For the full list of configurable settings, see the `.env.example` file in the repository root.

### Option B: Clone & Run with `uv`

```bash
git clone https://github.com/Accenture-NEU/312826_api-agent.git
cd 312826_api-agent
uv sync
```

Configure your environment — copy the example file and fill in your values:

```bash
cp .env.example .env
```

Then edit `.env` with your Azure OpenAI credentials. The `.env.example` file contains **all available settings** with descriptions and defaults. At minimum, set:

```env
# Azure OpenAI (default)
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-azure-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# OR for OpenAI (alternative)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...
```

> **Tip**: The `.env.example` file is version-controlled and documents every setting — LLM provider, server config, agent limits, polling, recipes, and tracing. See [Environment Variables Reference](#15-environment-variables-reference) for full details.

Start the server:

```bash
uv run api-agent
```

Server starts at `http://localhost:3000`.

### Option C: Docker

```bash
git clone https://github.com/Accenture-NEU/312826_api-agent.git
cd 312826_api-agent
cp .env.example .env   # ← edit with your LLM credentials
docker build -t api-agent .
docker run -p 3000:3000 --env-file .env api-agent
```

### Option D: Docker Compose (recommended for production)

```bash
cp .env.example .env   # ← edit with your LLM credentials
docker compose up -d
```

The `docker-compose.yml` reads from `.env` automatically:

```yaml
services:
  api-agent:
    build: .
    ports:
      - "3000:3000"
    env_file:
      - .env
    environment:
      - API_AGENT_HOST=0.0.0.0
      - API_AGENT_PORT=3000
      - API_AGENT_CORS_ALLOWED_ORIGINS=*
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### Health Check

```bash
curl http://localhost:3000/health
# → {"status": "ok"}
```

---

## 5. Connecting Your API (MCP Client Configuration)

API Agent doesn't need per-API code or configuration files. You "wrap" APIs entirely through **HTTP headers** sent by your MCP client.

### MCP Client Config Format

Most MCP clients (Claude Desktop, Cursor, etc.) use a JSON config:

```json
{
  "mcpServers": {
    "<your-api-name>": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "<graphql-endpoint-or-openapi-spec-url>",
        "X-API-Type": "<graphql|rest>",
        "X-Target-Headers": "{\"Authorization\": \"Bearer YOUR_TOKEN\"}"
      }
    }
  }
}
```

### GraphQL API Example

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

- `X-Target-URL` → the GraphQL endpoint (the URL you would POST queries to).
- The server introspects the schema automatically.

### REST API Example

```json
{
  "mcpServers": {
    "petstore": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://petstore3.swagger.io/api/v3/openapi.json",
        "X-API-Type": "rest"
      }
    }
  }
}
```

- `X-Target-URL` → the URL of the OpenAPI 3.x spec (JSON or YAML).
- The server fetches the spec, parses it, and derives the base URL from the `servers[0].url` field.

### Multiple APIs Simultaneously

You can connect multiple APIs by adding multiple entries:

```json
{
  "mcpServers": {
    "rickandmorty": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://rickandmortyapi.com/graphql",
        "X-API-Type": "graphql"
      }
    },
    "countries": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://countries.trevorblades.com/graphql",
        "X-API-Type": "graphql"
      }
    },
    "petstore": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://petstore3.swagger.io/api/v3/openapi.json",
        "X-API-Type": "rest"
      }
    }
  }
}
```

Each entry gets its own MCP session with isolated tool names (e.g., `rickandmortyapi_query`, `countries_trevorblades_query`, `petstore3_swagger_query`).

---

## 6. Headers Reference

All configuration is done via HTTP headers on each MCP request.

### Required Headers

| Header | Value | Description |
|--------|-------|-------------|
| `X-Target-URL` | URL string | **GraphQL**: The endpoint URL (e.g., `https://api.example.com/graphql`). **REST**: The OpenAPI spec URL (e.g., `https://api.example.com/openapi.json`). |
| `X-API-Type` | `graphql` or `rest` | Which protocol the target uses. |

### Optional Headers

| Header | Value | Default | Description |
|--------|-------|---------|-------------|
| `X-Target-Headers` | JSON string | `{}` | Headers to forward to the target API. Typically used for authentication. Must be a valid JSON object string. Example: `{"Authorization": "Bearer token123"}` |
| `X-API-Name` | string | auto-generated | Override the tool name prefix. By default, a prefix is derived from the hostname (e.g., `rickandmortyapi`). Set this to control tool names explicitly (e.g., `myapi` → tools become `myapi_query`, `myapi_execute`). Max 32 characters, snake_case. |
| `X-Base-URL` | URL string | from spec | Override the base URL for REST API calls. See [Setting the Base URL](#7-setting-the-base-url). |
| `X-Allow-Unsafe-Paths` | JSON array | `[]` | Glob patterns for paths where POST/PUT/DELETE/PATCH are allowed. See [Safety](#13-safety--read-only-mode). |
| `X-Include-Result` | `true` or `false` | `false` | Include the full uncapped `result` field in query responses (raw data alongside the agent's summary). |
| `X-Poll-Paths` | JSON array | `[]` | Paths that require polling for async operations. See [Polling](#12-polling-async-apis). |

---

## 7. Setting the Base URL

### For GraphQL APIs

**Not needed.** The `X-Target-URL` is the GraphQL endpoint itself — all queries are POSTed directly to it.

### For REST APIs

The base URL determines where API calls are sent. It's resolved in this priority order:

1. **`X-Base-URL` header** (highest priority) — explicit override.
2. **`servers[0].url` from the OpenAPI spec** — auto-extracted.
3. **Derived from the spec URL** — fallback (e.g., `https://api.example.com/openapi.json` → `https://api.example.com`).

#### When to Use `X-Base-URL`

- When the OpenAPI spec has a **relative** `servers[0].url` (e.g., `/api/v3` instead of `https://api.example.com/api/v3`).
- When the spec is hosted on a **different domain** than the API itself.
- When you want to point to a **staging/dev** version of the API instead of production.

#### Example: Explicit Base URL

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

Here, the spec is at `.../openapi.json` but the actual API calls should go to `.../api/v3/pet`, `.../api/v3/store`, etc.

#### How It's Used Internally

When the agent calls `rest_call("GET", "/pet/1")`, the server:
1. Takes the base URL: `https://petstore3.swagger.io/api/v3`
2. Joins with the path: `/pet/1`
3. Makes a GET to: `https://petstore3.swagger.io/api/v3/pet/1`

Path parameters are substituted automatically (e.g., `/users/{id}` + `path_params: {"id": "123"}` → `/users/123`).

---

## 8. Authentication

API Agent **does not handle authentication itself**. Instead, it **forwards headers** that you provide to the target API.

### How Auth Works

1. You provide auth headers via `X-Target-Headers` in your MCP client config.
2. API Agent parses the JSON and includes those headers in **every request** to the target API.
3. The target API sees them as if the request came from an authenticated client.

### Bearer Token Auth

```json
{
  "mcpServers": {
    "myapi": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://api.example.com/graphql",
        "X-API-Type": "graphql",
        "X-Target-Headers": "{\"Authorization\": \"Bearer eyJhbGciOiJSUzI1NiIs...\"}"
      }
    }
  }
}
```

### API Key Auth

```json
{
  "headers": {
    "X-Target-URL": "https://api.example.com/v1/openapi.json",
    "X-API-Type": "rest",
    "X-Target-Headers": "{\"X-API-Key\": \"your-api-key-here\"}"
  }
}
```

### Multiple Auth Headers

```json
{
  "headers": {
    "X-Target-URL": "https://api.example.com/graphql",
    "X-API-Type": "graphql",
    "X-Target-Headers": "{\"Authorization\": \"Bearer token\", \"X-Tenant-Id\": \"acme-corp\"}"
  }
}
```

### Auth for Spec Fetching (REST)

The `X-Target-Headers` are also sent when **fetching the OpenAPI spec** itself. This covers cases where the spec endpoint is behind authentication too.

### Security Notes

- Auth tokens are stored only in the MCP client config (your machine).
- API Agent does **not** log header values — only header keys are logged for debugging.
- Tokens are forwarded over HTTPS to the target API (ensure your target URL uses `https://`).
- API Agent itself does not require authentication to connect to. Secure it via network policies if exposing beyond localhost.

---

## 9. MCP Tools Exposed

When a client connects, API Agent exposes tools dynamically based on the target API.

### Core Tools (always present, 2 per API)

| Tool | Purpose | Input | Output |
|------|---------|-------|--------|
| `{prefix}_query` | Natural language querying | `question: string` | `{ok, data, queries/api_calls, result?, error?}` |
| `{prefix}_execute` | Direct API execution | GraphQL: `query`, `variables` / REST: `method`, `path`, params | `{ok, data, error?}` |

The `{prefix}` is auto-derived from the target URL hostname:
- `https://rickandmortyapi.com/graphql` → `rickandmortyapi`
- `https://countries.trevorblades.com/graphql` → `countries_trevorblades`
- `https://petstore3.swagger.io/api/v3/openapi.json` → `petstore3_swagger`

Override with the `X-API-Name` header.

### `{prefix}_query` — Natural Language Tool

Ask questions in plain English. The LLM agent reads the schema, builds queries, executes them, and returns answers.

**Input:**
```json
{ "question": "List all countries in Europe with their capital and currency" }
```

**Output:**
```json
{
  "ok": true,
  "data": "Here are the European countries with their capitals...",
  "queries": ["{ continent(code: \"EU\") { countries { name capital currency } } }"],
  "result": [{"name": "Germany", "capital": "Berlin", "currency": "EUR"}, ...]
}
```

### `{prefix}_execute` — Direct Execution Tool

Execute known queries/calls without LLM processing.

**GraphQL input:**
```json
{
  "query": "{ characters(filter: {status: \"Alive\"}) { results { name species } } }"
}
```

**REST input:**
```json
{
  "method": "GET",
  "path": "/pet/findByStatus",
  "query_params": {"status": "available"}
}
```

### Recipe Tools (dynamic)

After successful queries, recipes are automatically extracted and exposed as `r_{name}` tools. See [Recipe Learning System](#11-recipe-learning-system).

---

## 10. DuckDB SQL Post-Processing

This is one of API Agent's most powerful features. After fetching data from the API, results are loaded into in-memory DuckDB tables. The LLM agent can then run SQL queries for operations the API may not natively support.

### What DuckDB Enables

| Feature | Example |
|---------|---------|
| **Filtering** | `SELECT * FROM data WHERE status = 'alive'` |
| **Sorting** | `SELECT * FROM data ORDER BY name ASC` |
| **Aggregation** | `SELECT species, COUNT(*) FROM data GROUP BY species` |
| **Top-N** | `SELECT * FROM data ORDER BY views DESC LIMIT 10` |
| **JOINs** | `SELECT u.name, p.title FROM users u JOIN posts p ON u.id = p.authorId` |
| **DISTINCT** | `SELECT DISTINCT species FROM data` |
| **Nested data** | `SELECT t.user.name FROM data t` (dot notation for structs) |
| **Array expansion** | `FROM data, UNNEST(data.tags) AS u(tag)` |

### How Tables Are Created

Each API call result is stored as a named DuckDB table:

```
graphql_query('{ users { id name } }', name='users')
→ creates table "users" with columns (id, name)

graphql_query('{ posts { authorId title views } }', name='posts')
→ creates table "posts" with columns (authorId, title, views)

sql_query('SELECT u.name, COUNT(p.title) as post_count FROM users u JOIN posts p ON u.id = p.authorId GROUP BY u.name ORDER BY post_count DESC')
→ joins both tables
```

### DuckDB-Specific SQL Syntax

| Feature | Syntax |
|---------|--------|
| Structs (nested objects) | `t.field.subfield` (dot notation) |
| Arrays | `len(arr)`, `arr[1]` (1-indexed) |
| UNNEST | `FROM t, UNNEST(t.arr) AS u(val)` |
| EXCLUDE columns | `SELECT * EXCLUDE (col) FROM t` |
| UUIDs | `CAST(id AS VARCHAR)` |

---

## 11. Recipe Learning System

API Agent automatically learns from successful queries and creates reusable "recipes" — cached pipelines of API calls + SQL that can be replayed without LLM reasoning.

### How It Works

1. **Execute**: User asks a question → agent makes API calls + SQL.
2. **Extract**: The system uses the LLM to convert the execution trace into a parameterized template.
3. **Validate**: The template is rendered with default params and verified to reproduce the original calls.
4. **Cache**: Stored in-process, keyed by (API ID, schema hash).
5. **Expose**: Appears as an MCP tool `r_{name}` with typed parameters.

### Example

First query (uses LLM):
```
Question: "Top 5 users by age"
→ Agent: GET /users → SQL: SELECT * FROM data ORDER BY age DESC LIMIT 5
→ Recipe extracted: "get_top_users" with param {limit: int, default: 5}
```

Subsequent calls (no LLM):
```
r_get_top_users(limit=10)
→ Directly executes: GET /users → SQL: SELECT * FROM data ORDER BY age DESC LIMIT 10
```

### Recipe Characteristics

- **Parameterized**: User-specific values (IDs, limits, search terms) become parameters.
- **Schema-bound**: Recipes auto-expire when the API schema changes.
- **In-process**: Stored in memory with LRU eviction (default: 64 recipes).
- **Clients notified**: When a new recipe is created, MCP clients receive a `tools/list_changed` notification.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_AGENT_ENABLE_RECIPES` | `true` | Enable/disable recipe learning |
| `API_AGENT_RECIPE_CACHE_SIZE` | `64` | Max recipes in LRU cache |

Disable: set `API_AGENT_ENABLE_RECIPES=false`.

---

## 12. Polling (Async APIs)

Some REST APIs return results asynchronously — you make a request, then poll until the result is ready. API Agent supports this via the `X-Poll-Paths` header.

### Setup

```json
{
  "headers": {
    "X-Target-URL": "https://api.example.com/openapi.json",
    "X-API-Type": "rest",
    "X-Poll-Paths": "[\"/api/trips\", \"/api/reports\"]"
  }
}
```

### How It Works

When `X-Poll-Paths` is set, the REST agent gets an additional tool:

```
poll_until_done(method, path, done_field, done_value, body?, name?, delay_ms?)
```

- `done_field`: Dot-path to the completion field in the response (e.g., `"status"`, `"data.0.isCompleted"`)
- `done_value`: Target value to match (e.g., `"true"`, `"COMPLETED"`)
- `delay_ms`: Milliseconds between polls (default: 3000ms)
- Max polls: 20 (configurable via `API_AGENT_MAX_POLLS`)

The agent automatically uses `poll_until_done` instead of `rest_call` for paths listed in `X-Poll-Paths`.

---

## 13. Safety & Read-Only Mode

By default, API Agent operates in **read-only mode**.

### GraphQL

- **Mutations are blocked.** Any GraphQL query starting with `mutation` is rejected.
- Only `query` operations are allowed.

### REST

- **Unsafe HTTP methods blocked by default:** `POST`, `PUT`, `DELETE`, `PATCH`.
- Only `GET` requests are allowed unless explicitly whitelisted.

### Allowing Unsafe Methods

Use the `X-Allow-Unsafe-Paths` header with glob patterns:

```json
{
  "headers": {
    "X-Allow-Unsafe-Paths": "[\"/api/orders/*\", \"/api/checkout\"]"
  }
}
```

This allows POST/PUT/DELETE/PATCH **only** on paths matching the patterns. The matching uses Python's `fnmatch` glob syntax:

| Pattern | Matches |
|---------|---------|
| `/api/orders/*` | `/api/orders/123`, `/api/orders/new` |
| `/api/*/submit` | `/api/forms/submit`, `/api/tasks/submit` |
| `/api/**` | Everything under `/api/` |

---

## 14. LLM Provider Configuration

API Agent supports two LLM providers: **Azure OpenAI** (default) and **OpenAI**.

### Azure OpenAI (default)

```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-12-01-preview   # optional, default
```

### OpenAI (alternative)

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1    # optional, default
API_AGENT_MODEL_NAME=gpt-5.2                  # optional, default
```

### Custom / OpenAI-Compatible Providers

Any provider that exposes an OpenAI-compatible API can be used:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://your-custom-llm.example.com/v1
API_AGENT_MODEL_NAME=your-model-name
```

This works with providers like LiteLLM, Ollama (with OpenAI compatibility layer), vLLM, etc.

### Reasoning Effort

For models that support it (e.g., o1, o3), you can set reasoning effort:

```env
API_AGENT_REASONING_EFFORT=medium    # "low", "medium", "high", or empty to disable
```

---

## 15. Environment Variables Reference

All variables accept the `API_AGENT_` prefix. For OpenAI/Azure variables, both prefixed and unprefixed forms work.

### LLM Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `azure` | LLM provider: `azure` or `openai` |
| `AZURE_OPENAI_API_KEY` | Yes (if azure) | — | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Yes (if azure) | — | Azure resource endpoint |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Yes (if azure) | — | Azure deployment name |
| `OPENAI_API_KEY` | Yes (if openai) | — | OpenAI API key |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | OpenAI base URL |
| `AZURE_OPENAI_API_VERSION` | No | `2024-12-01-preview` | Azure API version |
| `API_AGENT_MODEL_NAME` | No | `gpt-5.2` | Model name (OpenAI provider only) |
| `API_AGENT_REASONING_EFFORT` | No | (empty) | Reasoning effort: `low`, `medium`, `high` |

### Server Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_AGENT_HOST` | No | `0.0.0.0` | Bind host |
| `API_AGENT_PORT` | No | `3000` | Bind port |
| `API_AGENT_TRANSPORT` | No | `streamable-http` | MCP transport: `http`, `streamable-http`, `sse` |
| `API_AGENT_CORS_ALLOWED_ORIGINS` | No | `*` | CORS allowed origins (comma-separated) |
| `API_AGENT_MCP_NAME` | No | `API Agent` | MCP server name |
| `API_AGENT_DEBUG` | No | `false` | Enable debug logging |

### Agent Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `API_AGENT_MAX_AGENT_TURNS` | `30` | Max LLM tool-call turns per query |
| `API_AGENT_MAX_RESPONSE_CHARS` | `50000` | Max response size |
| `API_AGENT_MAX_SCHEMA_CHARS` | `32000` | Max schema context for LLM |
| `API_AGENT_MAX_PREVIEW_ROWS` | `10` | Rows shown before suggesting pagination |
| `API_AGENT_MAX_TOOL_RESPONSE_CHARS` | `32000` | Max tool response size (~8K tokens) |

### Polling Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `API_AGENT_MAX_POLLS` | `20` | Max poll attempts |
| `API_AGENT_DEFAULT_POLL_DELAY_MS` | `3000` | Default ms between polls |

### Recipe Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `API_AGENT_ENABLE_RECIPES` | `true` | Enable recipe learning |
| `API_AGENT_RECIPE_CACHE_SIZE` | `64` | Max cached recipes (LRU) |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (empty) | OpenTelemetry OTLP endpoint. Set to enable tracing. |
| `API_AGENT_SERVICE_NAME` | `api-agent` | Service name for traces |

---

## 16. Observability & Tracing

API Agent supports OpenTelemetry tracing for full observability.

### Setup

Set the OTLP endpoint:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

### Compatible Backends

- **Jaeger** — `http://localhost:4318`
- **Zipkin** — via OTLP collector
- **Grafana Tempo**
- **Arize Phoenix** — AI-native observability

### What's Traced

- LLM calls (via OpenAI Agents SDK instrumentation)
- Tool invocations
- API calls to target endpoints
- SQL query execution
- Recipe extraction and execution

### Disabling Tracing

Simply don't set `OTEL_EXPORTER_OTLP_ENDPOINT`. If the endpoint is not set, tracing is completely disabled with zero overhead.

---

## 17. Dynamic Tool Naming

API Agent uses a middleware system to dynamically name tools based on the target API.

### How Tool Names Are Generated

1. The hostname from `X-Target-URL` is parsed.
2. Generic parts are stripped: `com`, `io`, `net`, `org`, `api`, `dev`, `qa`, `internal`, etc.
3. Remaining meaningful parts are joined with underscores, capped at 32 characters.

| URL | Generated Prefix |
|-----|-----------------|
| `https://rickandmortyapi.com/graphql` | `rickandmortyapi` |
| `https://countries.trevorblades.com/graphql` | `countries_trevorblades` |
| `https://flights-api-qa.internal.example.com/graphql` | `flights_example` |

### Overriding Tool Names

Use the `X-API-Name` header:

```json
{
  "headers": {
    "X-API-Name": "flights",
    "X-Target-URL": "https://flights-api-qa.internal.example.com/graphql",
    "X-API-Type": "graphql"
  }
}
```

Tools become: `flights_query`, `flights_execute`.

---

## 18. Troubleshooting

### "Full introspection failed (depth limit), retrying with shallow query"

**Not an error.** This is a normal fallback logged at INFO level. Some GraphQL servers enforce query depth limits. The server automatically retries with a shallower introspection query. The agent still works correctly with the shallow schema.

### "No base URL provided" / "Could not extract base URL from OpenAPI spec"

**Cause**: The OpenAPI spec has a relative `servers[0].url` or no `servers` block.

**Fix**: Add `X-Base-URL` header:
```json
{ "X-Base-URL": "https://api.example.com/v3" }
```

### "X-Target-URL header required" / "X-API-Type header required"

**Cause**: Missing required headers in MCP client configuration.

**Fix**: Ensure both `X-Target-URL` and `X-API-Type` are set in your MCP client config.

### "POST method not allowed (read-only mode)"

**Cause**: Trying to call unsafe methods without explicit permission.

**Fix**: Add `X-Allow-Unsafe-Paths` with glob patterns for the paths you need:
```json
{ "X-Allow-Unsafe-Paths": "[\"/api/orders/*\"]" }
```

### "Mutations are not allowed (read-only mode)"

**Cause**: Trying to execute a GraphQL mutation.

**Fix**: GraphQL mutations are blocked for safety. There is no header to allow them — this is by design.

### "Unsupported OpenAPI version: 2.0"

**Cause**: The spec is Swagger 2.0, not OpenAPI 3.x.

**Fix**: Convert the spec to OpenAPI 3.x using tools like [swagger2openapi](https://github.com/Mermade/oas-kit).

### "Failed to load schema"

**Cause**: The target URL is unreachable, returns an error, or requires authentication.

**Fix**:
1. Verify the URL is accessible: `curl <your-target-url>`
2. If auth is needed, add `X-Target-Headers`: `{"Authorization": "Bearer ..."}`
3. Check that the server can reach the target (network, firewalls, DNS).

### Large Schema Truncation

For very large APIs (100+ endpoints), the schema DSL may be truncated to fit within the LLM's context window (`MAX_SCHEMA_CHARS=32000`). When this happens, the agent gains a `search_schema` tool to explore the full schema via regex search.

---

## 19. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    MCP Client Layer                       │
│  (Claude Desktop / Cursor / Custom Client)               │
│  Sends: X-Target-URL, X-API-Type, X-Target-Headers      │
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol (Streamable HTTP)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              FastMCP Server (:3000)                       │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │        DynamicToolNamingMiddleware               │    │
│  │  • Extracts context from headers                 │    │
│  │  • Renames _query → {prefix}_query              │    │
│  │  • Injects recipe tools (r_*)                    │    │
│  │  • Routes recipe calls to executor               │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐ │
│  │ _query tool   │  │ _execute tool  │  │ r_* tools    │ │
│  │ (NL queries)  │  │ (direct exec) │  │ (recipes)    │ │
│  └──────┬───────┘  └───────┬───────┘  └──────┬───────┘ │
│         │                   │                  │         │
│  ┌──────▼───────────────────▼──────────────────▼──────┐ │
│  │                   Agent Layer                       │ │
│  │  ┌─────────────┐  ┌──────────────┐                 │ │
│  │  │ GraphQL     │  │ REST Agent   │                 │ │
│  │  │ Agent       │  │              │                 │ │
│  │  │ • Intro-    │  │ • OpenAPI    │                 │ │
│  │  │   spection  │  │   spec load  │                 │ │
│  │  │ • Query gen │  │ • REST calls │                 │ │
│  │  │ • SQL post  │  │ • Polling    │                 │ │
│  │  └─────────────┘  └──────────────┘                 │ │
│  │                                                     │ │
│  │  Internal tools:                                    │ │
│  │  • graphql_query / rest_call                        │ │
│  │  • sql_query (DuckDB)                               │ │
│  │  • search_schema (regex on raw schema)              │ │
│  │  • poll_until_done (if X-Poll-Paths set)            │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │               Execution Layer                       │  │
│  │  ┌─────────┐  ┌─────────┐  ┌───────────────────┐  │  │
│  │  │ httpx   │  │ DuckDB  │  │ Recipe Store      │  │  │
│  │  │ (HTTP)  │  │ (SQL)   │  │ (in-memory LRU)   │  │  │
│  │  └─────────┘  └─────────┘  └───────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │            LLM Provider (configurable)              │  │
│  │  OpenAI / Azure OpenAI / Compatible endpoint        │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| Entry point | `api_agent/__main__.py` | Creates FastMCP server, registers middleware |
| Config | `api_agent/config.py` | All settings via pydantic-settings |
| Context | `api_agent/context.py` | Extracts per-request context from headers |
| Middleware | `api_agent/middleware.py` | Dynamic tool naming, recipe tool injection |
| Query tool | `api_agent/tools/query.py` | Natural language query handler |
| Execute tool | `api_agent/tools/execute.py` | Direct API execution handler |
| GraphQL agent | `api_agent/agent/graphql_agent.py` | GraphQL schema introspection + LLM agent |
| REST agent | `api_agent/agent/rest_agent.py` | OpenAPI spec loading + LLM agent |
| LLM model | `api_agent/agent/model.py` | OpenAI / Azure client instantiation |
| GraphQL client | `api_agent/graphql/client.py` | HTTP calls to GraphQL endpoints |
| REST client | `api_agent/rest/client.py` | HTTP calls to REST endpoints |
| Schema loader | `api_agent/rest/schema_loader.py` | OpenAPI 3.x parsing → compact DSL |
| DuckDB executor | `api_agent/executor.py` | SQL execution on API response data |
| Recipe extractor | `api_agent/recipe/extractor.py` | LLM-based recipe extraction |
| Recipe store | `api_agent/recipe/store.py` | In-memory LRU cache with fuzzy matching |
| Tracing | `api_agent/tracing.py` | OpenTelemetry integration |

---

## 20. Examples

### Example 1: Public GraphQL API (No Auth)

**Config:**
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

**Questions you can ask:**
- "How many episodes are there in total?"
- "List all dead characters with their name and species"
- "Which species has the most characters? Show top 5"
- "Show locations of type Planet with their dimension"

### Example 2: Public GraphQL API (Countries)

**Config:**
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

**Questions you can ask:**
- "Which countries use the Euro?"
- "List all Asian countries with their capital and currency"
- "What languages are spoken in India?"
- "How many countries are in Africa vs Europe vs Asia?"
- "What country has phone code +91?"

### Example 3: REST API with Base URL Override

**Config:**
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

### Example 4: Authenticated Internal API

**Config:**
```json
{
  "mcpServers": {
    "internal_api": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://api.internal.company.com/graphql",
        "X-API-Type": "graphql",
        "X-Target-Headers": "{\"Authorization\": \"Bearer eyJhbGciOi...\", \"X-Tenant\": \"prod\"}",
        "X-API-Name": "company"
      }
    }
  }
}
```

Tools: `company_query`, `company_execute`

### Example 5: REST API with Write Access

**Config:**
```json
{
  "mcpServers": {
    "orders": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://api.example.com/openapi.json",
        "X-API-Type": "rest",
        "X-Target-Headers": "{\"Authorization\": \"Bearer token\"}",
        "X-Allow-Unsafe-Paths": "[\"/api/orders\", \"/api/orders/*\"]"
      }
    }
  }
}
```

This allows POST/PUT/DELETE on `/api/orders` and `/api/orders/{id}`, while all other paths remain read-only.

### Example 6: Async API with Polling

**Config:**
```json
{
  "mcpServers": {
    "reports": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://api.example.com/openapi.json",
        "X-API-Type": "rest",
        "X-Target-Headers": "{\"Authorization\": \"Bearer token\"}",
        "X-Poll-Paths": "[\"/api/reports/generate\"]"
      }
    }
  }
}
```

The agent will automatically use `poll_until_done` for `/api/reports/generate` instead of a regular REST call.

---

## 21. Programmatic Client Examples

API Agent uses the MCP protocol over **Streamable HTTP** (SSE). Below are complete, runnable examples in Python, Java, and Node.js showing how to:

1. Initialize a session
2. List available tools
3. Ask a natural language question (`{prefix}_query`)
4. Execute a direct API call (`{prefix}_execute`)

All examples connect to `http://localhost:3000/mcp` and query the Rick & Morty GraphQL API.

---

### 21.1 Python

**Requirements:** `pip install httpx` (or `pip install requests`)

```python
"""API Agent MCP Client — Python example using httpx."""

import httpx
import json

MCP_URL = "http://localhost:3000/mcp"

# Headers identifying the target API
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "X-Target-URL": "https://rickandmortyapi.com/graphql",
    "X-API-Type": "graphql",
    # For authenticated APIs, add:
    # "X-Target-Headers": json.dumps({"Authorization": "Bearer YOUR_TOKEN"}),
}


def parse_sse_response(response: httpx.Response) -> dict | None:
    """Parse SSE response and extract the result from the last data event."""
    for line in response.text.strip().splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:])
    # Non-SSE response (direct JSON)
    try:
        return response.json()
    except Exception:
        return None


def mcp_request(session_id: str | None, method: str, params: dict = None, req_id: int = 1) -> tuple[dict, str]:
    """Send an MCP JSON-RPC request and return (result, session_id)."""
    headers = {**API_HEADERS}
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
    }
    if params:
        payload["params"] = params

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(MCP_URL, json=payload, headers=headers)
        resp.raise_for_status()

        # Extract session ID from response headers
        new_session_id = resp.headers.get("mcp-session-id", session_id)
        data = parse_sse_response(resp)
        return data, new_session_id


def main():
    # ── Step 1: Initialize session ──────────────────────────────────
    print("1. Initializing MCP session...")
    result, session_id = mcp_request(
        session_id=None,
        method="initialize",
        params={
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "python-client", "version": "1.0"},
        },
    )
    print(f"   Session ID: {session_id}")
    print(f"   Server: {result.get('result', {}).get('serverInfo', {})}")

    # ── Step 2: List available tools ────────────────────────────────
    print("\n2. Listing tools...")
    result, session_id = mcp_request(session_id, "tools/list", req_id=2)
    tools = result.get("result", {}).get("tools", [])
    for tool in tools:
        print(f"   • {tool['name']}: {tool.get('description', '')[:80]}...")

    # ── Step 3: Natural language query ──────────────────────────────
    print("\n3. Asking: 'How many episodes are there in total?'")
    result, session_id = mcp_request(
        session_id,
        "tools/call",
        params={
            "name": "rickandmortyapi_query",
            "arguments": {
                "question": "How many episodes are there in total?",
            },
        },
        req_id=3,
    )
    # Extract structured content or text content
    structured = result.get("result", {}).get("structuredContent")
    if structured:
        print(f"   Answer: {json.dumps(structured, indent=2)}")
    else:
        content = result.get("result", {}).get("content", [])
        for c in content:
            print(f"   Answer: {c.get('text', '')[:500]}")

    # ── Step 4: Direct GraphQL execution ────────────────────────────
    print("\n4. Direct execute: fetching first 5 characters...")
    result, session_id = mcp_request(
        session_id,
        "tools/call",
        params={
            "name": "rickandmortyapi_execute",
            "arguments": {
                "query": "{ characters(page: 1) { results { name status species } } }",
            },
        },
        req_id=4,
    )
    structured = result.get("result", {}).get("structuredContent")
    if structured:
        data = structured.get("data", {})
        if isinstance(data, dict):
            characters = data.get("characters", {}).get("results", [])[:5]
            for ch in characters:
                print(f"   • {ch['name']} ({ch['species']}) - {ch['status']}")
        else:
            print(f"   Data: {str(data)[:500]}")
    else:
        content = result.get("result", {}).get("content", [])
        for c in content:
            print(f"   {c.get('text', '')[:500]}")

    print("\nDone!")


if __name__ == "__main__":
    main()
```

#### Python — Async Version (with `httpx`)

```python
"""API Agent MCP Client — async Python example."""

import asyncio
import json
import httpx

MCP_URL = "http://localhost:3000/mcp"
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "X-Target-URL": "https://rickandmortyapi.com/graphql",
    "X-API-Type": "graphql",
}


class MCPClient:
    """Simple MCP client for API Agent."""

    def __init__(self, base_url: str = MCP_URL, api_headers: dict = None):
        self.base_url = base_url
        self.api_headers = api_headers or API_HEADERS
        self.session_id: str | None = None
        self._req_id = 0

    async def _request(self, method: str, params: dict = None) -> dict:
        self._req_id += 1
        headers = {**self.api_headers}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {"jsonrpc": "2.0", "id": self._req_id, "method": method}
        if params:
            payload["params"] = params

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            resp.raise_for_status()
            self.session_id = resp.headers.get("mcp-session-id", self.session_id)

            for line in resp.text.strip().splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:])
            return resp.json()

    async def initialize(self) -> dict:
        """Initialize MCP session."""
        result = await self._request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "python-async-client", "version": "1.0"},
        })
        return result.get("result", {})

    async def list_tools(self) -> list[dict]:
        """List available tools."""
        result = await self._request("tools/list")
        return result.get("result", {}).get("tools", [])

    async def query(self, tool_name: str, question: str) -> dict:
        """Ask a natural language question."""
        result = await self._request("tools/call", {
            "name": tool_name,
            "arguments": {"question": question},
        })
        return result.get("result", {}).get("structuredContent") or result.get("result", {})

    async def execute(self, tool_name: str, **kwargs) -> dict:
        """Execute a direct API call."""
        result = await self._request("tools/call", {
            "name": tool_name,
            "arguments": kwargs,
        })
        return result.get("result", {}).get("structuredContent") or result.get("result", {})


async def main():
    client = MCPClient()

    # Initialize
    info = await client.initialize()
    print(f"Connected: {info.get('serverInfo', {}).get('name')}")

    # List tools
    tools = await client.list_tools()
    print(f"Tools: {[t['name'] for t in tools]}")

    # Natural language query
    answer = await client.query("rickandmortyapi_query", "List all dead human characters")
    print(f"Answer: {json.dumps(answer, indent=2)[:1000]}")

    # Direct execution
    data = await client.execute(
        "rickandmortyapi_execute",
        query="{ episodes(page: 1) { results { name episode air_date } } }",
    )
    print(f"Episodes: {json.dumps(data, indent=2)[:1000]}")


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 21.2 Node.js / TypeScript

**Requirements:** `npm install node-fetch` (Node 18+ has built-in fetch)

```javascript
/**
 * API Agent MCP Client — Node.js example.
 * Works with Node 18+ (built-in fetch) or install node-fetch for older versions.
 */

const MCP_URL = "http://localhost:3000/mcp";

const API_HEADERS = {
  "Content-Type": "application/json",
  Accept: "application/json, text/event-stream",
  "X-Target-URL": "https://rickandmortyapi.com/graphql",
  "X-API-Type": "graphql",
  // For authenticated APIs:
  // "X-Target-Headers": JSON.stringify({ Authorization: "Bearer YOUR_TOKEN" }),
};

let sessionId = null;
let reqId = 0;

/**
 * Parse SSE response body to extract JSON result.
 */
function parseSSE(body) {
  for (const line of body.split("\n")) {
    if (line.startsWith("data:")) {
      return JSON.parse(line.slice(5));
    }
  }
  return JSON.parse(body);
}

/**
 * Send an MCP JSON-RPC request.
 */
async function mcpRequest(method, params = undefined) {
  reqId++;
  const headers = { ...API_HEADERS };
  if (sessionId) {
    headers["Mcp-Session-Id"] = sessionId;
  }

  const payload = { jsonrpc: "2.0", id: reqId, method };
  if (params) payload.params = params;

  const resp = await fetch(MCP_URL, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
  }

  // Capture session ID
  sessionId = resp.headers.get("mcp-session-id") || sessionId;

  const body = await resp.text();
  return parseSSE(body);
}

/**
 * Extract answer from MCP tool call result.
 */
function extractAnswer(result) {
  const structured = result?.result?.structuredContent;
  if (structured) return structured;

  const content = result?.result?.content;
  if (Array.isArray(content)) {
    return content.map((c) => c.text).join("\n");
  }
  return result;
}

async function main() {
  // ── Step 1: Initialize ───────────────────────────────────────────
  console.log("1. Initializing MCP session...");
  const initResult = await mcpRequest("initialize", {
    protocolVersion: "2025-03-26",
    capabilities: {},
    clientInfo: { name: "node-client", version: "1.0" },
  });
  console.log(`   Session: ${sessionId}`);
  console.log(`   Server: ${JSON.stringify(initResult.result?.serverInfo)}`);

  // ── Step 2: List tools ───────────────────────────────────────────
  console.log("\n2. Listing tools...");
  const toolsResult = await mcpRequest("tools/list");
  const tools = toolsResult.result?.tools || [];
  tools.forEach((t) => console.log(`   • ${t.name}`));

  // ── Step 3: Natural language query ───────────────────────────────
  console.log("\n3. Asking: 'How many episodes are there?'");
  const queryResult = await mcpRequest("tools/call", {
    name: "rickandmortyapi_query",
    arguments: { question: "How many episodes are there in total?" },
  });
  const answer = extractAnswer(queryResult);
  console.log(`   Answer: ${JSON.stringify(answer, null, 2).slice(0, 500)}`);

  // ── Step 4: Direct execution ─────────────────────────────────────
  console.log("\n4. Direct execute: first 5 characters...");
  const execResult = await mcpRequest("tools/call", {
    name: "rickandmortyapi_execute",
    arguments: {
      query: "{ characters(page: 1) { results { name status species } } }",
    },
  });
  const execAnswer = extractAnswer(execResult);
  const characters =
    execAnswer?.data?.characters?.results?.slice(0, 5) || [];
  characters.forEach((ch) =>
    console.log(`   • ${ch.name} (${ch.species}) - ${ch.status}`)
  );

  // ── Step 5: Complex query with SQL post-processing ───────────────
  console.log("\n5. Complex query: 'Count characters by species, top 5'");
  const complexResult = await mcpRequest("tools/call", {
    name: "rickandmortyapi_query",
    arguments: {
      question:
        "Count characters per species and show the top 5 most common species",
    },
  });
  const complexAnswer = extractAnswer(complexResult);
  console.log(`   Answer: ${JSON.stringify(complexAnswer, null, 2).slice(0, 500)}`);

  console.log("\nDone!");
}

main().catch(console.error);
```

#### Node.js — TypeScript Version with Class Wrapper

```typescript
/**
 * API Agent MCP Client — TypeScript example.
 * Usage: npx tsx client.ts
 */

interface MCPResult {
  jsonrpc: string;
  id: number;
  result?: {
    tools?: Array<{ name: string; description: string }>;
    content?: Array<{ type: string; text: string }>;
    structuredContent?: Record<string, unknown>;
    serverInfo?: { name: string; version: string };
  };
  error?: { code: number; message: string };
}

interface MCPClientOptions {
  baseUrl: string;
  targetUrl: string;
  apiType: "graphql" | "rest";
  targetHeaders?: Record<string, string>;
  apiName?: string;
  baseUrlOverride?: string;
}

class MCPClient {
  private baseUrl: string;
  private headers: Record<string, string>;
  private sessionId: string | null = null;
  private reqId = 0;

  constructor(options: MCPClientOptions) {
    this.baseUrl = options.baseUrl;
    this.headers = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
      "X-Target-URL": options.targetUrl,
      "X-API-Type": options.apiType,
    };
    if (options.targetHeaders) {
      this.headers["X-Target-Headers"] = JSON.stringify(options.targetHeaders);
    }
    if (options.apiName) {
      this.headers["X-API-Name"] = options.apiName;
    }
    if (options.baseUrlOverride) {
      this.headers["X-Base-URL"] = options.baseUrlOverride;
    }
  }

  private async request(method: string, params?: Record<string, unknown>): Promise<MCPResult> {
    this.reqId++;
    const headers: Record<string, string> = { ...this.headers };
    if (this.sessionId) headers["Mcp-Session-Id"] = this.sessionId;

    const payload: Record<string, unknown> = { jsonrpc: "2.0", id: this.reqId, method };
    if (params) payload.params = params;

    const resp = await fetch(this.baseUrl, {
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

  async initialize(): Promise<MCPResult> {
    return this.request("initialize", {
      protocolVersion: "2025-03-26",
      capabilities: {},
      clientInfo: { name: "ts-client", version: "1.0" },
    });
  }

  async listTools(): Promise<Array<{ name: string; description: string }>> {
    const result = await this.request("tools/list");
    return result.result?.tools || [];
  }

  async query(toolName: string, question: string): Promise<unknown> {
    const result = await this.request("tools/call", {
      name: toolName,
      arguments: { question },
    });
    return result.result?.structuredContent || result.result;
  }

  async execute(toolName: string, args: Record<string, unknown>): Promise<unknown> {
    const result = await this.request("tools/call", {
      name: toolName,
      arguments: args,
    });
    return result.result?.structuredContent || result.result;
  }
}

// ── Usage ──────────────────────────────────────────────────────────
async function main() {
  const client = new MCPClient({
    baseUrl: "http://localhost:3000/mcp",
    targetUrl: "https://rickandmortyapi.com/graphql",
    apiType: "graphql",
  });

  await client.initialize();
  console.log("Connected!");

  const tools = await client.listTools();
  console.log("Tools:", tools.map((t) => t.name));

  const answer = await client.query(
    "rickandmortyapi_query",
    "What are the top 5 most common species?"
  );
  console.log("Answer:", JSON.stringify(answer, null, 2).slice(0, 1000));
}

main().catch(console.error);
```

---

### 21.3 Java

**Requirements:** Java 11+ (uses `java.net.http.HttpClient`). No external dependencies needed.

```java
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * API Agent MCP Client — Java example.
 * Uses only java.net.http (no external dependencies).
 *
 * Compile: javac MCPClient.java
 * Run:     java MCPClient
 */
public class MCPClient {

    private static final String MCP_URL = "http://localhost:3000/mcp";
    private static final String TARGET_URL = "https://rickandmortyapi.com/graphql";
    private static final String API_TYPE = "graphql";

    private final HttpClient httpClient;
    private final AtomicInteger reqId = new AtomicInteger(0);
    private String sessionId = null;

    public MCPClient() {
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .build();
    }

    /**
     * Parse SSE response to extract JSON from "data:" lines.
     */
    private String parseSSE(String body) {
        for (String line : body.split("\n")) {
            if (line.startsWith("data:")) {
                return line.substring(5).trim();
            }
        }
        return body; // Not SSE, return as-is
    }

    /**
     * Send MCP JSON-RPC request.
     */
    public String mcpRequest(String method, String params) throws Exception {
        int id = reqId.incrementAndGet();

        // Build JSON-RPC payload
        StringBuilder payload = new StringBuilder();
        payload.append("{\"jsonrpc\":\"2.0\",\"id\":").append(id);
        payload.append(",\"method\":\"").append(method).append("\"");
        if (params != null) {
            payload.append(",\"params\":").append(params);
        }
        payload.append("}");

        // Build request with headers
        HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                .uri(URI.create(MCP_URL))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json")
                .header("Accept", "application/json, text/event-stream")
                .header("X-Target-URL", TARGET_URL)
                .header("X-API-Type", API_TYPE)
                .POST(HttpRequest.BodyPublishers.ofString(payload.toString()));

        if (sessionId != null) {
            requestBuilder.header("Mcp-Session-Id", sessionId);
        }

        HttpResponse<String> response = httpClient.send(
                requestBuilder.build(),
                HttpResponse.BodyHandlers.ofString()
        );

        if (response.statusCode() != 200) {
            throw new RuntimeException("HTTP " + response.statusCode() + ": " + response.body());
        }

        // Extract session ID from response headers
        response.headers().firstValue("mcp-session-id").ifPresent(id1 -> sessionId = id1);

        return parseSSE(response.body());
    }

    public static void main(String[] args) throws Exception {
        MCPClient client = new MCPClient();

        // ── Step 1: Initialize session ────────────────────────────
        System.out.println("1. Initializing MCP session...");
        String initResult = client.mcpRequest("initialize",
                "{" +
                "\"protocolVersion\":\"2025-03-26\"," +
                "\"capabilities\":{}," +
                "\"clientInfo\":{\"name\":\"java-client\",\"version\":\"1.0\"}" +
                "}"
        );
        System.out.println("   Session: " + client.sessionId);
        System.out.println("   Response: " + initResult.substring(0, Math.min(200, initResult.length())));

        // ── Step 2: List tools ────────────────────────────────────
        System.out.println("\n2. Listing tools...");
        String toolsResult = client.mcpRequest("tools/list", null);
        System.out.println("   Tools: " + toolsResult.substring(0, Math.min(500, toolsResult.length())));

        // ── Step 3: Natural language query ─────────────────────────
        System.out.println("\n3. Asking: 'How many episodes are there?'");
        String queryResult = client.mcpRequest("tools/call",
                "{" +
                "\"name\":\"rickandmortyapi_query\"," +
                "\"arguments\":{\"question\":\"How many episodes are there in total?\"}" +
                "}"
        );
        System.out.println("   Answer: " + queryResult.substring(0, Math.min(500, queryResult.length())));

        // ── Step 4: Direct GraphQL execution ──────────────────────
        System.out.println("\n4. Direct execute: fetching characters...");
        String execResult = client.mcpRequest("tools/call",
                "{" +
                "\"name\":\"rickandmortyapi_execute\"," +
                "\"arguments\":{" +
                    "\"query\":\"{ characters(page: 1) { results { name status species } } }\"" +
                "}" +
                "}"
        );
        System.out.println("   Result: " + execResult.substring(0, Math.min(500, execResult.length())));

        // ── Step 5: Complex query ─────────────────────────────────
        System.out.println("\n5. Complex: 'Top 5 species by character count'");
        String complexResult = client.mcpRequest("tools/call",
                "{" +
                "\"name\":\"rickandmortyapi_query\"," +
                "\"arguments\":{\"question\":\"Count characters per species, show top 5 sorted by count\"}" +
                "}"
        );
        System.out.println("   Answer: " + complexResult.substring(0, Math.min(500, complexResult.length())));

        System.out.println("\nDone!");
    }
}
```

#### Java — With Jackson JSON Library (Cleaner)

If you have Jackson on your classpath (e.g., Spring Boot projects):

```java
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * API Agent MCP Client — Java + Jackson example.
 */
public class MCPClientJackson {

    private static final String MCP_URL = "http://localhost:3000/mcp";
    private static final ObjectMapper mapper = new ObjectMapper();

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    private String sessionId;
    private int reqId = 0;

    // Configuration
    private final String targetUrl;
    private final String apiType;
    private final String targetHeaders; // JSON string or null

    public MCPClientJackson(String targetUrl, String apiType, String targetHeaders) {
        this.targetUrl = targetUrl;
        this.apiType = apiType;
        this.targetHeaders = targetHeaders;
    }

    public JsonNode request(String method, JsonNode params) throws Exception {
        reqId++;

        ObjectNode payload = mapper.createObjectNode();
        payload.put("jsonrpc", "2.0");
        payload.put("id", reqId);
        payload.put("method", method);
        if (params != null) payload.set("params", params);

        HttpRequest.Builder rb = HttpRequest.newBuilder()
                .uri(URI.create(MCP_URL))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json")
                .header("Accept", "application/json, text/event-stream")
                .header("X-Target-URL", targetUrl)
                .header("X-API-Type", apiType)
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(payload)));

        if (targetHeaders != null) rb.header("X-Target-Headers", targetHeaders);
        if (sessionId != null) rb.header("Mcp-Session-Id", sessionId);

        HttpResponse<String> resp = httpClient.send(rb.build(), HttpResponse.BodyHandlers.ofString());
        resp.headers().firstValue("mcp-session-id").ifPresent(s -> sessionId = s);

        String body = resp.body();
        for (String line : body.split("\n")) {
            if (line.startsWith("data:")) {
                return mapper.readTree(line.substring(5).trim());
            }
        }
        return mapper.readTree(body);
    }

    public JsonNode initialize() throws Exception {
        ObjectNode params = mapper.createObjectNode();
        params.put("protocolVersion", "2025-03-26");
        params.putObject("capabilities");
        ObjectNode clientInfo = params.putObject("clientInfo");
        clientInfo.put("name", "java-jackson-client");
        clientInfo.put("version", "1.0");
        return request("initialize", params);
    }

    public JsonNode listTools() throws Exception {
        return request("tools/list", null);
    }

    public JsonNode query(String toolName, String question) throws Exception {
        ObjectNode params = mapper.createObjectNode();
        params.put("name", toolName);
        ObjectNode args = params.putObject("arguments");
        args.put("question", question);
        return request("tools/call", params);
    }

    public JsonNode execute(String toolName, ObjectNode arguments) throws Exception {
        ObjectNode params = mapper.createObjectNode();
        params.put("name", toolName);
        params.set("arguments", arguments);
        return request("tools/call", params);
    }

    // ── Usage ──────────────────────────────────────────────────────
    public static void main(String[] args) throws Exception {
        MCPClientJackson client = new MCPClientJackson(
                "https://rickandmortyapi.com/graphql",
                "graphql",
                null // no auth needed
        );

        // Initialize
        client.initialize();
        System.out.println("Connected! Session: " + client.sessionId);

        // List tools
        JsonNode tools = client.listTools();
        System.out.println("Tools: " + tools.path("result").path("tools"));

        // Natural language query
        JsonNode answer = client.query("rickandmortyapi_query",
                "Show all locations of type Planet with their dimension");
        System.out.println("Answer: " + answer.toPrettyString().substring(0, 500));

        // Direct execution
        ObjectNode execArgs = mapper.createObjectNode();
        execArgs.put("query", "{ episodes(page: 1) { results { name episode } } }");
        JsonNode episodes = client.execute("rickandmortyapi_execute", execArgs);
        System.out.println("Episodes: " + episodes.toPrettyString().substring(0, 500));
    }
}
```

---

### 21.4 REST API Example (All Languages)

The examples above use a GraphQL target. Here's how to adapt for a **REST API**:

#### Python (REST)

```python
# Change the headers for a REST API
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "X-Target-URL": "https://petstore3.swagger.io/api/v3/openapi.json",
    "X-API-Type": "rest",
    "X-Base-URL": "https://petstore3.swagger.io/api/v3",
    # For auth: "X-Target-Headers": json.dumps({"Authorization": "Bearer token"}),
}

# Tool names change based on hostname
# petstore3_swagger_query, petstore3_swagger_execute

# NL query
result = await client.query("petstore3_swagger_query", "What pets are available?")

# Direct REST execution
result = await client.execute("petstore3_swagger_execute",
    method="GET",
    path="/pet/findByStatus",
    query_params={"status": "available"},
)
```

#### Node.js (REST)

```javascript
const API_HEADERS = {
  "Content-Type": "application/json",
  Accept: "application/json, text/event-stream",
  "X-Target-URL": "https://petstore3.swagger.io/api/v3/openapi.json",
  "X-API-Type": "rest",
  "X-Base-URL": "https://petstore3.swagger.io/api/v3",
};

// Direct REST call
const result = await mcpRequest("tools/call", {
  name: "petstore3_swagger_execute",
  arguments: {
    method: "GET",
    path: "/pet/findByStatus",
    query_params: { status: "available" },
  },
});
```

#### Java (REST)

```java
// Change constructor for REST API
MCPClientJackson client = new MCPClientJackson(
    "https://petstore3.swagger.io/api/v3/openapi.json",
    "rest",
    null
);
// Also add X-Base-URL header in the request builder:
// rb.header("X-Base-URL", "https://petstore3.swagger.io/api/v3");

// Direct REST execution
ObjectNode args = mapper.createObjectNode();
args.put("method", "GET");
args.put("path", "/pet/findByStatus");
ObjectNode qp = args.putObject("query_params");
qp.put("status", "available");
JsonNode pets = client.execute("petstore3_swagger_execute", args);
```

---

### 21.5 cURL Quick Reference

For quick testing without code:

```bash
# ── Initialize session ──────────────────────────────────────────
SESSION=$(curl -s -D - -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-Target-URL: https://rickandmortyapi.com/graphql" \
  -H "X-API-Type: graphql" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}' \
  2>/dev/null | grep -i "mcp-session-id" | awk '{print $2}' | tr -d '\r')

echo "Session: $SESSION"

# ── List tools ──────────────────────────────────────────────────
curl -s -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "X-Target-URL: https://rickandmortyapi.com/graphql" \
  -H "X-API-Type: graphql" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

# ── Natural language query ──────────────────────────────────────
curl -s -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "X-Target-URL: https://rickandmortyapi.com/graphql" \
  -H "X-API-Type: graphql" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"rickandmortyapi_query","arguments":{"question":"How many episodes exist?"}}}'

# ── Direct execution ────────────────────────────────────────────
curl -s -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION" \
  -H "X-Target-URL: https://rickandmortyapi.com/graphql" \
  -H "X-API-Type: graphql" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"rickandmortyapi_execute","arguments":{"query":"{ characters(page:1) { results { name status } } }"}}}'
```
