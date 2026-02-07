"""Tests for query response building."""

from unittest.mock import MagicMock

import pytest

from api_agent.tools.query import _build_response
from api_agent.utils.csv import to_csv


@pytest.fixture
def ctx_without_include_result():
    """Context with include_result=False."""
    ctx = MagicMock()
    ctx.include_result = False
    return ctx


@pytest.fixture
def ctx_with_include_result():
    """Context with include_result=True."""
    ctx = MagicMock()
    ctx.include_result = True
    return ctx


class TestBuildResponse:
    """Tests for _build_response function."""

    def test_direct_return_response_rest(self, ctx_without_include_result):
        """Direct return response includes result and api_calls only."""
        result = {
            "ok": True,
            "result": {"users": [{"id": 1}]},
            "api_calls": [{"method": "GET", "path": "/users"}],
        }
        response = _build_response(result, "api_calls", ctx_without_include_result)

        assert response["ok"] is True
        assert response["result"] == {"users": [{"id": 1}]}
        assert response["api_calls"] == [{"method": "GET", "path": "/users"}]
        # Should not have cruft fields
        assert "direct_return" not in response

    def test_direct_return_response_graphql(self, ctx_without_include_result):
        """Direct return response includes result and queries only."""
        result = {
            "ok": True,
            "result": {"data": {"users": []}},
            "queries": ["query { users { id } }"],
        }
        response = _build_response(result, "queries", ctx_without_include_result)

        assert response["ok"] is True
        assert response["result"] == {"data": {"users": []}}
        assert response["queries"] == ["query { users { id } }"]
        assert "direct_return" not in response

    def test_result_included_when_present(self, ctx_without_include_result):
        """Result is included when present, even without include_result flag."""
        result = {
            "ok": True,
            "result": {"data": "value"},
            "api_calls": [],
        }
        response = _build_response(result, "api_calls", ctx_without_include_result)

        assert "result" in response
        assert response["result"] == {"data": "value"}

    def test_result_included_when_include_result_true(self, ctx_with_include_result):
        """Result included when include_result=True."""
        result = {
            "ok": True,
            "result": None,
            "api_calls": [],
        }
        response = _build_response(result, "api_calls", ctx_with_include_result)

        assert "result" in response

    def test_result_excluded_when_none_and_not_requested(self, ctx_without_include_result):
        """Result excluded when None and include_result=False."""
        result = {
            "ok": True,
            "api_calls": [],
        }
        response = _build_response(result, "api_calls", ctx_without_include_result)

        assert "result" not in response

    def test_empty_api_calls(self, ctx_without_include_result):
        """Empty api_calls list is preserved."""
        result = {"ok": True, "api_calls": []}
        response = _build_response(result, "api_calls", ctx_without_include_result)

        assert response["api_calls"] == []

    def test_empty_queries(self, ctx_without_include_result):
        """Empty queries list is preserved."""
        result = {"ok": True, "queries": []}
        response = _build_response(result, "queries", ctx_without_include_result)

        assert response["queries"] == []


class TestToCsv:
    """Tests for to_csv function."""

    def test_list_to_csv(self):
        """List converts to CSV with header."""
        data = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        result = to_csv(data)

        lines = result.strip().splitlines()
        assert len(lines) == 3
        assert lines[0] == "id,name"
        assert lines[1] == "1,a"
        assert lines[2] == "2,b"

    def test_single_object_to_csv(self):
        """Single object converts to single row CSV."""
        data = {"id": 1, "name": "test"}
        result = to_csv(data)

        lines = result.strip().splitlines()
        assert len(lines) == 2
        assert lines[0] == "id,name"
        assert lines[1] == "1,test"

    def test_empty_list_to_csv(self):
        """Empty list returns empty string."""
        assert to_csv([]) == ""

    def test_empty_none_to_csv(self):
        """None returns empty string."""
        assert to_csv(None) == ""

    def test_nested_objects_to_csv(self):
        """Nested objects get flattened by DuckDB."""
        data = [{"user": {"id": 1, "name": "a"}}, {"user": {"id": 2, "name": "b"}}]
        result = to_csv(data)

        lines = result.strip().splitlines()
        assert len(lines) == 3
        # DuckDB creates struct column
        assert "user" in lines[0]
