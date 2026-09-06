"""Релей к Anthropic API. Деплоится на Render (или любой зарубежный PaaS).

Бот шлет запросы сюда вместо api.anthropic.com, релей пересылает их дальше.
Ключ Anthropic сюда не сохраняется - проходит транзитом в заголовке x-api-key.
RELAY_SECRET защищает релей от чужого использования.
"""
import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

UPSTREAM = "https://api.anthropic.com"
RELAY_SECRET = os.environ["RELAY_SECRET"]

app = FastAPI()
client = httpx.AsyncClient(base_url=UPSTREAM, timeout=httpx.Timeout(300, connect=10))

HOP_HEADERS = {"host", "content-length", "connection", "x-relay-secret", "accept-encoding"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def relay(path: str, request: Request):
    if request.headers.get("x-relay-secret") != RELAY_SECRET:
        return Response(status_code=401, content="unauthorized")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    req = client.build_request(
        request.method,
        f"/v1/{path}",
        content=await request.body(),
        headers=headers,
        params=request.query_params,
    )
    # stream=True: SSE-чанки уходят клиенту сразу, без буферизации всего ответа
    upstream_resp = await client.send(req, stream=True)
    resp_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in ("content-encoding", "transfer-encoding", "content-length", "connection")
    }

    async def body():
        try:
            async for chunk in upstream_resp.aiter_raw():
                yield chunk
        finally:
            await upstream_resp.aclose()

    return StreamingResponse(
        body(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )
