"""Shared OpenAI / Azure OpenAI model configuration for API agents."""

import logging

from agents import ModelSettings, RunConfig, set_default_openai_api, set_tracing_disabled
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.run import CallModelData, ModelInputData
from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.shared import Reasoning

from ..config import settings
from ..tracing import init_tracing
from ..tracing import is_enabled as tracing_enabled
from .progress import get_turn_context, increment_turn

logger = logging.getLogger(__name__)

# Set default API mode
set_default_openai_api("chat_completions")

# Initialize tracing
init_tracing()
if not tracing_enabled():
    set_tracing_disabled(True)


def _build_client() -> AsyncOpenAI:
    """Build the appropriate OpenAI client based on LLM_PROVIDER setting.

    Missing credentials are logged as warnings (not raised) so that module
    import succeeds during tests/CI.  The actual error will surface at
    request time when the client tries to call the LLM.
    """
    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "azure":
        missing = []
        if not settings.AZURE_OPENAI_API_KEY:
            missing.append("AZURE_OPENAI_API_KEY")
        if not settings.AZURE_OPENAI_ENDPOINT:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not settings.AZURE_OPENAI_DEPLOYMENT_NAME:
            missing.append("AZURE_OPENAI_DEPLOYMENT_NAME")

        if missing:
            logger.warning(
                "LLM_PROVIDER=azure but missing credentials: %s. "
                "LLM calls will fail until these are set.",
                ", ".join(missing),
            )
            # Return a placeholder client so import succeeds (tests/CI)
            return AsyncAzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY or "not-set",
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT or "https://placeholder.openai.azure.com",
                azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME or "placeholder",
                api_version=settings.AZURE_OPENAI_API_VERSION,
            )

        logger.info(
            "Using Azure OpenAI: endpoint=%s deployment=%s api_version=%s",
            settings.AZURE_OPENAI_ENDPOINT,
            settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            settings.AZURE_OPENAI_API_VERSION,
        )
        return AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )
    else:
        if not settings.OPENAI_API_KEY:
            logger.warning(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "LLM calls will fail until it is provided.",
            )
        logger.info("Using OpenAI: base_url=%s", settings.OPENAI_BASE_URL)
        return AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "not-set",
            base_url=settings.OPENAI_BASE_URL,
        )


def _get_model_name() -> str:
    """Get the model name based on provider."""
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "azure":
        # For Azure, the deployment name IS the model identifier
        return settings.AZURE_OPENAI_DEPLOYMENT_NAME or settings.MODEL_NAME
    return settings.MODEL_NAME


# Shared client and model instance
client = _build_client()
model = OpenAIChatCompletionsModel(
    model=_get_model_name(),
    openai_client=client,
)


async def _inject_turn(call_data: CallModelData) -> ModelInputData:
    """Inject turn count into instructions before each LLM call."""
    increment_turn()
    turn_info = get_turn_context(settings.MAX_AGENT_TURNS)
    existing_instructions = call_data.model_data.instructions or ""
    call_data.model_data.instructions = f"{existing_instructions}\n\n{turn_info}"
    return call_data.model_data


def get_run_config() -> RunConfig:
    """Get RunConfig with optional reasoning settings and turn injection."""
    model_settings = None
    if settings.REASONING_EFFORT:
        model_settings = ModelSettings(reasoning=Reasoning(effort=settings.REASONING_EFFORT))  # type: ignore[arg-type]

    return RunConfig(
        model_settings=model_settings,
        call_model_input_filter=_inject_turn,
    )
