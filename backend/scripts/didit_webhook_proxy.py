"""Minimal local-only proxy for receiving Didit sandbox webhooks.

Expose this process through a temporary tunnel, never the main API. It accepts
only Didit's signed-webhook route and passes the small allow-list of headers to
the backend, where the signature is verified before any provider data is used.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException, Request, Response


MAX_WEBHOOK_BODY_BYTES = 512 * 1024
UPSTREAM_URL = os.getenv(
    "DIDIT_WEBHOOK_PROXY_UPSTREAM",
    "http://127.0.0.1:8000/api/v1/biometric/didit/webhook",
)
FORWARDED_HEADERS = frozenset({
    "content-type",
    "x-timestamp",
    "x-signature-v2",
    "x-signature-v2-previous",
})

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/api/v1/biometric/didit/webhook")
async def forward_didit_webhook(request: Request) -> Response:
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")

    headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() in FORWARDED_HEADERS
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.post(UPSTREAM_URL, content=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Webhook upstream is unavailable.") from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers={"Cache-Control": "no-store"},
    )
