"""Unit tests for individual recipe tool generation."""

from unittest.mock import MagicMock

from api_agent.recipe import (
    _sanitize_for_tool_name,
    build_api_id,
    build_partial_result,
    build_recipe_docstring,
    deduplicate_tool_name,
    validate_recipe_params,
)


def test_sanitize_for_tool_name_basic():
    """Test basic question sanitization."""
    assert _sanitize_for_tool_name("Get user posts") == "get_user_posts"
    assert _sanitize_for_tool_name("Fetch data from API") == "fetch_data_from_api"


def test_sanitize_for_tool_name_special_chars():
    """Test sanitization removes special characters."""
    assert _sanitize_for_tool_name("Get user's recent posts") == "get_users_recent_posts"
    assert _sanitize_for_tool_name("Fetch data (v2)") == "fetch_data_v2"
    assert _sanitize_for_tool_name("Query: users + posts") == "query_users_posts"
    assert _sanitize_for_tool_name("Get user's 'data'!") == "get_users_data"


def test_sanitize_for_tool_name_length_limit():
    """Test tool name is capped at 40 chars."""
    long_question = "Get all the user data from the API endpoint with filtering"
    result = _sanitize_for_tool_name(long_question)
    assert len(result) <= 40
    assert result == "get_all_the_user_data_from_the_api_endpo"


def test_sanitize_for_tool_name_trailing_underscores():
    """Test trailing underscores are stripped."""
    assert _sanitize_for_tool_name("Get data!!") == "get_data"
    assert _sanitize_for_tool_name("Query???") == "query"


def test_sanitize_for_tool_name_multiple_spaces():
    """Test multiple spaces are collapsed."""
    assert _sanitize_for_tool_name("Get    user     data") == "get_user_data"


def test_sanitize_for_tool_name_digit_prefix():
    """Test names starting with digit get r_ prefix."""
    assert _sanitize_for_tool_name("123 hotels") == "r_123_hotels"
    assert _sanitize_for_tool_name("5 star rating") == "r_5_star_rating"
    assert _sanitize_for_tool_name("1st place") == "r_1st_place"


def test_validate_recipe_params_success():
    """Test successful param validation."""
    params_spec = {
        "user_id": {"type": "int", "default": 123},
        "limit": {"type": "int", "default": 10},
    }
    provided = {"user_id": 456, "limit": 10}
    params, error = validate_recipe_params(params_spec, provided)
    assert error == ""
    assert params == {"user_id": 456, "limit": 10}


def test_validate_recipe_params_missing_required():
    """Test validation fails on missing required param."""
    params_spec = {
        "user_id": {"type": "int"},  # No default = required
        "limit": {"type": "int", "default": 10},
    }
    provided = {}
    params, error = validate_recipe_params(params_spec, provided)
    assert params is None
    assert "missing required param: user_id" in error


def test_validate_recipe_params_with_defaults():
    """Test params merge with defaults."""
    params_spec = {
        "user_id": {"type": "int", "default": 123},
        "query": {"type": "str", "default": "test"},
    }
    provided = {"user_id": 123, "query": "custom"}
    params, error = validate_recipe_params(params_spec, provided)
    assert error == ""
    assert params == {"user_id": 123, "query": "custom"}


def test_validate_recipe_params_empty_spec():
    """Test validation with no params."""
    params_spec = {}
    provided = {}
    params, error = validate_recipe_params(params_spec, provided)
    assert error == ""
    assert params == {}


def test_validate_recipe_params_extra_provided():
    """Test validation rejects extra params."""
    params_spec = {
        "user_id": {"type": "int", "default": 123},
    }
    provided = {"user_id": 456, "extra": "ignored"}
    params, error = validate_recipe_params(params_spec, provided)
    assert params is None
    assert "unexpected params: extra" in error


# build_recipe_docstring tests


def test_build_recipe_docstring_rest_single_step():
    """Test docstring for single REST API call."""
    docstring = build_recipe_docstring(
        "Get user data", steps=[{"kind": "rest"}], sql_steps=[], api_type="rest"
    )
    assert "Get user data" in docstring
    assert "1 API call" in docstring


def test_build_recipe_docstring_graphql_multiple():
    """Test docstring for multiple GraphQL queries."""
    docstring = build_recipe_docstring(
        "Get users and posts",
        steps=[{"kind": "graphql"}, {"kind": "graphql"}],
        sql_steps=[],
        api_type="graphql",
    )
    assert "Get users and posts" in docstring
    assert "2 GraphQL queries" in docstring


def test_build_recipe_docstring_sql_only():
    """Test docstring for SQL-only recipe."""
    docstring = build_recipe_docstring(
        "Run SQL query", steps=[], sql_steps=["SELECT * FROM data"], api_type="rest"
    )
    assert "Run SQL query" in docstring
    assert "1 SQL step" in docstring


def test_build_recipe_docstring_mixed_steps():
    """Test docstring for mixed API + SQL steps."""
    docstring = build_recipe_docstring(
        "Complex workflow",
        steps=[{"kind": "rest"}, {"kind": "rest"}],
        sql_steps=["SELECT 1", "SELECT 2", "SELECT 3"],
        api_type="rest",
    )
    assert "Complex workflow" in docstring
    assert "2 API calls" in docstring
    assert "3 SQL steps" in docstring


# deduplicate_tool_name tests


def test_deduplicate_tool_name_unique():
    """Test unique name passes through unchanged."""
    seen = set()
    name = deduplicate_tool_name("get_users", seen)
    assert name == "get_users"
    assert "get_users" in seen


def test_deduplicate_tool_name_duplicate():
    """Test duplicate gets _2 suffix."""
    seen = {"get_users"}
    name = deduplicate_tool_name("get_users", seen)
    assert name == "get_users_2"
    assert "get_users_2" in seen


def test_deduplicate_tool_name_multiple_duplicates():
    """Test multiple duplicates get incremented suffixes."""
    seen = {"get_users", "get_users_2", "get_users_3"}
    name = deduplicate_tool_name("get_users", seen)
    assert name == "get_users_4"
    assert "get_users_4" in seen


# build_api_id tests


def test_build_api_id_graphql():
    """Test GraphQL api_id format."""
    ctx = MagicMock()
    ctx.target_url = "https://api.example.com/graphql"
    api_id = build_api_id(ctx, "graphql")
    assert api_id == "graphql:https://api.example.com/graphql"


def test_build_api_id_rest():
    """Test REST api_id format includes base_url."""
    ctx = MagicMock()
    ctx.target_url = "https://api.example.com"
    api_id = build_api_id(ctx, "rest", base_url="/v1")
    assert api_id == "rest:https://api.example.com|/v1"


# build_partial_result tests


def test_build_partial_result_with_data():
    """Test partial result when data was retrieved."""
    result = build_partial_result(
        last_data={"users": [1, 2, 3]},
        api_calls=[{"method": "GET"}],
        turn_info="2/5 turns",
        call_key="api_calls",
    )
    assert result["ok"] is True
    assert "Partial" in result["data"]
    assert result["result"] == {"users": [1, 2, 3]}
    assert result["api_calls"] == [{"method": "GET"}]
    assert result["error"] is None


def test_build_partial_result_no_data():
    """Test partial result when no data retrieved."""
    result = build_partial_result(
        last_data=None, api_calls=[], turn_info="3/5 turns", call_key="graphql_queries"
    )
    assert result["ok"] is False
    assert result["data"] is None
    assert result["result"] is None
    assert result["graphql_queries"] == []
    assert "Max turns exceeded" in result["error"]
