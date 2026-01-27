"""Unified MCP tool for natural language API queries."""

import csv
import io
import json
import os
import tempfile
from typing import Annotated, Any

import duckdb
from fastmcp import FastMCP
from pydantic import Field

from ..agent.graphql_agent import process_query
from ..agent.rest_agent import process_rest_query
from ..context import MissingHeaderError, get_request_context


def _to_csv(data: Any) -> str:
    """Convert data to CSV via DuckDB."""
    if not data:
        return ""
    if not isinstance(data, list):
        data = [data]

    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_file = f.name

        conn = duckdb.connect()
        conn.execute(f"CREATE TABLE t AS SELECT * FROM read_json_auto('{temp_file}')")
        result = conn.execute("SELECT * FROM t")

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([desc[0] for desc in result.description])
        writer.writerows(result.fetchall())
        conn.close()
        return output.getvalue()
    finally:
        if temp_file:
            try:
                os.unlink(temp_file)
            except OSError:
                pass


def _build_response(result: dict, calls_key: str, ctx) -> dict:
    """Build unified response dict from agent result."""
    response = {
        "ok": result.get("ok", False),
        "data": result.get("data"),
        calls_key: result.get(calls_key, []),
        "error": result.get("error"),
    }
    if ctx.include_result or result.get("result") is not None:
        response["result"] = result.get("result")
    return response


def register_query_tool(mcp: FastMCP) -> None:
    """Register the unified query tool."""

    @mcp.tool(
        name="_query",
        description="""Ask questions about the API in natural language.

The agent reads the schema, builds queries, executes them, and can do multi-step data processing.

Returns answer and the queries/calls made (reusable with execute tool).""",
        tags={"query", "nl"},
    )
    async def query(
        question: Annotated[str, Field(description="Natural language question about the API")],
    ) -> dict | str:
        """Process natural language query against configured API."""
        try:
            ctx = get_request_context()
        except MissingHeaderError as e:
            return {"ok": False, "error": str(e)}

        if ctx.api_type == "graphql":
            result = await process_query(question, ctx)
        else:
            result = await process_rest_query(question, ctx)

        # Direct return: just CSV, no wrapper
        if result.get("result") is not None and result.get("data") is None:
            return _to_csv(result["result"])

        calls_key = "queries" if ctx.api_type == "graphql" else "api_calls"
        return _build_response(result, calls_key, ctx)
