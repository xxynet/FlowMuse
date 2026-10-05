import asyncio

from sqlalchemy import func, select

from .config import Settings
from .database import Database, Run, RunEvent, now
from .provider import Provider, ProviderError
from .schemas import Graph, Node
from .templates import TemplateError, merge_variables, resolve_template

TERMINAL = {"success", "error", "cancelled", "interrupted"}



class RunManager:
    """Single-process bounded task runner; SQLite persists history, not live credentials."""
    def __init__(self, database: Database, provider: Provider, settings: Settings):
        self.db, self.provider, self.settings = database, provider, settings
        self.tasks: dict[str, asyncio.Task] = {}
        self.slots = asyncio.Semaphore(settings.max_concurrent_runs)
        self.admission = asyncio.Lock()
        self.event_lock = asyncio.Lock()

    async def recover(self):
        async with self.db.sessions() as session:
            rows = (await session.scalars(select(Run).where(Run.status.in_(["queued", "running"])))).all()
        for row in rows:
            await self.emit(row.id, "run_interrupted", status="interrupted", error="服务重启，本次运行已中断")

    async def emit(self, run_id: str, kind: str, *, status=None, **payload):
        async with self.event_lock:
            await self._emit(run_id, kind, status=status, **payload)

    async def _emit(self, run_id: str, kind: str, *, status=None, **payload):
        async with self.db.sessions() as session:
            row = await session.get(Run, run_id)
            if row is None or row.status in TERMINAL:
                return
            sequence = (await session.scalar(select(func.max(RunEvent.sequence))
                                              .where(RunEvent.run_id == run_id)) or 0) + 1
            event = {"sequence": sequence, "type": kind, "time": now(), **payload}
            session.add(RunEvent(run_id=run_id, sequence=sequence, payload=event))
            if status:
                row.status = status
                if status in TERMINAL:
                    row.finished_at = now()
                    row.error = payload.get("error")
            await session.commit()

    def preflight(self, graph: Graph):
        for node in graph.nodes:
            params = node.data.params
            connected = {edge.targetHandle for edge in graph.edges if edge.target == node.id}
            if node.type == "image-upload" and not params.image:
                raise ProviderError("请先为上传节点选择图片")
            if node.type == "text-input" and not params.text.strip():
                raise ProviderError("请先为文本输入节点填写内容")
            if node.type == "variable-set":
                if not params.variables:
                    raise ProviderError("请先为变量设置节点添加变量")
                if any(not item.name or not item.value.strip() for item in params.variables):
                    raise ProviderError("请先为变量设置节点填写变量名和变量值")
            if node.type in ("llm", "image-gen"):
                self.provider.connection(params)
                prompt_port = "text" if node.type == "llm" else "prompt"
                if not params.prompt.strip() and prompt_port not in connected:
                    raise ProviderError("模型节点缺少提示词或上游文本连接")
            if node.type == "image-gen" and "image2" in connected and "image" not in connected:
                raise ProviderError("使用参考图 2 时，请同时连接参考图 1")
            if node.type == "output-gallery" and "images" not in connected:
                raise ProviderError("输出画廊尚未连接图片组")

    async def submit(self, graph: Graph, workflow_id: str | None) -> str:
        self.preflight(graph)
        async with self.admission:
            if len(self.tasks) >= self.settings.max_pending_runs:
                raise OverflowError("运行队列已满，请稍后重试")
            async with self.db.sessions() as session:
                row = Run(graph=Graph(nodes=graph.nodes, edges=graph.edges).public_dump(), workflow_id=workflow_id)
                session.add(row)
                await session.commit()
            task = asyncio.create_task(self.worker(row.id, graph), name=f"flowmuse-run-{row.id}")
            self.tasks[row.id] = task
            task.add_done_callback(lambda finished: self.completed(row.id, finished))
            return row.id

    def completed(self, run_id: str, task: asyncio.Task):
        self.tasks.pop(run_id, None)
        if not task.cancelled():
            # Retrieve unexpected infrastructure exceptions without logging sensitive context.
            task.exception()

    async def worker(self, run_id: str, graph: Graph):
        try:
            async with self.slots:
                await self.emit(run_id, "run_started", status="running")
                await asyncio.wait_for(self.execute(run_id, graph), timeout=self.settings.run_timeout)
        except asyncio.CancelledError:
            # Cancellation endpoint/shutdown owns the final transition, including tasks not yet started.
            raise
        except asyncio.TimeoutError:
            await self.emit(run_id, "run_error", status="error", error="运行超过时间预算，已停止")
        except Exception:  # noqa: BLE001 - Task boundary must persist a safe terminal state.
            await self.emit(run_id, "run_error", status="error", error="运行失败，请检查服务状态")

    async def execute(self, run_id: str, graph: Graph):
        results = {}
        for node in graph.ordered_nodes():
            await self.emit(run_id, "node_started", nodeId=node.id)
            inputs = {}
            for edge in graph.edges:
                if edge.target == node.id:
                    result = results[edge.source]
                    if edge.sourceHandle == "text":
                        inputs[edge.targetHandle] = result.get("text", "")
                    elif edge.sourceHandle == "variables":
                        inputs[edge.targetHandle] = result.get("variables", {})
                    else:
                        inputs[edge.targetHandle] = result.get("images", [])
            try:
                result = await self.execute_node(node, inputs)
            except (ProviderError, TemplateError, ValueError) as error:
                message = str(error) if isinstance(error, (ProviderError, TemplateError)) else "节点输入无效"
                await self.emit(run_id, "node_error", nodeId=node.id, error=message)
                await self.emit(run_id, "run_error", status="error", error=message)
                return
            results[node.id] = result
            await self.emit(run_id, "node_success", nodeId=node.id, result=result)
        await self.emit(run_id, "run_success", status="success")

    async def execute_node(self, node: Node, inputs: dict) -> dict:
        params = node.data.params
        image = (inputs.get("image") or [None])[0]
        if node.type == "image-upload":
            return {"images": [params.image]}
        if node.type == "text-input":
            if not params.text.strip():
                raise ProviderError("请先为文本输入节点填写内容")
            return {"text": params.text}
        if node.type == "variable-set":
            if not params.variables or any(not item.name or not item.value.strip() for item in params.variables):
                raise ProviderError("请先为变量设置节点填写变量名和变量值")
            own = {item.name: item.value for item in params.variables}
            return {"variables": merge_variables(inputs.get("variables", {}), own)}
        if node.type == "llm":
            upstream = inputs.get("text", "")
            prompt = resolve_template(params.prompt, upstream, inputs.get("variables")) or upstream
            return await self.provider.text(params, prompt, image)
        if node.type == "image-gen":
            upstream = inputs.get("prompt", "").strip()
            # Preserve the existing UI contract: connected text takes precedence.
            if upstream and "variables" not in inputs:
                prompt = upstream
            else:
                prompt = resolve_template(upstream or params.prompt, inputs.get("text", ""), inputs.get("variables"))
            if not prompt:
                raise ProviderError("缺少提示词")
            image2 = (inputs.get("image2") or [None])[0]
            return await self.provider.images(params, prompt, image, image2)
        images = inputs.get("images", [])
        if not images:
            raise ProviderError("未接收到任何图片")
        return {"images": images}

    async def cancel(self, run_id: str, interrupted=False):
        task = self.tasks.get(run_id)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.emit(run_id, "run_interrupted" if interrupted else "run_cancelled",
                        status="interrupted" if interrupted else "cancelled",
                        error="服务停止，本次运行已中断" if interrupted else "运行已取消")

    async def close(self):
        await asyncio.gather(*(self.cancel(run_id, interrupted=True) for run_id in list(self.tasks)))


