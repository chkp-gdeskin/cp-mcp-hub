from __future__ import annotations

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.settings import get_settings

router = APIRouter(prefix="/servers", tags=["proxy"], include_in_schema=False)

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


def _filter_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP}


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request) -> Response:
    target = f"http://127.0.0.1:{get_settings().MCP_PROXY_PORT}/servers/{path}"
    headers = _filter_headers(request.headers)
    accept = (headers.get("accept") or "").lower()
    is_sse = "text/event-stream" in accept

    client = httpx.AsyncClient(timeout=None if is_sse else httpx.Timeout(60.0))
    upstream = client.build_request(
        method=request.method,
        url=target,
        params=request.query_params,
        headers=headers,
        content=request.stream(),
    )
    upstream_response = await client.send(upstream, stream=True)
    response_headers = _filter_headers(upstream_response.headers)

    async def streamer():
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        streamer(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
