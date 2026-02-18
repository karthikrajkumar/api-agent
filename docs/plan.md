# Workflow Orchestration for MCP — Design Plan

> **Goal**: Enable domain teams to define multi-step, complex workflows across their APIs so that an MCP orchestrator (LLM) can discover and execute them correctly — without guessing the sequence.

---

## Problem Statement

Today, when a domain exposes 10 APIs as 10 MCP tools, the orchestrator sees them as **10 independent, flat tools** with no relationship information. It relies entirely on the LLM's reasoning to figure out ordering — which fails for domain-specific workflows.

| What the LLM sees today     | What it actually needs         |
| ---------------------------- | ------------------------------ |
| 10 independent tools         | Tool dependency graph          |
| Flat descriptions            | Pre/post conditions            |
| No sequencing hints          | Workflow templates             |
| No domain context            | Business rules & error recovery|

### Example

A travel booking domain has these APIs:

1. `search_flights` — Search available flights
2. `check_availability` — Check seat availability
3. `create_booking` — Reserve a flight
4. `process_payment` — Charge the customer
5. `search_hotels` — Search hotels
6. `book_hotel` — Reserve a hotel
7. `confirm_trip` — Confirm full trip
8. `cancel_booking` — Cancel a flight booking
9. `cancel_hotel` — Cancel a hotel booking
10. `add_to_waitlist` — Join a waitlist

The correct booking workflow is: `search_flights` → `check_availability` → (if available) `create_booking` → `process_payment`. But the LLM has no way to know this without domain knowledge.

---

## Complexity Spectrum

Real domain workflows aren't just linear. They span multiple levels of complexity:

```
Level 1: Linear          A → B → C
Level 2: Conditional     A → if X then B else C → D
Level 3: Parallel        (A ∥ B) → merge → C
Level 4: Sub-workflows   A → [Book Flight workflow] → C
Level 5: Fan-out/in      A → [B₁, B₂, B₃] → merge → C
Level 6: Loops/Retry     A → B → if fail: retry B (max 3) → C
Level 7: Cross-workflow   Workflow₁.output feeds Workflow₂.input
```

A single domain might use **all of these** across 10+ workflows.

---

## Design Overview

### Core Principle

**Put deterministic logic in the workflow engine, put reasoning in the LLM.**

- The LLM figures out **WHAT** to do (intent matching, param extraction, disambiguation).
- The workflow engine figures out **HOW** to do it (sequencing, branching, parallelism, retries, rollback).

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Orchestrator                          │
│                                                              │
│  "User wants to book a trip to Paris next week"              │
│                                                              │
│  Decision: This matches w_book_trip                          │
│  → Call w_book_trip(origin="NYC", dest="Paris",              │
│     checkin="2026-02-23", checkout="2026-02-28",             │
│     passenger="John")                                        │
│                                                              │
│  LLM handles: intent matching, param extraction,             │
│               date calculation, disambiguation                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                 Workflow Engine (new)                         │
│                                                              │
│  Deterministically executes the DAG:                         │
│  1. book_flight ∥ book_hotel (parallel)                      │
│  2. If flight fails → retry 2x → rollback hotel             │
│  3. If both succeed → confirm_trip                           │
│  4. Return final result                                      │
│                                                              │
│  Engine handles: sequencing, branching, parallelism,         │
│                  retries, rollback, error recovery            │
└─────────────────────────────────────────────────────────────┘
```

### Tool Layers (what the orchestrator sees)

```
┌──────────────────────────────────────────────────────┐
│  Layer 4: Workflow Tools (pre-defined by domain team) │
│  ┌──────────────────────────────────────────────────┐ │
│  │ w_book_flight(origin, dest, date, passenger)     │ │  ← Runs entire DAG
│  │ w_book_trip(origin, dest, checkin, checkout, ...) │ │    No LLM in the loop
│  │ w_cancel_booking(booking_id)                     │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Layer 3: Planner Tool (optional)                      │
│  ┌──────────────────────────────────────────────────┐ │
│  │ _plan(goal) → suggested workflow + params         │ │  ← For novel queries
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Layer 2: Recipe Tools (auto-learned)                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │ r_get_top_flights(limit)                         │ │  ← Cached from past runs
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Layer 1: Core Tools (always present)                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │ flights_query(question)                          │ │  ← NL → Agent
│  │ flights_execute(query, variables)                │ │  ← Direct execution
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## Approach: Three Complementary Strategies

### Strategy 1: Tool Description Enrichment (lightweight)

Inject sequencing hints into tool descriptions via a new `X-Tool-Hints` header. The existing middleware already transforms descriptions — we just add workflow context.

**Header format:**

```json
{
  "X-Tool-Hints": {
    "search_flights": {
      "next": ["check_availability"],
      "hint": "Always call check_availability after this with the flight_id from results"
    },
    "check_availability": {
      "requires": ["search_flights"],
      "next": ["create_booking"],
      "hint": "Requires flight_id from search_flights results"
    },
    "create_booking": {
      "requires": ["check_availability"],
      "hint": "Only call after check_availability confirms seats"
    }
  }
}
```

**What the LLM sees:**

> **check_availability** — Check seat availability for a flight.
> ⚠️ Requires: `search_flights` (needs flight_id from results)
> ➡️ Next: `create_booking`

**Pros**: Zero new tools, works with any LLM, simple to implement.
**Cons**: LLMs can still ignore hints, no enforcement, linear only.

---

### Strategy 2: Workflow Resources (MCP Resources)

Expose workflow definitions as readable MCP resources. The orchestrator reads them upfront before planning.

**Resource URI:** `workflow://travel_booking/graph`

**Content:**

```
When working with the Flights API:
1. Always search first (search_flights)
2. Check availability before booking (check_availability)
3. Only then create booking (create_booking)

Common workflows:
- Booking: search_flights → check_availability → create_booking
- Cancellation: get_booking → cancel_booking → confirm_cancellation
```

**Pros**: Clean separation of concerns, declarative.
**Cons**: Requires LLM to read and follow the resource, no execution guarantee.

---

### Strategy 3: Pre-defined Workflows with DAG Engine (full solution)

Domain teams author workflow specifications (YAML/JSON), loaded via `X-Workflow-URL` header. Each workflow is exposed as a composite MCP tool (`w_*`) with a DAG engine handling execution.

This is the primary proposed implementation. Details below.

---

## Workflow Specification Format

### MCP Client Configuration

```json
{
  "mcpServers": {
    "flights": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "X-Target-URL": "https://flights-api.example.com/graphql",
        "X-API-Type": "graphql",
        "X-Workflow-URL": "https://team.example.com/workflows.yaml"
      }
    }
  }
}
```

### Full Specification Example

```yaml
# workflows.yaml — Domain workflow specification
domain: travel_booking
version: "1.0"

workflows:

  # ─── Linear workflow ────────────────────────────────
  check_flight_status:
    description: "Check real-time status of a flight"
    params:
      flight_number: { type: str, required: true, example: "AA123" }
    graph:
      lookup:
        call: flights_query
        args: { question: "Get status for flight $flight_number" }

  # ─── Conditional branching ──────────────────────────
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
          - when: "$availability.seats_available == 0"
            goto: waitlist
          - default:
            goto: fail_no_seats

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
        output: waitlist_entry

      fail_no_seats:
        type: error
        message: "No seats available on any searched flight"

      fail_booking:
        type: error
        message: "Booking failed after retries"

  # ─── Parallel execution + merge ─────────────────────
  book_trip:
    description: "Book flight and hotel in parallel, then confirm"
    params:
      origin:      { type: str, required: true }
      destination: { type: str, required: true }
      checkin:     { type: str, required: true, format: date }
      checkout:    { type: str, required: true, format: date }
      passenger:   { type: str, required: true }
    graph:
      flight_and_hotel:
        type: parallel
        branches:
          book_flight_branch:
            workflow: book_flight
            args:
              origin: $origin
              destination: $destination
              date: $checkin
              passenger: $passenger
            output: flight_booking

          book_hotel_branch:
            workflow: book_hotel
            args:
              city: $destination
              checkin: $checkin
              checkout: $checkout
              guest: $passenger
            output: hotel_booking

        on_partial_failure: rollback_all

      confirm:
        call: confirm_trip
        depends_on: [flight_and_hotel]
        args:
          flight_booking_id: $flight_booking.id
          hotel_booking_id: $hotel_booking.id
        output: trip_confirmation

      rollback_all:
        type: compensate
        steps:
          - call: cancel_booking
            args: { booking_id: $flight_booking.id }
            ignore_error: true
          - call: cancel_hotel
            args: { booking_id: $hotel_booking.id }
            ignore_error: true

  # ─── Loop / fan-out ─────────────────────────────────
  find_cheapest_across_dates:
    description: "Search multiple dates and find cheapest option"
    params:
      origin:      { type: str, required: true }
      destination: { type: str, required: true }
      start_date:  { type: str, required: true, format: date }
      num_days:    { type: int, required: true, default: 7 }
    graph:
      search_loop:
        type: foreach
        items: "range($start_date, $start_date + $num_days days)"
        as: current_date
        step:
          call: search_flights
          args:
            origin: $origin
            destination: $destination
            date: $current_date
        output: all_results
        max_iterations: 30

      find_cheapest:
        depends_on: [search_loop]
        call: sql_query
        args:
          sql: >
            SELECT * FROM all_results
            ORDER BY price ASC
            LIMIT 5

  # ─── Human-in-the-loop ──────────────────────────────
  book_with_approval:
    description: "Search and book, but pause for user approval before payment"
    params:
      origin: { type: str, required: true }
      destination: { type: str, required: true }
      date: { type: str, required: true }
    graph:
      search:
        call: search_flights
        args: { origin: $origin, destination: $destination, date: $date }
        output: options

      present_options:
        type: yield
        depends_on: [search]
        message: "Found $options.length flights. Which one would you like to book?"
        expects: { selected_flight_id: str }

      book:
        depends_on: [present_options]
        call: create_booking
        args:
          flight_id: $present_options.selected_flight_id
```

### Node Types

| Type          | Description                                          | Key Fields                                      |
| ------------- | ---------------------------------------------------- | ----------------------------------------------- |
| `call`        | Execute an API tool                                  | `call`, `args`, `output`, `on_error`            |
| `branch`      | Conditional routing                                  | `on[].when`, `on[].goto`, `default`             |
| `parallel`    | Run branches simultaneously                          | `branches[]`, `on_partial_failure`              |
| `foreach`     | Loop over items                                      | `items`, `as`, `step`, `max_iterations`         |
| `workflow`    | Execute a sub-workflow                               | `workflow` (ref name), `args`, `output`         |
| `yield`       | Pause and return intermediate results to user        | `message`, `expects`                            |
| `compensate`  | Rollback/cleanup on failure                          | `steps[]`, `ignore_error`                       |
| `error`       | Terminal error state                                 | `message`                                       |

### `$reference` Syntax

Data flows between steps via `$references`:

| Reference                    | Resolves to                                  |
| ---------------------------- | -------------------------------------------- |
| `$origin`                    | `params["origin"]` (user input)              |
| `$flight_results.0.id`      | `outputs["flight_results"][0]["id"]`         |
| `$availability.seats`       | `outputs["availability"]["seats"]`           |
| `$present_options.selected_flight_id` | User-provided value from `yield`  |

### Error Handling

Each `call` node supports `on_error`:

```yaml
on_error:
  retry: 3              # Retry up to 3 times
  delay: 1000           # Delay between retries (ms)
  backoff: exponential   # Optional: linear | exponential
  fallback: node_name   # Goto this node on final failure
```

Parallel nodes support `on_partial_failure`:

- `rollback_all` — Run compensation steps, abort workflow
- `continue` — Continue with successful branches only
- `abort` — Stop immediately, return partial results

---

## Implementation Plan

### New Files

```
api_agent/
├── workflow/                     ← NEW module
│   ├── __init__.py
│   ├── models.py                 ← WorkflowDef, WorkflowStep, WorkflowResult dataclasses
│   ├── loader.py                 ← Fetch and parse YAML/JSON workflow specs from URL
│   ├── resolver.py               ← $reference resolution engine
│   └── engine.py                 ← DAG executor (branch, parallel, loop, yield, compensate)
└── tools/
    └── plan.py                   ← Optional _plan tool for novel compositions
```

### Modified Files

| File                | Change                                                                       |
| ------------------- | ---------------------------------------------------------------------------- |
| `context.py`        | Add `X-Workflow-URL` header parsing, `workflows` field on `RequestContext`   |
| `middleware.py`     | Load workflow spec, expose `w_*` tools in `on_list_tools`, handle in `on_call_tool` |
| `config.py`         | Add `ENABLE_WORKFLOWS` setting (default: `true`)                             |
| `tools/__init__.py` | Register optional `_plan` tool                                               |

### Implementation Phases

#### Phase 1: Core Engine (MVP)

- [ ] `workflow/models.py` — Data models for workflow definitions
- [ ] `workflow/loader.py` — Fetch and parse workflow specs from `X-Workflow-URL`
- [ ] `workflow/resolver.py` — `$reference` resolution
- [ ] `workflow/engine.py` — DAG executor with `call` and `branch` node types
- [ ] `context.py` — Parse `X-Workflow-URL` header
- [ ] `middleware.py` — Expose `w_*` tools, route `w_*` calls to engine
- [ ] `config.py` — `ENABLE_WORKFLOWS` setting

**Outcome**: Linear and conditional workflows work end-to-end.

#### Phase 2: Parallelism & Sub-workflows

- [ ] `workflow/engine.py` — Add `parallel` node type with `asyncio.gather`
- [ ] `workflow/engine.py` — Add `workflow` (sub-workflow) node type
- [ ] `workflow/engine.py` — Add `compensate` node type for rollbacks
- [ ] `workflow/engine.py` — Add `on_error` retry logic with backoff

**Outcome**: Complex multi-branch workflows with error recovery.

#### Phase 3: Loops, Yield & Planner

- [ ] `workflow/engine.py` — Add `foreach` node type
- [ ] `workflow/engine.py` — Add `yield` node type (pause/resume)
- [ ] `tools/plan.py` — `_plan` tool that suggests workflows for novel goals
- [ ] Workflow graph exposed as MCP resource (`workflow://{domain}/graph`)

**Outcome**: Full workflow complexity support, LLM-assisted planning.

#### Phase 4: Enrichment & Observability

- [ ] `X-Tool-Hints` header support for lightweight tool description enrichment
- [ ] OpenTelemetry spans per workflow step (integrate with existing `tracing.py`)
- [ ] Workflow execution history / metrics
- [ ] Validation CLI: `api-agent validate-workflows workflows.yaml`

---

## How the LLM Orchestrator Sees Workflow Tools

Tool descriptions encode the full structure so the LLM can make informed decisions:

```
Tool: w_book_trip

[flights.example.com GraphQL API] Book flight and hotel in parallel, then confirm.

┌─ Workflow: book_trip ───────────────────────────────┐
│                                                      │
│  ┌──────────┐    ┌──────────────┐                   │
│  │  book     │    │  book        │   ← parallel     │
│  │  flight   │    │  hotel       │                   │
│  └────┬─────┘    └──────┬───────┘                   │
│       │                  │                           │
│       └────────┬─────────┘                           │
│                ▼                                     │
│         ┌────────────┐                               │
│         │  confirm   │                               │
│         │  trip      │                               │
│         └────────────┘                               │
│                                                      │
│  On failure: rollback all bookings                   │
│                                                      │
│  Params: origin (str), destination (str),            │
│          checkin (date), checkout (date),             │
│          passenger (str)                             │
└──────────────────────────────────────────────────────┘
```

---

## Relationship to Existing Systems

| Feature             | Recipes (existing)                | Workflows (proposed)                |
| ------------------- | --------------------------------- | ----------------------------------- |
| Origin              | Auto-learned from successful runs | Pre-defined by domain team          |
| Complexity          | Linear (API calls + SQL)          | DAG (branch, parallel, loop, yield) |
| LLM involvement     | Extraction only                   | None in execution                   |
| Error recovery      | None (fail-fast)                  | Retry, fallback, compensate         |
| Data flow           | `{{param}}` templates             | `$reference` chaining               |
| Tool prefix         | `r_*`                             | `w_*`                               |
| Schema invalidation | Auto (schema hash)                | Manual (spec versioning)            |
| Storage             | In-memory LRU                     | Loaded from URL per session         |

Workflows and recipes are **complementary**:

- **Workflows** encode expert domain knowledge upfront.
- **Recipes** discover patterns from usage over time.
- **Core tools** handle novel, one-off questions.

The orchestrator picks the right layer based on the question.

---

## Open Questions

1. **Workflow spec hosting**: Should we support local file paths in addition to URLs?
2. **Caching**: Cache parsed workflow specs in-memory (like schemas), or re-fetch per session?
3. **Versioning**: How to handle workflow spec version changes mid-session?
4. **Yield/resume**: How to persist workflow state for human-in-the-loop across MCP calls?
5. **Cross-domain**: Should workflows reference tools from other MCP servers?
6. **Testing**: Should we provide a workflow dry-run/simulation mode?
