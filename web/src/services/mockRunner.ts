import type { FlowEdge, FlowNode, NodeResult } from '@/types/flow'
import { resolveTemplate } from '@/utils/template'
import { hashString, placeholderImage } from '@/services/placeholder'

export interface RunnerHooks {
  onNodeStart: (node: FlowNode) => void
  onNodeSuccess: (node: FlowNode, result: NodeResult) => void
  onNodeError: (node: FlowNode, error: string) => void
  log: (level: 'info' | 'success' | 'error', label: string, message: string) => void
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))
const jitter = (base: number) => base + Math.round(Math.random() * 500)

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

interface PortValue {
  text?: string
  image?: string
  images?: string[]
}

/** 拓扑排序（Kahn），检测到环时抛错 */
function topoSort(nodes: FlowNode[], edges: FlowEdge[]): FlowNode[] {
  const indegree = new Map<string, number>()
  const outgoing = new Map<string, string[]>()
  for (const node of nodes) {
    indegree.set(node.id, 0)
    outgoing.set(node.id, [])
  }
  for (const edge of edges) {
    if (!indegree.has(edge.source) || !indegree.has(edge.target)) continue
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1)
    outgoing.get(edge.source)?.push(edge.target)
  }

  const byId = new Map(nodes.map((n) => [n.id, n]))
  const queue = nodes.filter((n) => indegree.get(n.id) === 0).map((n) => n.id)
  const order: FlowNode[] = []

  while (queue.length > 0) {
    const id = queue.shift() as string
    const node = byId.get(id)
    if (node) order.push(node)
    for (const next of outgoing.get(id) ?? []) {
      const degree = (indegree.get(next) ?? 0) - 1
      indegree.set(next, degree)
      if (degree === 0) queue.push(next)
    }
  }

  if (order.length !== nodes.length) {
    throw new Error('画布中存在循环连线，无法执行')
  }
  return order
}

/** 收集某个节点各输入口拿到的上游产物 */
function collectInputs(node: FlowNode, edges: FlowEdge[], results: Map<string, NodeResult>): Record<string, PortValue> {
  const inputs: Record<string, PortValue> = {}
  for (const edge of edges) {
    if (edge.target !== node.id || !edge.targetHandle) continue
    const upstream = results.get(edge.source)
    if (!upstream) continue
    switch (edge.targetHandle) {
      case 'text':
      case 'prompt':
        inputs[edge.targetHandle] = { text: upstream.text ?? '' }
        break
      case 'image':
        inputs.image = { image: upstream.images?.[0] }
        break
      case 'images':
        inputs.images = { images: upstream.images ?? [] }
        break
      default:
        break
    }
  }
  return inputs
}

function parseSize(size: string): [number, number] {
  const match = /^(\d+)x(\d+)$/.exec(size)
  if (!match) return [512, 512]
  return [Number(match[1]) / 2, Number(match[2]) / 2]
}

async function executeNode(node: FlowNode, inputs: Record<string, PortValue>): Promise<NodeResult> {
  const params = node.data.params

  switch (node.type) {
    case 'image-upload': {
      const image = typeof params.image === 'string' ? params.image : ''
      if (!image) throw new Error('请先选择要上传的图片')
      await sleep(jitter(300))
      return { images: [image] }
    }

    case 'llm': {
      const prompt = resolveTemplate(params.prompt, { text: inputs.text?.text ?? '' }).trim()
      await sleep(jitter(900))
      const lines = [
        `【Mock LLM · ${String(params.model || '未配置模型')}】`,
        prompt ? `提示词：${prompt}` : '（未填写提示词）',
        inputs.image?.image ? '（已接收参考图 1 张）' : '',
      ].filter(Boolean)
      return { text: lines.join('\n') }
    }

    case 'image-gen': {
      const upstream = inputs.prompt?.text?.trim()
      const local = resolveTemplate(params.prompt, { text: inputs.prompt?.text ?? '' }).trim()
      const prompt = upstream || local
      if (!prompt) throw new Error('缺少提示词：请连接上游文本，或在本节点填写提示词')
      const count = clamp(Number(params.count) || 1, 1, 9)
      const [width, height] = parseSize(String(params.size || '1024x1024'))
      await sleep(jitter(1000) + count * 150)
      const baseSeed = hashString(prompt) % 997
      const images = Array.from({ length: count }, (_, i) =>
        placeholderImage({ text: prompt, seed: baseSeed + i + 1, width, height }),
      )
      return { text: prompt, images }
    }

    case 'output-gallery': {
      const images = inputs.images?.images ?? []
      if (images.length === 0) throw new Error('未接收到任何图片')
      await sleep(jitter(200))
      return { images }
    }

    default:
      throw new Error(`未知节点类型：${String(node.type)}`)
  }
}

/**
 * Mock 执行引擎：按拓扑序逐个“运行”节点，产出假数据。
 * 后续接后端时，只需把这个实现换成调用 /api/runs，hooks 接口保持不变。
 */
export async function runFlow(nodes: FlowNode[], edges: FlowEdge[], hooks: RunnerHooks): Promise<boolean> {
  if (nodes.length === 0) {
    hooks.log('error', '运行', '画布为空，请先添加节点或载入玩法模板')
    return false
  }

  let order: FlowNode[]
  try {
    order = topoSort(nodes, edges)
  } catch (error) {
    hooks.log('error', '运行', error instanceof Error ? error.message : String(error))
    return false
  }

  hooks.log('info', '运行', `开始执行，共 ${order.length} 个节点（Mock 引擎，不请求真实接口）`)
  const results = new Map<string, NodeResult>()

  for (const node of order) {
    hooks.onNodeStart(node)
    try {
      const inputs = collectInputs(node, edges, results)
      const result = await executeNode(node, inputs)
      results.set(node.id, result)
      hooks.onNodeSuccess(node, result)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      hooks.onNodeError(node, message)
      hooks.log('error', node.data.label, `节点失败，已中止本次运行：${message}`)
      return false
    }
  }

  hooks.log('success', '运行', '全部节点执行完成')
  return true
}
