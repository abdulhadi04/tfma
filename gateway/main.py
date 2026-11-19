
import os
import hmac
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.responses import FileResponse

# Configuration
API_KEY = os.getenv("API_KEY")
UPSTREAM_URL = os.getenv("UPSTREAM_URL", "http://localhost:8000")


# Create one HTTP client for communicating with vLLM
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=None)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="Terrifix Mesh Gateway", lifespan=lifespan)
@app.get("/")
async def frontend():
    return FileResponse("/app/frontend/index.html")

# Check whether the client supplied the correct API key
def authenticate(authorization: str | None):
    if not API_KEY:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Gateway API key is not configured",
                    "type": "server_error"
                }
            }
        )

    expected = f"Bearer {API_KEY}"

    if not authorization or not hmac.compare_digest(
        authorization, expected
    ):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "Invalid API key",
                    "type": "authentication_error",
                    "param": None,
                    "code": "invalid_api_key"
                }
            }
        )

    return None


# Gateway health endpoint
@app.get("/health")
async def health():
    return {"status": "healthy"}


# Return available models
@app.get("/v1/models")
async def list_models(authorization: str | None = Header(default=None)):
    auth_error = authenticate(authorization)

    if auth_error:
        return auth_error

    client = app.state.http_client

    try:
        response = await client.get(f"{UPSTREAM_URL}/v1/models")
        return JSONResponse(
            status_code=response.status_code,
            content=response.json()
        )
    except httpx.HTTPError:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": "Inference server unavailable"}}
        )


# Chat completions endpoint
@app.post("/v1/chat/completions")
async def chat_completions(
    payload: dict,
    authorization: str | None = Header(default=None)
):
    auth_error = authenticate(authorization)

    if auth_error:
        return auth_error

    client = app.state.http_client

    try:
        # Non-streaming request
        if not payload.get("stream", False):
            response = await client.post(
                f"{UPSTREAM_URL}/v1/chat/completions",
                json=payload
            )

            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )

        # Streaming request
        request = client.build_request(
            "POST",
            f"{UPSTREAM_URL}/v1/chat/completions",
            json=payload
        )

        upstream = await client.send(request, stream=True)
        
        if upstream.status_code >= 400:
            error_body = await upstream.aread()
            await upstream.aclose()

            return JSONResponse(
                status_code=upstream.status_code,
                content=json.loads(error_body)
            )

        async def stream_response():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()

        return StreamingResponse(
            stream_response(),
            status_code=upstream.status_code,
            media_type="text/event-stream"
        )

    except httpx.HTTPError:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": "Inference server unavailable"}}
        )
