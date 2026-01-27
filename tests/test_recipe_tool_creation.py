"""Test dynamic recipe tool creation with Pydantic models."""

import pytest
from pydantic import ValidationError

from api_agent.recipe import create_params_model


def test_create_params_model_basic():
    """Test create_params_model creates dynamic model with strict config."""
    params_spec = {
        "user_id": {"type": "int", "default": 123},
        "query": {"type": "str", "default": "test"},
    }

    ParamsModel = create_params_model(params_spec, "Test")

    # Test: Model can be instantiated with valid params
    instance = ParamsModel(user_id=456, query="custom")
    assert instance.user_id == 456
    assert instance.query == "custom"

    # Test: Default values work
    instance2 = ParamsModel()
    assert instance2.user_id == 123
    assert instance2.query == "test"

    # Test: Extra fields rejected (strict mode)
    with pytest.raises(ValidationError):
        ParamsModel(user_id=456, extra_field="should_fail")

    # Test: Model has correct schema (no additionalProperties)
    schema = ParamsModel.model_json_schema()
    assert "additionalProperties" not in schema or schema.get("additionalProperties") is False


def test_create_params_model_dynamic_name():
    """Test dynamic function names work correctly."""
    params_spec = {"param1": {"type": "str", "default": "value"}}
    ParamsModel = create_params_model(params_spec, "CustomTool")

    # Create function with dynamic name
    async def dynamic_tool(params: ParamsModel) -> str:
        return f"Called with {params.param1}"

    tool_name = "my_custom_recipe_tool"
    dynamic_tool.__name__ = tool_name
    assert dynamic_tool.__name__ == tool_name


def test_create_params_model_multiple():
    """Test creating multiple dynamic models doesn't conflict."""
    # Create first model
    Model1 = create_params_model({"field_a": {"type": "str", "default": "a"}}, "Recipe1")

    # Create second model
    Model2 = create_params_model({"field_b": {"type": "int", "default": 1}}, "Recipe2")

    # Both should work independently
    inst1 = Model1(field_a="custom")
    inst2 = Model2(field_b=99)

    assert inst1.field_a == "custom"
    assert inst2.field_b == 99

    # Each should enforce its own schema
    with pytest.raises(ValidationError):
        Model1(field_b=1)  # wrong field

    with pytest.raises(ValidationError):
        Model2(field_a="a")  # wrong field


def test_create_params_model_sdk_compatibility():
    """Test generated schema is compatible with OpenAI Agents SDK (no additionalProperties)."""
    params_spec = {
        "startsWith": {"type": "str", "default": "A"},
        "limit": {"type": "int", "default": 10},
    }

    ParamsModel = create_params_model(params_spec, "list_managers_starting_with")

    schema = ParamsModel.model_json_schema()

    # Critical: OpenAI SDK rejects schemas with additionalProperties: true
    assert "additionalProperties" not in schema or schema.get("additionalProperties") is False

    # Verify schema structure
    assert schema.get("type") == "object"
    assert "properties" in schema
    assert "startsWith" in schema["properties"]
    assert "limit" in schema["properties"]

    # Verify defaults work
    instance = ParamsModel()
    assert instance.startsWith == "A"
    assert instance.limit == 10


def test_create_params_model_all_types():
    """Test create_params_model handles all supported types."""
    params_spec = {
        "str_param": {"type": "str", "default": "text"},
        "int_param": {"type": "int", "default": 42},
        "float_param": {"type": "float", "default": 3.14},
        "bool_param": {"type": "bool", "default": True},
    }

    ParamsModel = create_params_model(params_spec, "AllTypes")
    instance = ParamsModel()

    assert instance.str_param == "text"
    assert instance.int_param == 42
    assert instance.float_param == 3.14
    assert instance.bool_param is True


def test_create_params_model_unknown_type_defaults_to_str():
    """Test unknown type falls back to str."""
    params_spec = {"param": {"type": "unknown", "default": "value"}}
    ParamsModel = create_params_model(params_spec, "UnknownType")

    instance = ParamsModel()
    assert instance.param == "value"
    assert isinstance(instance.param, str)
