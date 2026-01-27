"""Recipe module for parameterized API-call + SQL pipeline caching."""

from .common import (
    _return_directly_flag,
    _sanitize_for_tool_name,
    _set_return_directly,
    _tools_to_final_output,
    build_api_id,
    build_partial_result,
    build_recipe_context,
    build_recipe_docstring,
    create_params_model,
    deduplicate_tool_name,
    execute_recipe_steps,
    format_recipe_response,
    maybe_extract_and_save_recipe,
    search_recipes,
    validate_and_prepare_recipe,
    validate_recipe_params,
)
from .extractor import extract_recipe
from .store import (
    RECIPE_STORE,
    RecipeRecord,
    RecipeStore,
    params_with_defaults,
    render_param_refs,
    render_text_template,
    sha256_hex,
)

__all__ = [
    # Store
    "RECIPE_STORE",
    "_return_directly_flag",
    "_sanitize_for_tool_name",
    "_set_return_directly",
    "_tools_to_final_output",
    "RecipeStore",
    "RecipeRecord",
    "sha256_hex",
    "render_text_template",
    "render_param_refs",
    "params_with_defaults",
    # Extractor
    "extract_recipe",
    # Common
    "build_recipe_docstring",
    "create_params_model",
    "deduplicate_tool_name",
    "execute_recipe_steps",
    "format_recipe_response",
    "maybe_extract_and_save_recipe",
    "build_partial_result",
    "build_api_id",
    "build_recipe_context",
    "search_recipes",
    "validate_and_prepare_recipe",
    "validate_recipe_params",
]
