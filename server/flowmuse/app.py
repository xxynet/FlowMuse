import mimetypes
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .database import Database, Run, RunEvent, Workflow, now
from .images import read_image
from .provider import Provider, ProviderError
from .runner import TERMINAL, RunManager
from .schemas import Graph, RunCreate, WorkflowWrite


class RequestBoundary:
    """Bound streamed request bodies and reject cross-origin access to the local service."""
    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        origin = headers.get(b"origin", b"").decode("latin-1")
        if origin and origin not in self.settings.allowed_origins:
            return await JSONResponse({"detail": "不允许此来源访问"}, 403)(scope, receive, send)
        if scope["method"] in ("POST", "PUT", "PATCH"):
            parts, size = [], 0
            while True:
                part = await receive()
                if part["type"] == "http.disconnect":
                    return
                size += len(part.get("body", b""))
                if size > self.settings.max_request_bytes:
                    return await JSONResponse({"detail": "请求内容过大"}, 413)(scope, receive, send)
                parts.append(part.get("body", b""))
                if not part.get("more_body", False):
                    break
            body = b"".join(parts)
            sent = False

            async def bounded_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            return await self.app(scope, bounded_receive, send)
        return await self.app(scope, receive, send)


def run_summary(row: Run) -> dict:
    return {"id": row.id, "workflowId": row.workflow_id, "status": row.status, "error": row.error,
            "createdAt": row.created_at, "finishedAt": row.finished_at}


def workflow_detail(row: Workflow) -> dict:
    return {"id": row.id, "name": row.name, "createdAt": row.created_at,
            "updatedAt": row.updated_at, **row.graph}


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    # Windows registry associations can label .js as text/plain, blocking ES modules.
    mimetypes.add_type('text/javascript', '.js')
    mimetypes.add_type('text/css', '.css')
    config = settings or Settings()
    db = Database(config.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.initialize()
        async with httpx.AsyncClient(timeout=config.request_timeout, follow_redirects=False,
                                     transport=transport) as client, httpx.AsyncClient(
                                         timeout=30, follow_redirects=False, transport=transport) as image_client:
            app.state.image_client = image_client
            manager = RunManager(db, Provider(config, client), config)
            app.state.manager = manager
            await manager.recover()
            try:
                yield
            finally:
                await manager.close()
                await db.engine.dispose()

    app = FastAPI(title="FlowMuse API", version="0.1.0", lifespan=lifespan)
    app.state.database = db
    app.add_middleware(RequestBoundary, settings=config)
    app.add_middleware(CORSMiddleware, allow_origins=config.allowed_origins,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, error):
        # FastAPI's default validation response includes input values (possibly an API key).
        messages = [item["msg"] for item in error.errors() if item["type"] == "value_error"]
        return JSONResponse({"detail": messages[0] if messages else "请求参数或工作流格式无效"}, status_code=422)

    @app.exception_handler(Exception)
    async def internal_error(_request, _error):
        return JSONResponse({"detail": "服务内部错误，请检查服务状态"}, status_code=500)

    async def session():
        async with db.sessions() as value:
            yield value

    session_dependency = Depends(session)

    async def get_workflow(workflow_id: str, db_session: AsyncSession) -> Workflow:
        row = await db_session.get(Workflow, workflow_id)
        if row is None:
            raise HTTPException(404, "工作流不存在")
        return row

    async def get_run(run_id: str, db_session: AsyncSession) -> Run:
        row = await db_session.get(Run, run_id)
        if row is None:
            raise HTTPException(404, "运行记录不存在")
        return row

    @app.get("/api/health")
    async def health(db_session: AsyncSession = session_dependency):
        await db_session.execute(text("SELECT 1"))
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/workflows")
    async def workflows(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                        db_session: AsyncSession = session_dependency):
        rows = (await db_session.execute(select(Workflow.id, Workflow.name, Workflow.created_at,
                                               Workflow.updated_at).order_by(Workflow.updated_at.desc(),
                                                                            Workflow.id)
                                        .limit(limit).offset(offset))).all()
        return [{"id": row.id, "name": row.name, "createdAt": row.created_at,
                 "updatedAt": row.updated_at} for row in rows]

    @app.post("/api/workflows", status_code=201)
    async def create_workflow(body: WorkflowWrite, db_session: AsyncSession = session_dependency):
        row = Workflow(name=body.name, graph=Graph(nodes=body.nodes, edges=body.edges).public_dump())
        db_session.add(row)
        await db_session.commit()
        return workflow_detail(row)

    @app.get("/api/workflows/{workflow_id}")
    async def read_workflow(workflow_id: str, db_session: AsyncSession = session_dependency):
        return workflow_detail(await get_workflow(workflow_id, db_session))

    @app.put("/api/workflows/{workflow_id}")
    async def update_workflow(workflow_id: str, body: WorkflowWrite,
                              db_session: AsyncSession = session_dependency):
        row = await get_workflow(workflow_id, db_session)
        row.name, row.graph, row.updated_at = body.name, Graph(nodes=body.nodes, edges=body.edges).public_dump(), now()
        await db_session.commit()
        return workflow_detail(row)

    @app.delete("/api/workflows/{workflow_id}", status_code=204)
    async def delete_workflow(workflow_id: str, db_session: AsyncSession = session_dependency):
        await db_session.delete(await get_workflow(workflow_id, db_session))
        await db_session.commit()
        return Response(status_code=204)

    @app.post("/api/runs", status_code=202)
    async def start_run(body: RunCreate, request: Request, db_session: AsyncSession = session_dependency):
        if body.workflowId:
            await get_workflow(body.workflowId, db_session)
        try:
            run_id = await request.app.state.manager.submit(body, body.workflowId)
        except ProviderError as error:
            raise HTTPException(422, str(error)) from None
        except OverflowError:
            raise HTTPException(429, "运行队列已满，请稍后重试") from None
        return {"id": run_id, "status": "queued"}

    @app.get("/api/runs")
    async def runs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   workflowId: str | None = None, db_session: AsyncSession = session_dependency):
        # Defer the potentially large graph snapshot on list queries.
        from sqlalchemy.orm import defer
        query = select(Run).options(defer(Run.graph)).order_by(Run.created_at.desc(), Run.id)
        if workflowId:
            query = query.where(Run.workflow_id == workflowId)
        return [run_summary(row) for row in await db_session.scalars(query.limit(limit).offset(offset))]

    @app.get("/api/runs/{run_id}")
    async def read_run(run_id: str, after: int = Query(0, ge=0), db_session: AsyncSession = session_dependency):
        # Read status first: observing a terminal status guarantees its final event is committed.
        row = await get_run(run_id, db_session)
        rows = (await db_session.scalars(select(RunEvent)
                                         .where(RunEvent.run_id == run_id, RunEvent.sequence > after)
                                         .order_by(RunEvent.sequence).limit(101))).all()
        events = []
        for event in rows[:100]:
            payload = dict(event.payload)
            if payload.get("type") == "node_success" and payload.get("result", {}).get("images"):
                payload["result"] = {**payload["result"], "downloadUrls": [
                    f"/api/runs/{run_id}/images/{event.sequence}/{index}"
                    for index in range(len(payload["result"]["images"]))
                ]}
            events.append(payload)
        return {**run_summary(row), "events": events, "hasMore": len(rows) > 100,
                "nextCursor": events[-1]["sequence"] if events else after}

    @app.get("/api/runs/{run_id}/images/{sequence}/{index}")
    async def download_image(run_id: str, sequence: int, index: int, request: Request,
                             db_session: AsyncSession = session_dependency):
        event = await db_session.get(RunEvent, (run_id, sequence))
        if event is None or event.payload.get("type") != "node_success":
            raise HTTPException(404, "运行图片不存在")
        images = event.payload.get("result", {}).get("images", [])
        if index < 0 or index >= len(images):
            raise HTTPException(404, "运行图片不存在")
        source = images[index]
        # Release the database transaction before performing a potentially slow download.
        await db_session.rollback()
        data, mime, extension = await read_image(source, request.app.state.image_client, config.max_response_bytes)
        filename = f"flowmuse-{sequence}-{index + 1}.{extension}"
        return Response(data, media_type=mime, headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        })
    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str, request: Request, db_session: AsyncSession = session_dependency):
        await get_run(run_id, db_session)
        await request.app.state.manager.cancel(run_id)
        await db_session.rollback()
        return run_summary(await get_run(run_id, db_session))

    @app.delete("/api/runs/{run_id}", status_code=204)
    async def delete_run(run_id: str, db_session: AsyncSession = session_dependency):
        row = await get_run(run_id, db_session)
        if row.status not in TERMINAL:
            raise HTTPException(409, "请先取消正在执行的运行")
        await db_session.execute(delete(RunEvent).where(RunEvent.run_id == run_id))
        await db_session.delete(row)
        await db_session.commit()
        return Response(status_code=204)

    # API misses must stay JSON even when the compiled frontend is served.
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
    async def unknown_api(path: str):
        raise HTTPException(404, "接口不存在")

    if config.static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=config.static_dir / "assets", check_dir=False), name="assets")

        @app.get("/")
        async def index():
            return FileResponse(config.static_dir / "index.html")

        @app.get("/favicon.svg")
        async def favicon():
            return FileResponse(config.static_dir / "favicon.svg")

    return app


app = create_app()
