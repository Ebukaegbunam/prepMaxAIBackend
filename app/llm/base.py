from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel


class ContentBlock(BaseModel):
    type: Literal["text", "image_url"] = "text"
    text: str | None = None
    image_url: str | None = None


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[ContentBlock]


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float


class LLMRequest(BaseModel):
    messages: list[Message]
    response_schema: dict | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    stream: bool = False


class LLMResponse(BaseModel):
    text: str
    structured: dict | None = None
    usage: Usage
    provider: str
    model: str


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, req: LLMRequest, model: str) -> LLMResponse: ...

    @abstractmethod
    async def stream(self, req: LLMRequest, model: str) -> AsyncIterator[str]: ...


class LLMError(Exception):
    pass


class CostCapExceededError(LLMError):
    pass


class RateLimitError(LLMError):
    pass
