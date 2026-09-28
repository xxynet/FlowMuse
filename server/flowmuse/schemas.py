import base64
import binascii
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NodeKind = Literal["image-upload", "llm", "image-gen", "output-gallery"]
PORTS = {
    "image-upload": ({}, {"image": "image"}),
    "llm": ({"text": "text", "image": "image"}, {"text": "text"}),
    "image-gen": ({"prompt": "text", "image": "image"}, {"images": "images"}),
    "output-gallery": ({"images": "images"}, {}),
}


def validate_url(value: str) -> str:
    try:
        url = urlsplit(value)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in value)):
            raise ValueError()
        _ = url.port
    except ValueError:
        raise ValueError("URL 必须是无账号、查询参数或片段的 HTTP(S) 地址") from None
    return value.rstrip("/")


def decode_image(value: str) -> tuple[str, bytes]:
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp|gif));base64,([A-Za-z0-9+/=]+)", value)
    if not match or len(match[2]) > 14 * 1024 * 1024:
        raise ValueError("图片必须是 PNG、JPEG、WebP 或 GIF，且不超过 10 MB")
    try:
        data = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("图片 Base64 格式无效") from None
    mime = match[1]
    valid = {
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/webp": data.startswith(b"RIFF") and data[8:12] == b"WEBP",
        "image/gif": data.startswith((b"GIF87a", b"GIF89a")),
    }
    if not valid[mime] or len(data) > 10 * 1024 * 1024:
        raise ValueError("图片内容与格式不符，或超过 10 MB")
    return mime, data


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image: str = ""
    baseUrl: str = Field("", max_length=2048)
    apiKey: str = Field("", max_length=4096, repr=False)
    model: str = Field("", max_length=200)
    system: str = Field("", max_length=32000)
    prompt: str = Field("", max_length=32000)
    temperature: float = Field(0.7, ge=0, le=2, allow_inf_nan=False)
    apiType: Literal["images", "chat"] = "images"
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    count: int = Field(1, ge=1, le=9)

    @field_validator("baseUrl")
    @classmethod
    def base_url(cls, value):
        return validate_url(value) if value else value

    @field_validator("apiKey")
    @classmethod
    def api_key(cls, value):
        if "\r" in value or "\n" in value:
            raise ValueError("API Key 格式无效")
        return value

    @field_validator("image")
    @classmethod
    def image_data(cls, value):
        if value:
            decode_image(value)
        return value


class Position(BaseModel):
    x: float = Field(0, allow_inf_nan=False)
    y: float = Field(0, allow_inf_nan=False)


class NodeData(BaseModel):
    label: str = Field("", max_length=200)
    params: Params = Field(default_factory=Params)


class Node(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    type: NodeKind
    position: Position = Field(default_factory=Position)
    data: NodeData


class Edge(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    source: str
    target: str
    sourceHandle: str
    targetHandle: str
    type: str = "smoothstep"


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list, max_length=100)
    edges: list[Edge] = Field(default_factory=list, max_length=300)

    @model_validator(mode="after")
    def validate_graph(self):
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("节点 ID 不得重复")
        if len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("连线 ID 不得重复")
        occupied = set()
        for edge in self.edges:
            if edge.source not in nodes or edge.target not in nodes:
                raise ValueError("连线引用了不存在的节点")
            output = PORTS[nodes[edge.source].type][1].get(edge.sourceHandle)
            input_kind = PORTS[nodes[edge.target].type][0].get(edge.targetHandle)
            if output is None or input_kind is None or output != input_kind:
                raise ValueError("连线端口不存在或类型不兼容")
            port = (edge.target, edge.targetHandle)
            if port in occupied:
                raise ValueError("每个输入端口只允许一条连线")
            occupied.add(port)
        self.ordered_nodes()
        return self

    def ordered_nodes(self) -> list[Node]:
        indegree = {node.id: 0 for node in self.nodes}
        outgoing = {node.id: [] for node in self.nodes}
        for edge in self.edges:
            indegree[edge.target] += 1
            outgoing[edge.source].append(edge.target)
        queue = [node.id for node in self.nodes if indegree[node.id] == 0]
        by_id = {node.id: node for node in self.nodes}
        order = []
        for node_id in queue:
            order.append(by_id[node_id])
            for target in outgoing[node_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if len(order) != len(self.nodes):
            raise ValueError("画布中存在循环连线，无法执行")
        return order

    def public_dump(self) -> dict:
        result = self.model_dump()
        for node in result["nodes"]:
            node["data"]["params"].pop("apiKey", None)
            node["data"]["status"] = "idle"
        return result


class WorkflowWrite(Graph):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError("工作流名称不能为空")
        return value.strip()


class RunCreate(Graph):
    workflowId: str | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.nodes:
            raise ValueError("画布为空，请先添加节点或载入玩法模板")
        return self
