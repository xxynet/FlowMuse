import type { FlowEdge, FlowNode } from '@/types/flow'

export interface WorkflowSummary {
  id: string
  name: string
  updatedAt: string
}

export interface SavedWorkflow extends WorkflowSummary {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export function graphPayload(nodes: FlowNode[], edges: FlowEdge[], includeKeys = true) {
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: { ...node.position },
      data: {
        label: node.data.label,
        params: Object.fromEntries(Object.entries(node.data.params).filter(([key]) => includeKeys || key !== 'apiKey')),
      },
    })),
    edges: edges.map((edge) => ({
      id: edge.id, source: edge.source, target: edge.target,
      sourceHandle: edge.sourceHandle, targetHandle: edge.targetHandle,
      type: edge.type ?? 'smoothstep',
    })),
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)
  try {
    const response = await fetch(`/api${path}`, {
      ...options,
      signal: controller.signal,
      cache: 'no-store',
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: unknown }
      throw new Error(typeof body.detail === 'string' ? body.detail : `请求失败（HTTP ${response.status}）`)
    }
    return response.status === 204 ? undefined as T : await response.json() as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('后端请求超时')
    if (error instanceof TypeError) throw new Error('无法连接后端，请确认服务已启动')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

