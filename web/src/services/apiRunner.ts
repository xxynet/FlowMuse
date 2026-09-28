import type { FlowEdge, FlowNode, NodeResult } from '@/types/flow'
import type { RunnerHooks } from '@/services/mockRunner'
import { api, graphPayload } from '@/services/api'

interface RunEvent {
  sequence: number
  type: string
  nodeId?: string
  result?: NodeResult
  error?: string
}

interface RunState {
  id: string
  status: 'queued' | 'running' | 'success' | 'error' | 'cancelled' | 'interrupted'
  error?: string
  events: RunEvent[]
  nextCursor: number
  hasMore: boolean
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export async function cancelRun(id: string): Promise<void> {
  await api(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST' })
}

export async function runFlow(
  nodes: FlowNode[], edges: FlowEdge[], hooks: RunnerHooks,
  onCreated: (id: string) => void, workflowId?: string,
): Promise<boolean> {
  const snapshot = graphPayload(nodes, edges)
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const active = new Set<string>()
  let runId: string | undefined
  try {
    const created = await api<{ id: string }>('/runs', {
      method: 'POST', body: JSON.stringify({ ...snapshot, workflowId }),
    })
    runId = created.id
    onCreated(runId)
    hooks.log('info', '运行', `已提交 ${nodes.length} 个节点`)
    let cursor = 0
    let failures = 0
    while (true) {
      let state: RunState
      try {
        state = await api<RunState>(`/runs/${encodeURIComponent(runId)}?after=${cursor}`)
        failures = 0
      } catch (error) {
        failures += 1
        if (failures >= 5) throw error
        await sleep(Math.min(failures * 1000, 5000))
        continue
      }
      for (const event of state.events) {
        const node = event.nodeId ? byId.get(event.nodeId) : undefined
        if (!node) continue
        if (event.type === 'node_started') {
          active.add(node.id)
          hooks.onNodeStart(node)
        } else if (event.type === 'node_success') {
          active.delete(node.id)
          hooks.onNodeSuccess(node, event.result ?? {})
        } else if (event.type === 'node_error') {
          active.delete(node.id)
          hooks.onNodeError(node, event.error ?? '节点执行失败')
        }
      }
      cursor = state.nextCursor
      if (state.hasMore) continue
      if (state.status !== 'queued' && state.status !== 'running') {
        const success = state.status === 'success'
        const message = success ? '全部节点执行完成' : state.error ?? '运行已停止'
        for (const id of active) hooks.onNodeError(byId.get(id)!, message)
        hooks.log(success ? 'success' : 'error', '运行', message)
        return success
      }
      await sleep(700)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '运行失败'
    for (const id of active) hooks.onNodeError(byId.get(id)!, message)
    hooks.log('error', '运行', message)
    if (runId) {
      try {
        await cancelRun(runId)
      } catch {
        hooks.log('error', '运行', `无法确认后端是否停止，请在 API 查询运行：${runId}`)
      }
    }
    return false
  }
}
