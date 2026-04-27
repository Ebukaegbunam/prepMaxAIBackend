import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.llm.base import ContentBlock, LLMError, LLMRequest, LLMResponse, LLMProvider, Message, Usage

# USD per 1K tokens
_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.000150, "output": 0.000600},
    "gpt-4-turbo": {"input": 0.010, "output": 0.030},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = _PRICES.get(model, {"input": 0.010, "output": 0.030})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1000


def _to_openai_messages(messages: list[Message]) -> list[dict]:
    result = []
    for msg in messages:
        if isinstance(msg.content, str):
            result.append({"role": msg.role, "content": msg.content})
        else:
            parts = []
            for block in msg.content:
                if block.type == "text" and block.text:
                    parts.append({"type": "text", "text": block.text})
                elif block.type == "image_url" and block.image_url:
                    parts.append({"type": "image_url", "image_url": {"url": block.image_url}})
            result.append({"role": msg.role, "content": parts})
    return result


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(self, req: LLMRequest, model: str) -> LLMResponse:
        kwargs: dict = {
            "model": model,
            "messages": _to_openai_messages(req.messages),
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }

        if req.response_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": req.response_schema,
                    "strict": True,
                },
            }

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"OpenAI API error: {exc}") from exc

        choice = response.choices[0]
        text = choice.message.content or ""
        usage_data = response.usage

        input_tokens = usage_data.prompt_tokens if usage_data else 0
        output_tokens = usage_data.completion_tokens if usage_data else 0
        cost = _estimate_cost(model, input_tokens, output_tokens)

        structured: dict | None = None
        if req.response_schema:
            try:
                structured = json.loads(text)
            except json.JSONDecodeError:
                structured = None

        return LLMResponse(
            text=text,
            structured=structured,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost),
            provider="openai",
            model=model,
        )

    async def stream(self, req: LLMRequest, model: str) -> AsyncIterator[str]:
        kwargs: dict = {
            "model": model,
            "messages": _to_openai_messages(req.messages),
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": True,
        }
        try:
            async for chunk in await self._client.chat.completions.create(**kwargs):
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError(f"OpenAI streaming error: {exc}") from exc
