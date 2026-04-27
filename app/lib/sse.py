"""Server-Sent Events helpers."""
import json
from typing import AsyncIterator

from fastapi.responses import StreamingResponse


def _format_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def progress_event(stage: str) -> str:
    return _format_event("progress", {"stage": stage})


def delta_event(text: str) -> str:
    return _format_event("delta", {"text": text})


def final_event(payload: dict) -> str:
    return _format_event("final", payload)


def error_event(code: str, message: str) -> str:
    return _format_event("error", {"error": {"code": code, "message": message}})


def sse_response(generator: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
