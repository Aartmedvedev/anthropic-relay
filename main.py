import os

import httpx
from fastapi import FastAPI, Request, Response

UPSTREAM = "https://api.anthropic.com"
RELAY_SECRET = os.environ["RELAY_SECRET"]

app = FastAPI()
client = httpx.AsyncClient(base_url=UPSTREAM, timeout=180)

HOP_HEADERS = {"host", "content-length", "connection", "x-relay-secret", "accept-encoding"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.api_route("/v1/{path:path}", methods=["GET", "POST"])
async def relay(path: str, request: Request):
    if request.headers.get("x-relay-secret") != RELAY_SECRET:
        return Response(status_code=401, content="unauthorized")
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    upstream_resp = await client.request(
        request.method,
        f"/v1/{path}",
        content=await request.body(),
        headers=headers,
        params=request.query_params,
    )
    resp_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in ("content-encoding", "transfer-encoding", "content-length", "connection")
    }
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )
