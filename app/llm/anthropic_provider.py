from collections.abc import AsyncIterator

from app.llm.base import LLMProvider, LLMRequest, LLMResponse


class AnthropicProvider(LLMProvider):
    """Stub — implement when switching from OpenAI to Anthropic via config."""

    async def complete(self, req: LLMRequest, model: str) -> LLMResponse:
        raise NotImplementedError("AnthropicProvider is not yet implemented")

    async def stream(self, req: LLMRequest, model: str) -> AsyncIterator[str]:
        raise NotImplementedError("AnthropicProvider is not yet implemented")
        yield  # make it a generator
