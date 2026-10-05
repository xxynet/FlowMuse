import asyncio
import base64
import json
from contextlib import asynccontextmanager

import httpx
import pytest

from flowmuse.app import create_app
from flowmuse.config import Settings
from flowmuse.database import Run, RunEvent
from flowmuse.provider import Provider, ProviderError
from flowmuse.schemas import Params

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
IMAGE = "data:image/png;base64," + PNG
SECRET = "test-secret-do-not-persist"


def node(node_id, kind, **params):
    return {"id": node_id, "type": kind, "position": {"x": 10, "y": 20},
            "data": {"label": node_id, "status": "idle", "params": params}}


def edge(source, target, source_port, target_port):
    return {"id": f"{source}-{target}-{target_port}", "source": source, "target": target,
            "sourceHandle": source_port, "targetHandle": target_port}


def graph():
    return {"nodes": [node("upload", "image-upload", image=IMAGE),
                      node("llm", "llm", model="vision-model", apiKey=SECRET, prompt="describe", system="system"),
                      node("gen", "image-gen", model="image-model", apiKey=SECRET, prompt="fallback", count=2),
                      node("gallery", "output-gallery")],
            "edges": [edge("upload", "llm", "image", "image"), edge("llm", "gen", "text", "prompt"),
                      edge("upload", "gen", "image", "image"), edge("gen", "gallery", "images", "images")]}


def settings(tmp_path, **overrides):
    return Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
                    allowed_hosts=["testserver"], static_dir=tmp_path / "missing", **overrides)


@asynccontextmanager
async def client_for(config, handler=None):
    def default_handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "generated prompt"}}]})
    app = create_app(config, transport=httpx.MockTransport(handler or default_handler))
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client, app


async def finish(client, run_id):
    for _ in range(200):
        state = (await client.get(f"/api/runs/{run_id}")).json()
        if state["status"] not in ("queued", "running"):
            return state
        await asyncio.sleep(0.01)
    pytest.fail("Run did not finish")


async def test_workflow_crud_persistence_and_secret_removal(tmp_path):
    config = settings(tmp_path)
    body = {"name": "测试工作流", **graph()}
    async with client_for(config) as (client, _):
        response = await client.post("/api/workflows", json=body)
        assert response.status_code == 201
        assert SECRET not in response.text
        saved = response.json()
        assert saved["nodes"][0]["position"] == {"x": 10, "y": 20}
        assert len((await client.get("/api/workflows")).json()) == 1
        updated = await client.put(f"/api/workflows/{saved['id']}", json={**body, "name": "重命名"})
        assert updated.json()["name"] == "重命名"
    assert SECRET.encode() not in (tmp_path / "test.db").read_bytes()
    async with client_for(config) as (client, _):
        assert (await client.get(f"/api/workflows/{saved['id']}")).json()["name"] == "重命名"
        assert (await client.delete(f"/api/workflows/{saved['id']}")).status_code == 204
        assert (await client.get(f"/api/workflows/{saved['id']}")).status_code == 404


async def test_full_reference_image_workflow_and_incremental_events(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        if request.url.path == "/v1/chat/completions":
            payload = json.loads(request.content)
            assert payload["max_tokens"] == 2048
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][1]["content"][1]["image_url"]["url"] == IMAGE
            return httpx.Response(200, json={"choices": [{"message": {"content": "generated prompt"}}]})
        assert request.url.path == "/v1/images/edits"
        assert "multipart/form-data" in request.headers["content-type"]
        assert b"generated prompt" in request.content
        assert base64.b64decode(PNG) in request.content
        return httpx.Response(200, json={"data": [{"b64_json": PNG}, {"url": "https://example.com/b.png"}]})
    async with client_for(settings(tmp_path), handler) as (client, app):
        response = await client.post("/api/runs", json=graph())
        assert response.status_code == 202
        run_id = response.json()["id"]
        state = await finish(client, run_id)
        assert state["status"] == "success"
        assert [item["nodeId"] for item in state["events"] if item["type"] == "node_success"] == [
            "upload", "llm", "gen", "gallery"]
        assert state["events"][-2]["result"]["images"][0] == IMAGE
        assert state["events"][-1]["type"] == "run_success"
        assert (await client.get(f"/api/runs/{run_id}?after={state['nextCursor']}")).json()["events"] == []
        assert SECRET not in json.dumps(state)
        async with app.state.database.sessions() as session:
            stored = await session.get(Run, run_id)
            assert SECRET not in json.dumps(stored.graph)
        assert len(requests) == 2
        assert len((await client.get("/api/runs")).json()) == 1
        assert (await client.delete(f"/api/runs/{run_id}")).status_code == 204
        assert (await client.get(f"/api/runs/{run_id}")).status_code == 404


@pytest.mark.parametrize("case", ["cycle", "missing", "port", "duplicate_node", "duplicate_port", "size", "count", "nan", "image", "extra"])
async def test_invalid_graphs_rejected_without_leaking_inputs(tmp_path, case):
    body = graph()
    if case == "cycle":
        body["edges"].append(edge("llm", "llm", "text", "text"))
    elif case == "missing":
        body["edges"][0]["source"] = "not-found"
    elif case == "port":
        body["edges"][0]["sourceHandle"] = "text"
    elif case == "duplicate_node":
        body["nodes"].append(body["nodes"][0])
    elif case == "duplicate_port":
        body["edges"].append({**body["edges"][0], "id": "second"})
    elif case == "size":
        body["nodes"][2]["data"]["params"]["size"] = "bad"
    elif case == "count":
        body["nodes"][2]["data"]["params"]["count"] = 1000
    elif case == "nan":
        body["nodes"][1]["data"]["params"]["temperature"] = "NaN"
    elif case == "image":
        body["nodes"][0]["data"]["params"]["image"] = "data:image/png;base64,c2VjcmV0"
    else:
        body["nodes"][0]["data"]["params"]["unexpected"] = SECRET
    async with client_for(settings(tmp_path)) as (client, _):
        response = await client.post("/api/runs", json=body)
        assert response.status_code == 422
        assert SECRET not in response.text
        assert (await client.get("/api/runs")).json() == []


async def test_upstream_errors_are_safe_and_stop_downstream(tmp_path, caplog):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(401, json={"error": f"sensitive prompt {SECRET}"})
    async with client_for(settings(tmp_path), handler) as (client, _):
        run_id = (await client.post("/api/runs", json=graph())).json()["id"]
        state = await finish(client, run_id)
        assert state["status"] == "error"
        assert "401" in state["error"]
        assert SECRET not in json.dumps(state)
        assert not any(event.get("nodeId") == "gen" for event in state["events"])
        assert len(requests) == 1
    assert SECRET not in caplog.text


async def test_cancel_queued_running_and_queue_limit(tmp_path):
    entered = asyncio.Event()
    async def handler(request):
        entered.set()
        await asyncio.sleep(30)
        return httpx.Response(200, json={})
    async with client_for(settings(tmp_path, max_concurrent_runs=1, max_pending_runs=2), handler) as (client, _):
        first = (await client.post("/api/runs", json=graph())).json()["id"]
        await asyncio.wait_for(entered.wait(), 2)
        second = (await client.post("/api/runs", json=graph())).json()["id"]
        assert (await client.post("/api/runs", json=graph())).status_code == 429
        assert (await client.delete(f"/api/runs/{first}")).status_code == 409
        assert (await client.post(f"/api/runs/{second}/cancel")).json()["status"] == "cancelled"
        assert (await client.post(f"/api/runs/{first}/cancel")).json()["status"] == "cancelled"
        again = await client.post(f"/api/runs/{first}/cancel")
        assert again.json()["status"] == "cancelled"
        state = (await client.get(f"/api/runs/{second}")).json()
        assert [event["type"] for event in state["events"]] == ["run_cancelled"]


async def test_shutdown_and_crash_recovery(tmp_path):
    config = settings(tmp_path)
    async def handler(request):
        await asyncio.sleep(30)
        return httpx.Response(200, json={})
    async with client_for(config, handler) as (client, app):
        run_id = (await client.post("/api/runs", json=graph())).json()["id"]
        async with app.state.database.sessions() as session:
            abandoned = Run(graph={}, status="running")
            session.add(abandoned)
            await session.commit()
            abandoned_id = abandoned.id
    async with client_for(config) as (client, _):
        assert (await client.get(f"/api/runs/{run_id}")).json()["status"] == "interrupted"
        recovered = (await client.get(f"/api/runs/{abandoned_id}")).json()
        assert recovered["status"] == "interrupted"
        assert recovered["events"][-1]["type"] == "run_interrupted"


@pytest.mark.parametrize("budget", ["request", "run"])
async def test_timeout_budget(tmp_path, budget):
    async def handler(request):
        await asyncio.sleep(2)
        return httpx.Response(200, json={})
    overrides = {f"{budget}_timeout": 0.03}
    async with client_for(settings(tmp_path, **overrides), handler) as (client, _):
        run_id = (await client.post("/api/runs", json=graph())).json()["id"]
        state = await finish(client, run_id)
        assert state["status"] == "error"
        assert "超" in state["error"]


async def test_request_boundary_health_and_missing_routes(tmp_path):
    async with client_for(settings(tmp_path, max_request_bytes=1024)) as (client, _):
        assert (await client.get("/api/health")).json()["status"] == "ok"
        schema = (await client.get("/openapi.json")).json()
        assert "/api/{path}" not in schema["paths"]
        operations = [item["operationId"] for path in schema["paths"].values() for item in path.values()]
        assert len(operations) == len(set(operations))
        assert (await client.post("/api/runs", content=b"x" * 1025)).status_code == 413
        assert (await client.get("/api/health", headers={"Origin": "https://evil.example"})).status_code == 403
        assert (await client.get("/api/health", headers={"Host": "evil.example"})).status_code == 400
        assert (await client.get("/api/missing")).status_code == 404
        assert (await client.get("/api/runs/missing")).status_code == 404
        assert (await client.post("/api/runs", json={"nodes": [], "edges": []})).status_code == 422


async def test_default_secret_never_sent_to_custom_endpoint(tmp_path):
    called = []
    def handler(request):
        called.append(request)
        return httpx.Response(200, json={})
    config = settings(tmp_path, provider_api_key=SECRET)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(config, client)
        assert provider.connection(Params(model="test"))[1]["Authorization"] == f"Bearer {SECRET}"
        with pytest.raises(ProviderError):
            await provider.text(Params(model="test", baseUrl="https://other.example/v1"), "hello", None)
        assert not called


async def test_image_generation_and_chat_image_formats(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path.endswith("generations"):
            assert json.loads(request.content)["n"] == 1
            return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
        content = ([{"type": "image_url", "image_url": {"url": IMAGE}}] if len(requests) == 2
                   else f"![result]({IMAGE})")
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(settings(tmp_path), client)
        params = Params(model="test", apiKey=SECRET)
        assert (await provider.images(params, "draw", None))["images"] == [IMAGE]
        params.apiType, params.count = "chat", 2
        assert (await provider.images(params, "draw", IMAGE))["images"] == [IMAGE, IMAGE]
        assert len(requests) == 3


@pytest.mark.parametrize("response", [httpx.Response(302, headers={"Location": "https://evil.example"}),
                                     httpx.Response(200, text="not-json"),
                                     httpx.Response(200, json={"choices": []}),
                                     httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})])
async def test_malformed_provider_responses_fail_safely(tmp_path, response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
        provider = Provider(settings(tmp_path), client)
        with pytest.raises(ProviderError):
            await provider.text(Params(model="test", apiKey=SECRET), "hello", None)


async def test_response_size_budget(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 2048))) as client:
        provider = Provider(settings(tmp_path, max_response_bytes=1024), client)
        with pytest.raises(ProviderError, match="大小"):
            await provider.text(Params(model="test", apiKey=SECRET), "hello", None)


async def test_event_pagination(tmp_path):
    async with client_for(settings(tmp_path)) as (client, app):
        async with app.state.database.sessions() as session:
            run = Run(graph={}, status="success")
            session.add(run)
            await session.flush()
            session.add_all([RunEvent(run_id=run.id, sequence=i, payload={"sequence": i, "type": "node_success"})
                             for i in range(1, 106)])
            await session.commit()
            run_id = run.id
        page = (await client.get(f"/api/runs/{run_id}")).json()
        assert page["hasMore"] and page["nextCursor"] == 100
        second = (await client.get(f"/api/runs/{run_id}?after=100")).json()
        assert not second["hasMore"] and len(second["events"]) == 5



async def test_static_frontend_serves_javascript_with_correct_mime(tmp_path):
    import mimetypes
    static = tmp_path / "web"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text('<div id="app"></div>', encoding="utf-8")
    (static / "assets" / "app.js").write_text('console.log("test")', encoding="utf-8")
    (static / "assets" / "app.css").write_text('body {}', encoding="utf-8")
    mimetypes.add_type("text/plain", ".js")
    config = settings(tmp_path)
    config.static_dir = static
    async with client_for(config) as (client, _):
        assert (await client.get("/")).status_code == 200
        response = await client.get("/assets/app.js")
        assert response.headers["content-type"].startswith("text/javascript")
        assert (await client.get("/assets/app.css")).headers["content-type"].startswith("text/css")
        assert (await client.get("/api/missing")).status_code == 404



@pytest.mark.parametrize("error_type", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout,
                                       httpx.PoolTimeout, httpx.ProxyError, httpx.ConnectError,
                                       httpx.RemoteProtocolError, httpx.LocalProtocolError,
                                       httpx.ReadError, httpx.WriteError, httpx.DecodingError])
async def test_transport_failure_categories_are_safe(tmp_path, error_type):
    calls = []
    def handler(request):
        calls.append(request)
        raise error_type(f"{SECRET}: sensitive prompt and proxy credentials", request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(settings(tmp_path), client)
        with pytest.raises(ProviderError) as caught:
            await provider.text(Params(model="test", apiKey=SECRET), "hello", None)
        assert error_type.__name__ in str(caught.value)
        assert SECRET not in str(caught.value)
        assert "sensitive prompt" not in str(caught.value)
        assert len(calls) == 1  # Never automatically retry a potentially billable request.


@pytest.mark.parametrize("cause_kind,code", [("certificate", "TLS_CERTIFICATE"),
                                            ("tls", "TLS_HANDSHAKE"), ("dns", "DNS_ERROR")])
async def test_connection_cause_classification(tmp_path, cause_kind, code):
    import socket
    import ssl
    causes = {"certificate": ssl.SSLCertVerificationError(1, SECRET),
              "tls": ssl.SSLError(1, SECRET), "dns": socket.gaierror(1, SECRET)}
    def handler(request):
        raise httpx.ConnectError(SECRET, request=request) from causes[cause_kind]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(settings(tmp_path), client)
        with pytest.raises(ProviderError) as caught:
            await provider.text(Params(model="test", apiKey=SECRET), "hello", None)
        assert code in str(caught.value)
        assert SECRET not in str(caught.value)


async def test_response_disconnect_is_preserved_in_run_events(tmp_path):
    def handler(request):
        raise httpx.RemoteProtocolError(SECRET, request=request)
    async with client_for(settings(tmp_path), handler) as (client, _):
        run_id = (await client.post("/api/runs", json=graph())).json()["id"]
        state = await finish(client, run_id)
        assert state["status"] == "error"
        assert "RemoteProtocolError" in state["error"]
        assert SECRET not in json.dumps(state)
        assert not any(event.get("nodeId") == "gen" for event in state["events"])


async def test_upstream_503_reports_service_unavailability(tmp_path):
    async with client_for(settings(tmp_path), lambda r: httpx.Response(503, text=SECRET)) as (client, _):
        run_id = (await client.post("/api/runs", json=graph())).json()["id"]
        state = await finish(client, run_id)
        assert "503" in state["error"]
        assert "暂时不可用" in state["error"]
        assert "额度" not in state["error"]
        assert SECRET not in json.dumps(state)


async def record_image(app, source):
    async with app.state.database.sessions() as session:
        row = Run(graph={}, status="success")
        session.add(row)
        await session.flush()
        session.add(RunEvent(run_id=row.id, sequence=1, payload={
            "sequence": 1, "type": "node_success", "nodeId": "gen",
            "result": {"images": [source]},
        }))
        await session.commit()
        return row.id


async def test_inline_result_download_has_correct_bytes_and_filename(tmp_path):
    async with client_for(settings(tmp_path)) as (client, app):
        run_id = await record_image(app, IMAGE)
        state = (await client.get(f"/api/runs/{run_id}")).json()
        url = state["events"][0]["result"]["downloadUrls"][0]
        response = await client.get(url)
        assert response.status_code == 200
        assert response.content == base64.b64decode(PNG)
        assert response.headers["content-type"] == "image/png"
        assert response.headers["content-disposition"] == 'attachment; filename="flowmuse-1-1.png"'
        assert response.headers["cache-control"] == "no-store"
        assert (await client.get(f"/api/runs/{run_id}/images/1/-1")).status_code == 404
        assert (await client.get(f"/api/runs/{run_id}/images/1/1")).status_code == 404
        assert (await client.get(f"/api/runs/{run_id}/images/2/0")).status_code == 404
        assert (await client.get("/api/runs/missing/images/1/0")).status_code == 404


async def test_remote_result_download_does_not_forward_credentials(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        # Extension comes from the bytes, not a misleading URL or Content-Type.
        return httpx.Response(200, content=base64.b64decode(PNG), headers={"content-type": "application/octet-stream"})
    async with client_for(settings(tmp_path, provider_api_key=SECRET), handler) as (client, app):
        run_id = await record_image(app, "https://images.example/result.svg?signature=test")
        response = await client.get(f"/api/runs/{run_id}/images/1/0", headers={"cookie": "private=test"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["content-disposition"].endswith('.png"')
        assert len(calls) == 1


@pytest.mark.parametrize("source", ["file:///private/image.png", "http://localhost/image.png",
                                    "http://127.0.0.1/image.png", "http://192.168.1.1/image.png",
                                    "https://user:secret@images.example/image.png"])
async def test_invalid_download_addresses_are_rejected(tmp_path, source):
    def handler(request):
        pytest.fail("Invalid address must not be requested")
    async with client_for(settings(tmp_path), handler) as (client, app):
        run_id = await record_image(app, source)
        response = await client.get(f"/api/runs/{run_id}/images/1/0")
        assert response.status_code == 422
        assert "secret" not in response.text


@pytest.mark.parametrize("status,body", [(302, b""), (403, b"secret upstream body"),
                                        (200, b"<html>Not an image</html>")])
async def test_invalid_remote_download_returns_safe_error(tmp_path, status, body):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=body, headers={"Location": "http://127.0.0.1/private"})
    async with client_for(settings(tmp_path), handler) as (client, app):
        run_id = await record_image(app, "https://images.example/result.png")
        response = await client.get(f"/api/runs/{run_id}/images/1/0")
        assert response.status_code == 502
        assert "secret upstream body" not in response.text
        assert len(calls) == 1


async def test_download_size_and_network_limits(tmp_path):
    def handler(request):
        return httpx.Response(200, content=base64.b64decode(PNG) + b"x" * 2048)
    async with client_for(settings(tmp_path, max_response_bytes=1024), handler) as (client, app):
        run_id = await record_image(app, "https://images.example/result.png")
        assert (await client.get(f"/api/runs/{run_id}/images/1/0")).status_code == 413


@pytest.mark.parametrize("error_type,status", [(httpx.ReadTimeout, 504), (httpx.ConnectError, 502)])
async def test_download_transport_errors_are_safe(tmp_path, error_type, status):
    def handler(request):
        raise error_type(SECRET, request=request)
    async with client_for(settings(tmp_path), handler) as (client, app):
        run_id = await record_image(app, "https://images.example/result.png")
        response = await client.get(f"/api/runs/{run_id}/images/1/0")
        assert response.status_code == status
        assert SECRET not in response.text


@pytest.mark.parametrize("api_type", ["images", "chat"])
async def test_two_reference_workflow_round_trip_and_order(tmp_path, api_type):
    # Distinct validated MIME types make reversed or dropped references observable.
    gif = b"GIF89a" + b"second-reference"
    second = "data:image/gif;base64," + base64.b64encode(gif).decode()
    body = {
        "nodes": [node("original", "image-upload", image=IMAGE),
                  node("character", "image-upload", image=second),
                  node("gen", "image-gen", model="test", apiKey=SECRET,
                       apiType=api_type, prompt="replace the character, preserve layout"),
                  node("gallery", "output-gallery")],
        # Deliberately put port 2 first in the edge list.
        "edges": [edge("character", "gen", "image", "image2"),
                  edge("original", "gen", "image", "image"),
                  edge("gen", "gallery", "images", "images")],
    }
    requests = []
    def handler(request):
        requests.append(request)
        if api_type == "chat":
            assert request.url.path == "/v1/chat/completions"
            content = json.loads(request.content)["messages"][-1]["content"]
            assert content[0]["text"] == body["nodes"][2]["data"]["params"]["prompt"]
            assert [part["image_url"]["url"] for part in content[1:]] == [IMAGE, second]
            return httpx.Response(200, json={"choices": [{"message": {"images": [{"url": IMAGE}]}}]})
        assert request.url.path == "/v1/images/edits"
        assert request.content.count(b'name="image[]"') == 2
        assert request.content.index(base64.b64decode(PNG)) < request.content.index(gif)
        assert b"replace the character, preserve layout" in request.content
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/workflows", json={"name": "人物替换", **body})
        assert response.status_code == 201
        saved = (await client.get("/api/workflows/" + response.json()["id"])).json()
        assert saved["edges"] == [{**item, "type": "smoothstep"} for item in body["edges"]]
        assert saved["nodes"][0]["data"]["params"]["image"] == IMAGE
        assert saved["nodes"][1]["data"]["params"]["image"] == second
        assert SECRET not in json.dumps(saved)
        saved["nodes"][2]["data"]["params"]["apiKey"] = SECRET
        response = await client.post("/api/runs", json={"nodes": saved["nodes"], "edges": saved["edges"]})
        assert response.status_code == 202
        state = await finish(client, response.json()["id"])
        assert state["status"] == "success"
        assert state["events"][-2]["result"]["images"] == [IMAGE]
        assert len(requests) == 1


async def test_second_reference_requires_first_before_run_is_created(tmp_path):
    body = {"nodes": [node("upload", "image-upload", image=IMAGE),
                      node("gen", "image-gen", model="test", apiKey=SECRET, prompt="swap")],
            "edges": [edge("upload", "gen", "image", "image2")]}
    async with client_for(settings(tmp_path)) as (client, _):
        response = await client.post("/api/runs", json=body)
        assert response.status_code == 422
        assert "参考图 1" in response.json()["detail"]
        assert (await client.get("/api/runs")).json() == []


async def test_missing_character_upload_rejected_before_model_call(tmp_path):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})
    body = {"nodes": [node("original", "image-upload", image=IMAGE),
                      node("character", "image-upload"),
                      node("gen", "image-gen", model="test", apiKey=SECRET, prompt="swap")],
            "edges": [edge("original", "gen", "image", "image"),
                      edge("character", "gen", "image", "image2")]}
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/runs", json=body)
        assert response.status_code == 422
        assert "选择图片" in response.json()["detail"]
        assert not requests
        assert (await client.get("/api/runs")).json() == []


async def test_single_reference_keeps_legacy_multipart_field(tmp_path):
    def handler(request):
        assert request.url.path == "/v1/images/edits"
        assert request.content.count(b'name="image"') == 1
        assert b'name="image[]"' not in request.content
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(settings(tmp_path), client)
        assert (await provider.images(Params(model="test", apiKey=SECRET), "draw", IMAGE))["images"] == [IMAGE]


@pytest.mark.parametrize("api_type", ["images", "chat"])
async def test_two_reference_provider_rejects_missing_first(tmp_path, api_type):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected call"))) as client:
        provider = Provider(settings(tmp_path), client)
        with pytest.raises(ProviderError, match="参考图 1"):
            await provider.images(Params(model="test", apiKey=SECRET, apiType=api_type), "draw", None, IMAGE)


@pytest.mark.parametrize("api_type", ["images", "chat"])
@pytest.mark.parametrize("plot", ["第一格：主角登上月球。\n第二格：遇见小兔子。\n第三格：一起种花。\n第四格：花开了。",
                                  "主角寻找丢失的钥匙，最后发现钥匙在自己的口袋里。"])
async def test_user_comic_story_round_trip_and_prompt_composition(tmp_path, api_type, plot):
    template = "画一张 2×2 四格漫画。\n用户剧情：\n{{ 剧情 }}\n保留参考角色，按左上、右上、左下、右下阅读。"
    expected = template.replace("{{ 剧情 }}", plot)
    requests = []
    def handler(request):
        requests.append(request)
        if api_type == "chat":
            assert request.url.path == "/v1/chat/completions"
            content = json.loads(request.content)["messages"][-1]["content"]
            assert content[0]["text"] == expected
            assert content[1]["image_url"]["url"] == IMAGE
            return httpx.Response(200, json={"choices": [{"message": {"images": [{"url": IMAGE}]}}]})
        assert request.url.path == "/v1/images/edits"
        assert expected.encode() in request.content
        assert b'name="n"\r\n\r\n1' in request.content
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
    body = {
        "nodes": [node("character", "image-upload", image=IMAGE),
                  node("story", "variable-set", variables=[{"name": "剧情", "value": plot}]),
                  node("gen", "image-gen", model="test", apiKey=SECRET, apiType=api_type, prompt=template),
                  node("gallery", "output-gallery")],
        "edges": [edge("story", "gen", "variables", "variables"),
                  edge("character", "gen", "image", "image"),
                  edge("gen", "gallery", "images", "images")],
    }
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/workflows", json={"name": "自定义剧情", **body})
        assert response.status_code == 201
        saved = (await client.get("/api/workflows/" + response.json()["id"])).json()
        assert saved["nodes"][1]["data"]["params"]["variables"] == [{"name": "剧情", "value": plot}]
        saved["nodes"][2]["data"]["params"]["apiKey"] = SECRET
        response = await client.post("/api/runs", json={"nodes": saved["nodes"], "edges": saved["edges"]})
        assert response.status_code == 202
        state = await finish(client, response.json()["id"])
        assert state["status"] == "success"
        results = {item["nodeId"]: item["result"] for item in state["events"] if item["type"] == "node_success"}
        assert results["story"]["variables"] == {"剧情": plot}
        assert results["gen"]["text"] == expected
        assert results["gallery"]["images"] == [IMAGE]
        assert len(requests) == 1  # Story input does not require a model request.


@pytest.mark.parametrize("text", ["", " \n\t", "a" * 32001])
async def test_invalid_text_input_rejected_before_run_creation(tmp_path, text):
    async with client_for(settings(tmp_path)) as (client, _):
        response = await client.post("/api/runs", json={"nodes": [node("story", "text-input", text=text)]})
        assert response.status_code == 422
        assert (await client.get("/api/runs")).json() == []


async def test_text_input_runs_without_provider_credentials(tmp_path):
    def handler(request):
        pytest.fail("Text input must not request a model")
    text = "  用户写的剧情 {{text}}\n第二行  "
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/runs", json={"nodes": [node("story", "text-input", text=text)]})
        assert response.status_code == 202
        state = await finish(client, response.json()["id"])
        assert state["status"] == "success"
        assert state["events"][-2]["result"] == {"text": text}


async def test_full_upstream_prompt_still_overrides_local_template_and_material(tmp_path):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["prompt"] == "完整上游提示词"
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
    body = {
        "nodes": [node("material", "text-input", text="剧情素材"),
                  node("prompt", "text-input", text="完整上游提示词"),
                  node("gen", "image-gen", model="test", apiKey=SECRET, prompt="本地格式：{{text}}")],
        "edges": [edge("material", "gen", "text", "text"), edge("prompt", "gen", "text", "prompt")],
    }
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/runs", json=body)
        assert response.status_code == 202
        assert (await finish(client, response.json()["id"]))["status"] == "success"


@pytest.mark.parametrize("kind", ["llm", "image-gen"])
async def test_named_variable_chain_round_trip_and_override(tmp_path, kind):
    expected = "水彩：新剧情\n字面值 {{unknown}}"
    requests = []
    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        if kind == "llm":
            assert payload["messages"][-1]["content"][0]["text"] == expected
            return httpx.Response(200, json={"choices": [{"message": {"content": "result"}}]})
        assert payload["prompt"] == expected
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
    body = {
        "nodes": [
            node("defaults", "variable-set", variables=[{"name": "style", "value": "水彩"},
                                                       {"name": "story", "value": "原剧情"}]),
            node("custom", "variable-set", variables=[{"name": "story", "value": "新剧情\n字面值 {{unknown}}"}]),
            node("model", kind, model="test", apiKey=SECRET, prompt="{style}：{{ story }}"),
        ],
        "edges": [edge("defaults", "custom", "variables", "variables"),
                  edge("custom", "model", "variables", "variables")],
    }
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/workflows", json={"name": "通用变量", **body})
        assert response.status_code == 201
        saved = (await client.get("/api/workflows/" + response.json()["id"])).json()
        assert saved["nodes"][1]["data"]["params"]["variables"] == body["nodes"][1]["data"]["params"]["variables"]
        saved["nodes"][2]["data"]["params"]["apiKey"] = SECRET
        response = await client.post("/api/runs", json={"nodes": saved["nodes"], "edges": saved["edges"]})
        assert response.status_code == 202
        state = await finish(client, response.json()["id"])
        assert state["status"] == "success"
        result = next(item["result"] for item in state["events"] if item.get("nodeId") == "custom"
                      and item["type"] == "node_success")
        assert result["variables"] == {"style": "水彩", "story": "新剧情\n字面值 {{unknown}}"}
        assert len(requests) == 1


@pytest.mark.parametrize("bindings", [
    [], [{"name": "", "value": "data"}], [{"name": "story", "value": " \n"}],
    [{"name": "1bad", "value": "data"}],
    [{"name": "story", "value": "one"}, {"name": "story", "value": "two"}],
    [{"name": "story", "value": "a" * 32001}],
    [{"name": f"v{i}", "value": "x"} for i in range(51)],
])
async def test_invalid_variable_nodes_are_rejected_without_model_calls(tmp_path, bindings):
    def handler(request):
        pytest.fail("Invalid variables must not request a model")
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/runs", json={"nodes": [node("vars", "variable-set", variables=bindings)]})
        assert response.status_code == 422
        assert (await client.get("/api/runs")).json() == []


@pytest.mark.parametrize("prompt", ["{missing}", "{{ missing }}", "{story}{story}"])
async def test_missing_variable_or_expanded_prompt_budget_stops_model_call(tmp_path, prompt):
    def handler(request):
        pytest.fail("Invalid expansion must not request a model")
    body = {
        "nodes": [node("vars", "variable-set", variables=[{"name": "story", "value": "s" * 20000}]),
                  node("gen", "image-gen", model="test", apiKey=SECRET, prompt=prompt)],
        "edges": [edge("vars", "gen", "variables", "variables")],
    }
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/runs", json=body)
        assert response.status_code == 202
        state = await finish(client, response.json()["id"])
        assert state["status"] == "error"
        assert "未定义变量" in state["error"] or "32000" in state["error"]
        assert "s" * 100 not in state["error"]


async def test_upstream_prompt_and_named_variables_compose_together(tmp_path):
    def handler(request):
        assert json.loads(request.content)["prompt"] == "完整模板：水彩"
        return httpx.Response(200, json={"data": [{"b64_json": PNG}]})
    body = {
        "nodes": [node("vars", "variable-set", variables=[{"name": "style", "value": "水彩"}]),
                  node("prompt", "text-input", text="完整模板：{style}"),
                  node("gen", "image-gen", model="test", apiKey=SECRET, prompt="unused")],
        "edges": [edge("vars", "gen", "variables", "variables"), edge("prompt", "gen", "text", "prompt")],
    }
    async with client_for(settings(tmp_path), handler) as (client, _):
        response = await client.post("/api/runs", json=body)
        assert response.status_code == 202
        assert (await finish(client, response.json()["id"]))["status"] == "success"
