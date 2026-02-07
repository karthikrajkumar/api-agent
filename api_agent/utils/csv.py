"""CSV conversion helpers."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from typing import Any

import duckdb


def to_csv(data: Any) -> str:
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

        with duckdb.connect() as conn:
            conn.execute(f"CREATE TABLE t AS SELECT * FROM read_json_auto('{temp_file}')")
            result = conn.execute("SELECT * FROM t")

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([desc[0] for desc in result.description])
            writer.writerows(result.fetchall())
            return output.getvalue()
    finally:
        if temp_file:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
