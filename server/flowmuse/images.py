"""Download images from recorded results without forwarding provider credentials."""
import asyncio
import ipaddress
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from .schemas import decode_image


def image_format(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", "gif"
    raise HTTPException(502, "下载地址未返回受支持的图片")


def validate_download_url(source: str):
    try:
        url = urlsplit(source)
        host = url.hostname or ""
        if (url.scheme not in ("http", "https") or not host or url.username or url.password
                or host.lower().rstrip(".") in ("localhost", "localhost.localdomain")
                or host.lower().rstrip(".").endswith((".localhost", ".local"))):
            raise ValueError()
        _ = url.port
    except ValueError:
        raise HTTPException(422, "图片下载地址无效") from None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if not address.is_global:
        raise HTTPException(422, "不支持下载本地网络图片")


async def read_image(source: str, client: httpx.AsyncClient, limit: int) -> tuple[bytes, str, str]:
    if source.startswith("data:"):
        try:
            _, data = await asyncio.to_thread(decode_image, source)
        except ValueError:
            raise HTTPException(422, "图片数据无效") from None
        if len(data) > limit:
            raise HTTPException(413, "图片超过下载大小限制")
    else:
        validate_download_url(source)

        async def fetch():
            # This accepts only a stored result URL, never an arbitrary URL supplied to the endpoint.
            # No redirects, provider Authorization header, or browser credentials are forwarded.
            async with client.stream("GET", source, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise HTTPException(502, f"无法下载图片（上游 HTTP {response.status_code}），链接可能已失效")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise HTTPException(413, "图片超过下载大小限制")
                return bytes(body)
        try:
            data = await asyncio.wait_for(fetch(), timeout=60)
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise HTTPException(504, "下载图片超时，请稍后重试") from None
        except httpx.HTTPError:
            raise HTTPException(502, "下载图片时连接中断，请稍后重试") from None
    mime, extension = image_format(data)
    return data, mime, extension
