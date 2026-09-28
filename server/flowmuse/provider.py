"""OpenAI-compatible wire protocols. Never expose upstream error bodies or credentials."""
import asyncio
import json
import re
import socket
import ssl
from urllib.parse import urlsplit

import httpx

from .config import Settings
from .schemas import Params, decode_image, validate_url


class ProviderError(Exception):
    """Only static, safe messages may be raised across the provider boundary."""


def transport_error_message(error: httpx.HTTPError) -> str:
    """Classify failures without exposing exception strings, request bodies or headers."""
    if isinstance(error, httpx.ConnectError):
        cause, seen = error, set()
        while cause is not None and id(cause) not in seen:
            seen.add(id(cause))
            if isinstance(cause, ssl.SSLCertVerificationError):
                return "模型服务 TLS 证书校验失败，请检查证书链或代理证书（TLS_CERTIFICATE）"
            if isinstance(cause, ssl.SSLError):
                return "模型服务 TLS 握手失败，请检查服务端或代理的 TLS 配置（TLS_HANDSHAKE）"
            if isinstance(cause, socket.gaierror):
                return "无法解析模型服务或代理的域名，请检查地址与 DNS（DNS_ERROR）"
            cause = cause.__cause__ or cause.__context__
    messages = (
        (httpx.ConnectTimeout, "连接模型服务或代理超时（ConnectTimeout）"),
        (httpx.ReadTimeout, "等待模型服务响应超时（ReadTimeout）"),
        (httpx.WriteTimeout, "向模型服务发送数据超时（WriteTimeout）"),
        (httpx.PoolTimeout, "等待可用模型连接超时，请稍后重试（PoolTimeout）"),
        (httpx.TimeoutException, "模型请求超时（TimeoutException）"),
        (httpx.ProxyError, "无法建立代理连接，请检查后端代理配置（ProxyError）"),
        (httpx.ConnectError, "无法建立模型服务或代理连接，请检查地址与网络（ConnectError）"),
        (httpx.RemoteProtocolError, "模型服务或代理返回异常 HTTP 响应，或提前断开连接（RemoteProtocolError）"),
        (httpx.LocalProtocolError, "模型请求不符合 HTTP 协议，请检查请求配置（LocalProtocolError）"),
        (httpx.ReadError, "接收模型响应时连接中断，请检查模型服务或代理（ReadError）"),
        (httpx.WriteError, "发送模型请求时连接中断，请检查模型服务或代理（WriteError）"),
        (httpx.DecodingError, "模型响应的压缩编码无效，无法解码（DecodingError）"),
    )
    for error_type, message in messages:
        if isinstance(error, error_type):
            return message
    return "模型请求发生 HTTP 传输异常（HTTPError）"


def status_error_message(status: int) -> str:
    messages = {
        401: "模型服务认证失败，请检查 API Key",
        403: "模型服务拒绝访问，请检查账号或模型权限",
        404: "模型接口或资源不存在，请检查 Base URL 路径与模型名称",
        408: "模型服务处理请求超时",
        429: "模型服务触发限流或额度限制，请检查配额并稍后重试",
    }
    if status >= 500:
        message = "模型服务或其网关暂时不可用，请稍后重试或检查供应商状态"
    else:
        message = messages.get(status, "模型服务拒绝请求，请检查接口参数")
    return f"{message}（HTTP {status}）"

def image_url(value) -> str:
    if not isinstance(value, str):
        raise ProviderError("模型返回的图片地址格式无效")
    if value.startswith("data:"):
        try:
            decode_image(value)
        except ValueError:
            raise ProviderError("模型返回的图片数据无效或过大") from None
    else:
        try:
            url = urlsplit(value)
            if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
                raise ValueError()
        except ValueError:
            raise ProviderError("模型返回的图片地址格式无效") from None
    return value


def base64_image(value, output_format="png") -> str:
    if output_format not in ("png", "jpeg", "webp", "gif"):
        output_format = "png"
    return image_url(f"data:image/{output_format};base64,{value}")


def content_parts(message: dict) -> tuple[str, list[str]]:
    content = message.get("content")
    texts, images = [], []
    if isinstance(content, str):
        texts.append(content)
        for value in re.findall(r"!\[[^\]]*\]\(([^\s)]+)\)", content):
            images.append(image_url(value))
        if content.strip().startswith("data:image/"):
            images.append(image_url(content.strip()))
    elif isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                texts.append(part["text"])
            elif part.get("type") in ("image_url", "image"):
                value = part.get("image_url", part.get("url"))
                images.append(image_url(value.get("url") if isinstance(value, dict) else value))
    for part in message.get("images") or []:
        if isinstance(part, dict):
            value = part.get("image_url", part.get("url"))
            images.append(image_url(value.get("url") if isinstance(value, dict) else value))
    return "\n".join(texts), list(dict.fromkeys(images))


class Provider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    def connection(self, params: Params) -> tuple[str, dict]:
        try:
            configured = validate_url(self.settings.provider_base_url)
            base = validate_url(params.baseUrl or configured)
        except ValueError:
            raise ProviderError("模型服务 Base URL 配置无效") from None
        # A custom endpoint must never receive the server's default secret.
        key = params.apiKey or (self.settings.provider_api_key.get_secret_value() if base == configured else "")
        if not params.model.strip():
            raise ProviderError("请填写模型名称")
        if not key:
            raise ProviderError("请填写 API Key，或配置匹配该 Base URL 的服务端默认密钥")
        if "\r" in key or "\n" in key:
            raise ProviderError("API Key 配置无效")
        return base, {"Authorization": f"Bearer {key}"}

    async def request(self, params: Params, path: str, **kwargs) -> dict:
        base, headers = self.connection(params)
        async def send():
            async with self.client.stream("POST", base + path, headers=headers, **kwargs) as response:
                if response.status_code >= 300:
                    raise ProviderError(status_error_message(response.status_code))
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.settings.max_response_bytes:
                        raise ProviderError("模型响应超过大小限制")
                try:
                    result = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    raise ProviderError("模型服务返回了无效 JSON") from None
                if not isinstance(result, dict):
                    raise ProviderError("模型服务响应格式无效")
                return result
        try:
            return await asyncio.wait_for(send(), timeout=self.settings.request_timeout)
        except asyncio.TimeoutError:
            raise ProviderError("模型请求超过总时间预算，已停止等待（RequestDeadline）") from None
        except httpx.HTTPError as error:
            raise ProviderError(transport_error_message(error)) from None
        except httpx.InvalidURL:
            raise ProviderError("模型服务或代理 URL 格式无效（InvalidURL）") from None

    async def chat(self, params: Params, prompt: str, image: str | None = None) -> dict:
        content = [{"type": "text", "text": prompt}]
        if image:
            content.append({"type": "image_url", "image_url": {"url": image}})
        messages = []
        if params.system:
            messages.append({"role": "system", "content": params.system})
        messages.append({"role": "user", "content": content})
        result = await self.request(params, "/chat/completions", json={
            "model": params.model, "messages": messages, "temperature": params.temperature,
            "max_tokens": self.settings.max_output_tokens, "stream": False,
        })
        try:
            message = result["choices"][0]["message"]
            if not isinstance(message, dict):
                raise TypeError()
            return message
        except (KeyError, IndexError, TypeError):
            raise ProviderError("模型服务未返回有效消息") from None

    async def text(self, params: Params, prompt: str, image: str | None) -> dict:
        text, _ = content_parts(await self.chat(params, prompt, image))
        if not text.strip():
            raise ProviderError("模型服务未返回文本")
        return {"text": text}

    async def images(self, params: Params, prompt: str, image: str | None) -> dict:
        if params.apiType == "chat":
            images = []
            for _ in range(params.count):
                _, produced = content_parts(await self.chat(params, prompt, image))
                if not produced:
                    raise ProviderError("Chat 生图未返回图片；请确认模型支持图片输出")
                images.append(produced[0])
            return {"text": prompt, "images": images}
        payload = {"model": params.model, "prompt": prompt, "n": params.count, "size": params.size}
        if image:
            mime, data = decode_image(image)
            extension = mime.split("/")[1]
            result = await self.request(params, "/images/edits",
                                        data={k: str(v) for k, v in payload.items()},
                                        files={"image": (f"reference.{extension}", data, mime)})
        else:
            result = await self.request(params, "/images/generations", json=payload)
        try:
            images = [base64_image(item["b64_json"], result.get("output_format", "png"))
                      if item.get("b64_json") else image_url(item["url"]) for item in result["data"]]
        except (KeyError, TypeError, AttributeError):
            raise ProviderError("生图服务响应格式无效") from None
        if len(images) != params.count:
            raise ProviderError("生图服务返回的图片数量与请求不符")
        return {"text": prompt, "images": images}


