"""Unit tests for RequestIDMiddleware."""
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def _test_app():
    """Minimal FastAPI app with only RequestIDMiddleware for isolated testing."""
    import os
    os.environ["APP_ENV"] = "test"
    os.environ["SUPABASE_JWT_SECRET"] = "test-secret-that-is-at-least-32-chars-long!"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://x:x@localhost/x"

    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from app.middleware.request_id import RequestIDMiddleware, REQUEST_ID_HEADER

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/echo")
    async def echo(request: Request) -> JSONResponse:
        return JSONResponse({
            "request_id": request.state.request_id,
        })

    return app


async def test_request_id_generated_when_absent(_test_app):
    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as client:
        response = await client.get("/echo")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    # Should be a valid UUID4
    import uuid
    uuid.UUID(request_id, version=4)


async def test_request_id_propagated_from_header(_test_app):
    custom_id = "my-custom-request-id-12345"
    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as client:
        response = await client.get("/echo", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_id
    assert response.json()["request_id"] == custom_id


async def test_request_id_in_response_header(_test_app):
    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as client:
        response = await client.get("/echo")

    assert "X-Request-ID" in response.headers
    # Request id in header matches what the route read from request.state
    assert response.headers["X-Request-ID"] == response.json()["request_id"]


async def test_each_request_gets_unique_id(_test_app):
    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as client:
        r1 = await client.get("/echo")
        r2 = await client.get("/echo")

    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]
