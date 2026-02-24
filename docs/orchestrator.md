# Orchestrator Design — Tool Discovery, Ordering & Workflow Inference

> **Goal**: Enable an LLM orchestrator to discover MCP tools, understand their relationships, determine correct execution order, and compose them into workflows — ranging from zero-config inference to fully declarative workflow definitions.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [What the Orchestrator Sees Today](#what-the-orchestrator-sees-today)
3. [Design Principle](#design-principle)
4. [Strategy 1 — Self-Describing Tools](#strategy-1--self-describing-tools)
5. [Strategy 2 — MCP Resources (Workflow Graphs)](#strategy-2--mcp-resources-workflow-graphs)
6. [Strategy 3 — Composite Workflow Tools (DAG Engine)](#strategy-3--composite-workflow-tools-dag-engine)
7. [How to Begin a Workflow](#how-to-begin-a-workflow)
8. [How to Infer Workflows from Tool Metadata](#how-to-infer-workflows-from-tool-metadata)
9. [Workflow Definition Formats](#workflow-definition-formats)
10. [Implementation Plan](#implementation-plan)
11. [Examples](#examples)
12. [Comparison of Strategies](#comparison-of-strategies)
13. [Open Questions](#open-questions)

---

## The Problem

When an LLM orchestrator connects to an MCP server, it calls `tools/list` and receives a flat list of tools. Each tool has three pieces of information:

| Field         | What it contains                     | What's missing                        |
|---------------|--------------------------------------|---------------------------------------|
| `name`        | Tool identifier (e.g. `flights_query`) | No grouping, no relationships        |
| `description` | Free-text purpose                    | No dependency info, no output schema |
| `inputSchema` | JSON Schema for parameters           | No output schema, no chaining hints  |

The orchestrator has **zero information** about:

1. **Tool relationships** — which tools depend on which
2. **Execution order** — what sequence to follow for a business process
3. **Data flow** — how the output of tool A feeds into the input of tool B
4. **Business rules** — domain-specific constraints (e.g., "check availability before booking")
5. **Error recovery** — what to do when a step fails, what to rollback

This means the LLM must **guess** the correct sequence. For simple cases (fetching data from one API), this works. For multi-step business processes across multiple tools, it fails.

### Example: Travel Booking Domain

A domain exposes 10 tools:

```
search_flights, check_availability, create_booking, process_payment,
search_hotels, book_hotel, confirm_trip, cancel_booking, cancel_hotel,
add_to_waitlist
```

The correct booking workflow is:

```
search_flights → check_availability → (if available) create_booking → process_payment
```

But the LLM has no way to know this. It might try `create_booking` first (fails — no flight selected), skip `check_availability` (books an unavailable flight), or call `process_payment` before `create_booking` (nothing to pay for).

---

## What the Orchestrator Sees Today

When an MCP client initializes a session with the API Agent server, the tool discovery flow is:

```
Client                          MCP Server
  │                                │
  │─── POST /mcp ──────────────────▶
  │    initialize                   │
  │◀── session_id ──────────────────│
  │                                │
  │─── POST /mcp ──────────────────▶
  │    tools/list                   │
  │    Headers:                     │
  │      X-Target-URL: ...         │
  │      X-API-Type: graphql|rest  │
  │◀── tool list ───────────────────│
  │                                │
  │    [                            │
  │      {                          │
  │        "name": "flights_query", │
  │        "description": "[flights.example.com GraphQL API] Ask questions...",
  │        "inputSchema": { "question": "string" }
  │      },                         │
  │      {                          │
  │        "name": "flights_execute",
  │        "description": "[flights.example.com GraphQL API] Execute a specific...",
  │        "inputSchema": { "query": "string", "variables": "object" }
  │      },                         │
  │      {                          │
  │        "name": "r_get_top_flights",  ← auto-learned recipe
  │        "description": "...",    │
  │        "inputSchema": { "limit": "integer" }
  │      }                          │
  │    ]                            │
```

The orchestrator gets:
- **Core tools**: `{prefix}_query` (natural language) and `{prefix}_execute` (direct API call)
- **Recipe tools**: `r_{name}` (auto-learned parameterized pipelines from past successful runs)

This is sufficient for **single-API interactions** because the internal agent (GraphQL or REST agent) handles multi-step reasoning within a single API. But when the orchestrator needs to **coordinate across multiple APIs** or follow **domain-specific business processes**, the flat tool list is insufficient.

---

## Design Principle

**Put deterministic logic in the workflow engine, put reasoning in the LLM.**

| Responsibility | Who handles it | Why |
|---|---|---|
| Intent matching | LLM | Natural language understanding, ambiguity resolution |
| Parameter extraction | LLM | Parsing dates, names, IDs from user input |
| Disambiguation | LLM | "Did you mean London, UK or London, Ontario?" |
| Tool sequencing | Workflow engine | Deterministic, testable, auditable |
| Branching logic | Workflow engine | Conditions evaluated against real data |
| Parallelism | Workflow engine | `asyncio.gather`, not LLM reasoning |
| Retry / rollback | Workflow engine | Reliable error recovery |

The LLM decides **WHAT** to do. The workflow engine decides **HOW** to do it.

---

## Strategy 1 — Self-Describing Tools

**Complexity: Low | Config: Header-based | Enforcement: None (advisory)**

Enrich tool descriptions with structured metadata so the LLM can infer correct ordering. No new tools, no engine — just better descriptions.

### How It Works

The domain team provides an `X-Tool-Hints` header when configuring the MCP client. The middleware reads these hints and appends structured metadata to each tool's description before returning them to the orchestrator.

### Configuration

```json
{
  "mcpServers": {
    "flights": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://flights.example.com/graphql",
        "X-API-Type": "graphql",
        "X-Tool-Hints": {
          "search_flights": {
            "category": "search",
            "outputs": ["flight_id", "airline", "price", "departure", "arrival"],
            "next": ["check_availability"],
            "hint": "Always search before booking. Results contain flight_id needed by downstream tools."
          },
          "check_availability": {
            "category": "validation",
            "requires": ["search_flights"],
            "outputs": ["seats_available", "cabin_class"],
            "next": ["create_booking", "add_to_waitlist"],
            "hint": "Requires flight_id from search_flights. Must confirm availability before booking."
          },
          "create_booking": {
            "category": "booking",
            "requires": ["check_availability"],
            "outputs": ["booking_id", "status", "total_price"],
            "next": ["process_payment"],
            "hint": "Only call after check_availability confirms seats. Returns booking_id for payment."
          },
          "process_payment": {
            "category": "payment",
            "requires": ["create_booking"],
            "outputs": ["payment_id", "receipt_url"],
            "hint": "Final step. Requires booking_id from create_booking."
          }
        }
      }
    }
  }
}
```

### What the LLM Sees

After middleware processing, tool descriptions become:

```
flights_query
[flights.example.com GraphQL API] Ask questions about the API in natural language.

flights_execute
[flights.example.com GraphQL API] Execute a specific API call directly.

search_flights
[flights.example.com GraphQL API] Search available flights.
  ├─ Category: search
  ├─ Outputs: flight_id, airline, price, departure, arrival
  ├─ Next: check_availability
  └─ Hint: Always search before booking. Results contain flight_id needed by downstream tools.

check_availability
[flights.example.com GraphQL API] Check seat availability.
  ├─ Category: validation
  ├─ Requires: search_flights
  ├─ Outputs: seats_available, cabin_class
  ├─ Next: create_booking, add_to_waitlist
  └─ Hint: Requires flight_id from search_flights. Must confirm availability before booking.

create_booking
[flights.example.com GraphQL API] Reserve a flight.
  ├─ Category: booking
  ├─ Requires: check_availability
  ├─ Outputs: booking_id, status, total_price
  ├─ Next: process_payment
  └─ Hint: Only call after check_availability confirms seats. Returns booking_id for payment.
```

An LLM can now read these descriptions and reason:
1. User wants to book a flight → I need `search_flights` first (it has no `requires`)
2. After search, call `check_availability` (it requires `search_flights`, search's `next` points here)
3. If available, call `create_booking` (requires `check_availability`)
4. Then `process_payment` (requires `create_booking`)

### Implementation

**Modified files:**
- `context.py` — Parse `X-Tool-Hints` header into `RequestContext`
- `middleware.py` — Append hint metadata to tool descriptions in `on_list_tools`

**No new modules required.** This is purely additive to existing middleware.

### Limitations

- LLMs can still ignore hints — there is no enforcement
- Works best for linear/simple branching flows
- No execution guarantee or error recovery
- Hints are advisory, not programmatic

---

## Strategy 2 — MCP Resources (Workflow Graphs)

**Complexity: Medium | Config: Header or file-based | Enforcement: None (advisory)**

Expose workflow definitions as **MCP resources** that the orchestrator reads before planning. Resources are read-only data the client can fetch to understand the domain.

### How It Works

The MCP server registers resources that describe workflow graphs. When the orchestrator starts a session, it reads these resources to build a mental model of the domain before making any tool calls.

```
Client                          MCP Server
  │                                │
  │─── resources/list ─────────────▶
  │◀── resource URIs ──────────────│
  │                                │
  │    [                            │
  │      "workflow://flights/overview",
  │      "workflow://flights/book_flight",
  │      "workflow://flights/cancel_booking"
  │    ]                            │
  │                                │
  │─── resources/read ─────────────▶
  │    uri: workflow://flights/overview
  │◀── resource content ───────────│
```

### Resource Content (Natural Language)

```
URI: workflow://flights/overview

# Flights API — Workflow Guide

## Available Workflows

### 1. Book a Flight
Steps: search_flights → check_availability → create_booking → process_payment
- search_flights: Returns flight options. Pass flight_id to next step.
- check_availability: Checks seats. If 0, use add_to_waitlist instead.
- create_booking: Reserves the flight. Returns booking_id.
- process_payment: Charges customer. Final step.

### 2. Cancel a Booking
Steps: get_booking → cancel_booking → process_refund
- get_booking: Retrieve booking details by booking_id.
- cancel_booking: Cancel if status is "confirmed".
- process_refund: Automatic if cancellation within 24 hours.

## Rules
- Never call create_booking without check_availability first.
- process_payment is irreversible.
- Cancellations after 24 hours incur a fee.
```

### Resource Content (Structured — JSON/YAML)

```
URI: workflow://flights/book_flight

{
  "workflow": "book_flight",
  "description": "End-to-end flight booking process",
  "steps": [
    {
      "id": "search",
      "tool": "search_flights",
      "inputs": {"origin": "$user", "destination": "$user", "date": "$user"},
      "outputs": {"flight_id": "$.results[0].id", "options": "$.results"}
    },
    {
      "id": "check",
      "tool": "check_availability",
      "depends_on": ["search"],
      "inputs": {"flight_id": "$search.flight_id"},
      "outputs": {"available": "$.seats_available > 0"}
    },
    {
      "id": "book",
      "tool": "create_booking",
      "depends_on": ["check"],
      "condition": "$check.available == true",
      "inputs": {"flight_id": "$search.flight_id", "passenger": "$user"},
      "outputs": {"booking_id": "$.booking_id"}
    },
    {
      "id": "pay",
      "tool": "process_payment",
      "depends_on": ["book"],
      "inputs": {"booking_id": "$book.booking_id"},
      "outputs": {"receipt": "$.receipt_url"}
    }
  ]
}
```

### Configuration

```json
{
  "mcpServers": {
    "flights": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://flights.example.com/graphql",
        "X-API-Type": "graphql",
        "X-Workflow-Resources": "https://team.example.com/workflows/flights.yaml"
      }
    }
  }
}
```

### Implementation

**New files:**
- `api_agent/workflow/resources.py` — Register workflow resources with FastMCP

**Modified files:**
- `context.py` — Parse `X-Workflow-Resources` header
- `__main__.py` — Register workflow resources on app creation

### Limitations

- Requires the LLM to read and follow the resource content
- No execution enforcement — the orchestrator might still call tools in the wrong order
- Better for documentation than enforcement

---

## Strategy 3 — Composite Workflow Tools (DAG Engine)

**Complexity: High | Config: YAML/JSON spec | Enforcement: Full (engine-driven)**

Domain teams author workflow specifications (YAML/JSON/XML). Each workflow is exposed as a single composite MCP tool (`w_*`) with a DAG engine handling execution deterministically.

### How It Works

```
User: "Book me a flight from NYC to Paris next week"
  │
  ▼
LLM Orchestrator
  │  Sees: w_book_flight(origin, destination, date, passenger)
  │  Decision: this matches w_book_flight
  │  Calls: w_book_flight(origin="NYC", destination="Paris",
  │                        date="2026-02-26", passenger="John")
  │
  ▼
Workflow Engine (inside MCP server)
  │  Loads workflow spec
  │  Executes DAG deterministically:
  │    1. search_flights(origin="NYC", dest="Paris", date="2026-02-26")
  │    2. check_availability(flight_id=results[0].id)
  │    3. if available → create_booking(flight_id, passenger="John")
  │    4. process_payment(booking_id)
  │  Returns final result
  │
  ▼
LLM receives: { "booking_id": "BK-123", "receipt": "..." }
```

The LLM does NOT reason about tool order — it just picks the right workflow and provides parameters. The engine handles everything deterministically.

### Configuration

```json
{
  "mcpServers": {
    "flights": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://flights.example.com/graphql",
        "X-API-Type": "graphql",
        "X-Workflow-URL": "https://team.example.com/workflows.yaml"
      }
    }
  }
}
```

### Workflow Specification Format

See [Workflow Definition Formats](#workflow-definition-formats) for full YAML, JSON, and XML examples.

### What the Orchestrator Sees

```
Tool: w_book_flight

[flights.example.com GraphQL API] Search, check availability, and book a flight.

┌─ Workflow: book_flight ─────────────────────────────────────┐
│                                                              │
│  search_flights → check_availability → create_booking        │
│                                        ↘ add_to_waitlist     │
│                                                              │
│  On failure: retry 2x, then fail with message               │
│                                                              │
│  Params:                                                     │
│    origin (str, required)                                    │
│    destination (str, required)                               │
│    date (date, required)                                     │
│    passenger (str, required)                                 │
└──────────────────────────────────────────────────────────────┘
```

The orchestrator only needs to:
1. Recognize the user wants to book a flight
2. Extract: origin, destination, date, passenger
3. Call `w_book_flight` with those params

### Implementation

**New module: `api_agent/workflow/`**

```
api_agent/workflow/
├── __init__.py
├── models.py      ← WorkflowDef, StepDef, WorkflowResult dataclasses
├── loader.py      ← Fetch and parse YAML/JSON/XML workflow specs from URL
├── resolver.py    ← $reference resolution engine for data flow
└── engine.py      ← DAG executor (branch, parallel, loop, yield, compensate)
```

**Modified files:**

| File | Change |
|---|---|
| `context.py` | Parse `X-Workflow-URL` header |
| `middleware.py` | Load workflow spec, expose `w_*` tools, route `w_*` calls to engine |
| `config.py` | Add `ENABLE_WORKFLOWS` setting |

---

## How to Begin a Workflow

### From the Orchestrator's Perspective

The orchestrator (LLM client) follows this decision tree when a user makes a request:

```
User Request
    │
    ▼
┌─────────────────────────────────┐
│  1. DISCOVER                     │
│  Call tools/list                 │
│  Read workflow resources         │
│  (if Strategy 2 or 3 enabled)   │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  2. CLASSIFY                     │
│  Does this match a w_* tool?    │──── Yes ──▶ Call w_* tool (Strategy 3)
│  (composite workflow)            │            Engine handles everything.
└────────────┬────────────────────┘
             │ No
             ▼
┌─────────────────────────────────┐
│  Does this match an r_* tool?   │──── Yes ──▶ Call r_* tool (Recipe)
│  (learned recipe)                │            Single API call + SQL.
└────────────┬────────────────────┘
             │ No
             ▼
┌─────────────────────────────────┐
│  Can I infer a multi-tool       │──── Yes ──▶ Read tool hints/resources,
│  sequence from hints?           │            call tools in inferred order.
│  (Strategy 1 or 2)              │            (Strategy 1/2)
└────────────┬────────────────────┘
             │ No
             ▼
┌─────────────────────────────────┐
│  3. FALLBACK                     │
│  Use {prefix}_query tool         │            The internal agent handles
│  (natural language query)        │            multi-step reasoning within
│  for single-API questions        │            a single API.
└─────────────────────────────────┘
```

### From the API Provider's Perspective

The domain team sets up workflow support in increasing order of effort:

| Step | Effort | What to do |
|------|--------|------------|
| 1. Expose APIs | Minimal | Point `X-Target-URL` at your GraphQL/OpenAPI spec |
| 2. Add tool hints | Low | Add `X-Tool-Hints` header with dependency info |
| 3. Write workflow resources | Medium | Create natural language workflow descriptions |
| 4. Author workflow specs | High | Write YAML/JSON/XML workflow definitions |

### Starting a Workflow — Step by Step

**Step 1: Session initialization**

The MCP client connects and provides API configuration via headers:

```json
{
  "X-Target-URL": "https://flights.example.com/graphql",
  "X-API-Type": "graphql",
  "X-Tool-Hints": { ... },
  "X-Workflow-URL": "https://team.example.com/workflows.yaml"
}
```

**Step 2: Tool discovery**

The orchestrator calls `tools/list` and receives:
- Core tools: `flights_query`, `flights_execute`
- Recipe tools: `r_get_top_flights`, `r_search_by_route`
- Workflow tools: `w_book_flight`, `w_cancel_booking`, `w_book_trip`

**Step 3: Resource discovery (optional)**

If workflow resources are registered, the orchestrator calls `resources/list` and reads workflow documentation.

**Step 4: Intent matching**

When the user says "Book me a flight from NYC to Paris," the orchestrator matches this to `w_book_flight` based on the tool description.

**Step 5: Parameter extraction**

The LLM extracts parameters from natural language:
- origin: "NYC"
- destination: "Paris"
- date: "2026-02-26" (inferred from "next week")
- passenger: (asks user if not provided)

**Step 6: Execution**

The orchestrator calls `w_book_flight(origin="NYC", destination="Paris", date="2026-02-26", passenger="John")`. The workflow engine takes over.

---

## How to Infer Workflows from Tool Metadata

This section addresses the question: **given only tool descriptions and schemas, can the orchestrator figure out the correct tool order?**

### Inference Approach 1: Input/Output Matching

The most reliable inference method matches **outputs of one tool** to **inputs of another**.

```
Tool A: search_flights
  inputSchema: { origin: str, destination: str, date: str }
  outputs (from hints): flight_id, airline, price

Tool B: check_availability
  inputSchema: { flight_id: str }
  outputs (from hints): seats_available, cabin_class

Tool C: create_booking
  inputSchema: { flight_id: str, passenger: str }
```

**Inference**: Tool B needs `flight_id` → Tool A produces `flight_id` → A must run before B.
**Inference**: Tool C needs `flight_id` → Tool A produces it. Tool C needs availability confirmed → Tool B's purpose is validation → B runs before C.

For this to work, tools need **output schemas** — either in hints (`X-Tool-Hints`) or in tool annotations.

### Inference Approach 2: Description Keyword Analysis

Parse tool descriptions for ordering keywords:

| Keyword pattern | Inferred relationship |
|---|---|
| "after calling X" | This tool depends on X |
| "requires X" | This tool depends on X |
| "use the result from X" | Data flows from X to this |
| "before calling Y" | This tool must precede Y |
| "returns X_id" | This tool produces an ID for downstream use |
| "final step" | This is a terminal node |

### Inference Approach 3: Category + Lifecycle Analysis

Group tools by category and apply standard lifecycle patterns:

```
search tools  → validation tools → action tools → confirmation tools
  (read)           (check)          (write)          (finalize)
```

If tool hints include categories:
```json
{
  "search_flights": { "category": "search" },
  "check_availability": { "category": "validation" },
  "create_booking": { "category": "action" },
  "process_payment": { "category": "finalization" }
}
```

The orchestrator can apply the generic lifecycle pattern: search → validate → act → finalize.

### Inference Approach 4: Schema Signature Matching

Compare JSON Schema `$ref` types across tools. If Tool A's output type matches Tool B's input type, there's likely a data dependency.

```yaml
# Tool A output schema
{ "type": "array", "items": { "$ref": "#/definitions/Flight" } }

# Tool B input schema
{ "flight_id": { "type": "string", "description": "ID from Flight object" } }
```

### Building the Dependency Graph Programmatically

Combining the approaches above, the orchestrator (or a helper tool) can build a dependency graph:

```python
# Pseudocode for workflow inference
def infer_workflow(tools: list[Tool]) -> DAG:
    graph = DAG()

    for tool in tools:
        graph.add_node(tool.name)

    # From explicit hints
    for tool in tools:
        if tool.hints:
            for dep in tool.hints.get("requires", []):
                graph.add_edge(dep, tool.name)
            for next_tool in tool.hints.get("next", []):
                graph.add_edge(tool.name, next_tool)

    # From input/output matching
    output_map = {}  # field_name → producing tool
    for tool in tools:
        for field in tool.hints.get("outputs", []):
            output_map[field] = tool.name

    for tool in tools:
        for param in tool.input_schema.get("properties", {}):
            if param in output_map:
                graph.add_edge(output_map[param], tool.name)

    return graph.topological_sort()
```

### When Inference Fails

Inference works for simple, linear workflows. It breaks down for:

- **Conditional branching**: "If available, book; if not, waitlist" — requires business rules
- **Parallel execution**: "Book flight AND hotel simultaneously" — requires explicit specification
- **Error recovery**: "If payment fails, cancel booking" — requires compensation logic
- **Domain constraints**: "Maximum 3 retries" — requires configuration

For these cases, use Strategy 3 (declarative workflow definitions).

---

## Workflow Definition Formats

Domain teams can author workflow specifications in YAML, JSON, or XML.

### YAML Format (Recommended)

```yaml
domain: travel_booking
version: "1.0"

workflows:
  book_flight:
    description: "Search, check availability, and book a flight"
    params:
      origin:      { type: str, required: true }
      destination: { type: str, required: true }
      date:        { type: str, required: true, format: date }
      passenger:   { type: str, required: true }

    graph:
      search:
        call: search_flights
        args:
          origin: $origin
          destination: $destination
          date: $date
        output: flight_results

      check:
        call: check_availability
        depends_on: [search]
        args:
          flight_id: $flight_results.0.id
        output: availability

      decide:
        type: branch
        depends_on: [check]
        on:
          - when: "$availability.seats_available > 0"
            goto: reserve
          - default:
            goto: waitlist

      reserve:
        call: create_booking
        args:
          flight_id: $flight_results.0.id
          passenger: $passenger
        output: booking
        on_error:
          retry: 2
          delay: 1000
          fallback: fail_booking

      waitlist:
        call: add_to_waitlist
        args:
          flight_id: $flight_results.0.id
          passenger: $passenger

      fail_booking:
        type: error
        message: "Booking failed after retries"
```

### JSON Format

```json
{
  "domain": "travel_booking",
  "version": "1.0",
  "workflows": {
    "book_flight": {
      "description": "Search, check availability, and book a flight",
      "params": {
        "origin": { "type": "str", "required": true },
        "destination": { "type": "str", "required": true },
        "date": { "type": "str", "required": true, "format": "date" },
        "passenger": { "type": "str", "required": true }
      },
      "graph": {
        "search": {
          "call": "search_flights",
          "args": { "origin": "$origin", "destination": "$destination", "date": "$date" },
          "output": "flight_results"
        },
        "check": {
          "call": "check_availability",
          "depends_on": ["search"],
          "args": { "flight_id": "$flight_results.0.id" },
          "output": "availability"
        },
        "reserve": {
          "call": "create_booking",
          "depends_on": ["check"],
          "args": { "flight_id": "$flight_results.0.id", "passenger": "$passenger" },
          "output": "booking"
        }
      }
    }
  }
}
```

### XML Format (BPMN-inspired)

For teams that prefer XML or need BPMN tooling compatibility:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<workflows domain="travel_booking" version="1.0">

  <workflow id="book_flight" description="Search, check availability, and book a flight">
    <params>
      <param name="origin" type="str" required="true"/>
      <param name="destination" type="str" required="true"/>
      <param name="date" type="str" required="true" format="date"/>
      <param name="passenger" type="str" required="true"/>
    </params>

    <graph>
      <step id="search">
        <call tool="search_flights"/>
        <args>
          <arg name="origin" value="$origin"/>
          <arg name="destination" value="$destination"/>
          <arg name="date" value="$date"/>
        </args>
        <output name="flight_results"/>
      </step>

      <step id="check" depends_on="search">
        <call tool="check_availability"/>
        <args>
          <arg name="flight_id" value="$flight_results.0.id"/>
        </args>
        <output name="availability"/>
      </step>

      <branch id="decide" depends_on="check">
        <condition when="$availability.seats_available > 0" goto="reserve"/>
        <default goto="waitlist"/>
      </branch>

      <step id="reserve">
        <call tool="create_booking"/>
        <args>
          <arg name="flight_id" value="$flight_results.0.id"/>
          <arg name="passenger" value="$passenger"/>
        </args>
        <output name="booking"/>
        <on_error retry="2" delay="1000" fallback="fail_booking"/>
      </step>

      <step id="waitlist">
        <call tool="add_to_waitlist"/>
        <args>
          <arg name="flight_id" value="$flight_results.0.id"/>
          <arg name="passenger" value="$passenger"/>
        </args>
      </step>

      <error id="fail_booking" message="Booking failed after retries"/>
    </graph>
  </workflow>

</workflows>
```

### Node Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `call` | Execute an API tool | `call`, `args`, `output`, `on_error` |
| `branch` | Conditional routing | `on[].when`, `on[].goto`, `default` |
| `parallel` | Run branches simultaneously | `branches[]`, `on_partial_failure` |
| `foreach` | Loop over items | `items`, `as`, `step`, `max_iterations` |
| `workflow` | Execute a sub-workflow | `workflow` (ref name), `args`, `output` |
| `yield` | Pause and return intermediate results | `message`, `expects` |
| `compensate` | Rollback/cleanup on failure | `steps[]`, `ignore_error` |
| `error` | Terminal error state | `message` |

### `$reference` Syntax for Data Flow

Data flows between steps via `$references`:

| Reference | Resolves to |
|---|---|
| `$origin` | `params["origin"]` (user input) |
| `$flight_results.0.id` | `outputs["flight_results"][0]["id"]` |
| `$availability.seats` | `outputs["availability"]["seats"]` |
| `$present_options.selected_flight_id` | User-provided value from `yield` |

### Error Handling

Each `call` node supports `on_error`:

```yaml
on_error:
  retry: 3               # Retry up to 3 times
  delay: 1000            # Delay between retries (ms)
  backoff: exponential   # linear | exponential
  fallback: node_name    # Goto this node on final failure
```

Parallel nodes support `on_partial_failure`:
- `rollback_all` — Run compensation steps, abort workflow
- `continue` — Continue with successful branches only
- `abort` — Stop immediately, return partial results

---

## Implementation Plan

### Phase 1: Tool Description Enrichment (Strategy 1)

**Scope**: Parse `X-Tool-Hints` header, append metadata to tool descriptions.

| Task | File | Description |
|------|------|-------------|
| Parse `X-Tool-Hints` header | `context.py` | Add `tool_hints` field to `RequestContext` |
| Enrich tool descriptions | `middleware.py` | Append hints metadata in `on_list_tools` |
| Add `ENABLE_TOOL_HINTS` setting | `config.py` | Default: `true` |

**Outcome**: LLM sees dependency/ordering metadata in tool descriptions. Zero new modules.

### Phase 2: Workflow Resources (Strategy 2)

**Scope**: Expose workflow documentation as MCP resources.

| Task | File | Description |
|------|------|-------------|
| Workflow resource registration | `workflow/resources.py` (new) | Register workflow resources with FastMCP |
| Parse `X-Workflow-Resources` | `context.py` | Header → URL for workflow resource content |
| Register resources on startup | `__main__.py` | Hook into `create_app()` |

**Outcome**: Orchestrator can read workflow documentation via MCP resource protocol.

### Phase 3: Workflow Engine (Strategy 3 — MVP)

**Scope**: YAML/JSON workflow specs, linear + conditional execution.

| Task | File | Description |
|------|------|-------------|
| Data models | `workflow/models.py` (new) | `WorkflowDef`, `StepDef`, `WorkflowResult` |
| Spec loader | `workflow/loader.py` (new) | Fetch and parse YAML/JSON/XML from URL |
| Reference resolver | `workflow/resolver.py` (new) | `$reference` resolution engine |
| DAG executor | `workflow/engine.py` (new) | Execute `call` and `branch` node types |
| Parse `X-Workflow-URL` | `context.py` | Header parsing |
| Expose `w_*` tools | `middleware.py` | Load spec, register tools, route calls |
| Enable/disable setting | `config.py` | `ENABLE_WORKFLOWS` (default: `true`) |

**Outcome**: Linear and conditional workflows work end-to-end.

### Phase 4: Advanced Workflow Features

**Scope**: Parallelism, sub-workflows, loops, human-in-the-loop.

| Task | File | Description |
|------|------|-------------|
| `parallel` node type | `workflow/engine.py` | `asyncio.gather` for concurrent branches |
| `workflow` node type | `workflow/engine.py` | Sub-workflow invocation |
| `compensate` node type | `workflow/engine.py` | Rollback on failure |
| `foreach` node type | `workflow/engine.py` | Loop with `max_iterations` guard |
| `yield` node type | `workflow/engine.py` | Pause/resume for user input |
| `on_error` retry logic | `workflow/engine.py` | Retry with backoff |

**Outcome**: Full workflow complexity support.

### Phase 5: Observability & Validation

| Task | File | Description |
|------|------|-------------|
| OpenTelemetry spans per step | `workflow/engine.py` | Integrate with `tracing.py` |
| Workflow validation CLI | `__main__.py` | `api-agent validate-workflows file.yaml` |
| Execution history/metrics | `workflow/engine.py` | Step timing, success/failure tracking |

---

## Examples

### Example 1: Rick & Morty API with Tool Hints

A simple GraphQL API where tools have ordering hints:

```json
{
  "mcpServers": {
    "rickmorty": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://rickandmortyapi.com/graphql",
        "X-API-Type": "graphql",
        "X-Tool-Hints": {
          "rickmorty_query": {
            "category": "search",
            "hint": "Use for any question about characters, episodes, or locations.",
            "outputs": ["characters", "episodes", "locations"],
            "examples": [
              "List all characters from Earth",
              "What episodes feature Rick?"
            ]
          }
        }
      }
    }
  }
}
```

### Example 2: E-Commerce with Workflow Spec

A REST API with a complex checkout workflow:

```yaml
# ecommerce_workflows.yaml
domain: ecommerce
version: "1.0"

workflows:
  checkout:
    description: "Full checkout process: validate cart, apply discount, process payment, confirm order"
    params:
      cart_id:      { type: str, required: true }
      discount_code: { type: str, required: false }
      payment_method: { type: str, required: true }

    graph:
      validate_cart:
        call: rest_call
        args:
          method: GET
          path: /carts/$cart_id
        output: cart

      apply_discount:
        type: branch
        depends_on: [validate_cart]
        on:
          - when: "$discount_code != null"
            goto: apply_code
          - default:
            goto: calculate_total

      apply_code:
        call: rest_call
        args:
          method: POST
          path: /carts/$cart_id/discount
          body: { code: $discount_code }
        output: discounted_cart

      calculate_total:
        call: sql_query
        depends_on: [validate_cart]
        args:
          sql: "SELECT SUM(price * quantity) as total FROM cart_items"
        output: totals

      process_payment:
        call: rest_call
        depends_on: [apply_code, calculate_total]
        args:
          method: POST
          path: /payments
          body:
            cart_id: $cart_id
            amount: $totals.total
            method: $payment_method
        output: payment
        on_error:
          retry: 3
          delay: 2000
          backoff: exponential
          fallback: payment_failed

      confirm_order:
        call: rest_call
        depends_on: [process_payment]
        args:
          method: POST
          path: /orders
          body:
            cart_id: $cart_id
            payment_id: $payment.id

      payment_failed:
        type: error
        message: "Payment processing failed after 3 attempts"
```

### Example 3: Multi-API Workflow (Flight + Hotel)

```yaml
workflows:
  book_trip:
    description: "Book flight and hotel in parallel, then confirm"
    params:
      origin:      { type: str, required: true }
      destination: { type: str, required: true }
      checkin:     { type: str, required: true, format: date }
      checkout:    { type: str, required: true, format: date }
      passenger:   { type: str, required: true }

    graph:
      parallel_booking:
        type: parallel
        branches:
          flight:
            workflow: book_flight
            args:
              origin: $origin
              destination: $destination
              date: $checkin
              passenger: $passenger
            output: flight_booking

          hotel:
            call: hotels_query
            args:
              question: "Book hotel in $destination from $checkin to $checkout for $passenger"
            output: hotel_booking

        on_partial_failure: rollback_all

      confirm:
        call: confirm_trip
        depends_on: [parallel_booking]
        args:
          flight_booking_id: $flight_booking.id
          hotel_booking_id: $hotel_booking.id

      rollback_all:
        type: compensate
        steps:
          - call: cancel_booking
            args: { booking_id: $flight_booking.id }
            ignore_error: true
          - call: cancel_hotel
            args: { booking_id: $hotel_booking.id }
            ignore_error: true
```

---

## Comparison of Strategies

| Dimension | Strategy 1: Tool Hints | Strategy 2: MCP Resources | Strategy 3: Workflow Engine |
|---|---|---|---|
| **Effort to set up** | Low (header config) | Medium (write docs) | High (write YAML/JSON/XML) |
| **Enforcement** | None (advisory) | None (advisory) | Full (deterministic) |
| **Complexity supported** | Linear, simple branch | Any (but LLM must follow) | Linear, branch, parallel, loop, yield |
| **Error recovery** | None | None | Retry, fallback, compensate |
| **LLM dependency** | High (must reason) | High (must read & follow) | Low (only intent + params) |
| **New code required** | ~50 lines | ~150 lines + resources | ~800 lines (new module) |
| **Best for** | Simple APIs, quick wins | Documentation, onboarding | Critical business processes |
| **Tool prefix** | (uses existing tools) | (no new tools) | `w_*` |

### Recommendation

Use all three strategies together — they are complementary:

1. **Always** add tool hints (Strategy 1) — minimal effort, immediate benefit
2. **Add resources** (Strategy 2) for documentation and complex domain knowledge
3. **Use workflow engine** (Strategy 3) for critical, multi-step business processes where correctness is non-negotiable

### Relationship to Existing Systems

| Feature | Core Tools | Recipes (existing) | Workflows (proposed) |
|---|---|---|---|
| Origin | Built-in | Auto-learned from runs | Pre-defined by domain team |
| Complexity | Single API, multi-step | Linear (API + SQL) | DAG (branch, parallel, loop) |
| LLM involvement | Full (agent loop) | Extraction only | None in execution |
| Error recovery | Agent retries | None (fail-fast) | Retry, fallback, compensate |
| Tool prefix | `{api}_` | `r_` | `w_` |
| Data flow | Agent-managed | `{{param}}` templates | `$reference` chaining |

```
┌──────────────────────────────────────────────────────┐
│  Layer 4: Workflow Tools (pre-defined by domain team) │
│  w_book_flight, w_book_trip, w_cancel_booking         │  ← Runs DAG
│                                                        │
│  Layer 3: Planner Tool (optional, LLM-assisted)       │
│  _plan(goal) → suggested workflow + params             │  ← For novel queries
│                                                        │
│  Layer 2: Recipe Tools (auto-learned)                  │
│  r_get_top_flights, r_search_by_route                  │  ← Cached pipelines
│                                                        │
│  Layer 1: Core Tools (always present)                  │
│  flights_query, flights_execute                        │  ← NL + direct
└──────────────────────────────────────────────────────┘
```

---

## Open Questions

1. **Workflow spec hosting**: Should we support local file paths (`file://`) in addition to HTTP URLs?
2. **Caching**: Cache parsed workflow specs in-memory (like schemas), or re-fetch per session?
3. **Versioning**: How to handle workflow spec version changes mid-session?
4. **Yield/resume**: How to persist workflow state for human-in-the-loop across MCP calls?
5. **Cross-domain workflows**: Should workflows reference tools from other MCP servers?
6. **Validation**: Should we provide a workflow dry-run/simulation mode?
7. **Observability**: How granular should per-step tracing be? Span per step or span per workflow?
8. **XML support**: Full BPMN compatibility, or a simplified XML subset?
9. **Tool hint propagation**: Should hints from one API session influence tool descriptions in another?
10. **Workflow composition**: Can workflows call other workflows across different `X-Workflow-URL` sources?
