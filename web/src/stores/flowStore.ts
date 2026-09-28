import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { FlowEdge, FlowNode, NodeKind, NodeResult, NodeRunStatus, PresetDef } from '@/types/flow'
import { defaultParams, nodeRegistry } from '@/registry/nodeRegistry'

let nodeSeq = 0

export const useFlowStore = defineStore('flow', () => {
  const workflowId = ref('')
  const workflowName = ref('未命名工作流')
  const nodes = ref<FlowNode[]>([])
  const edges = ref<FlowEdge[]>([])
  /** 画布被整体替换（载入玩法 / 清空）时自增，画布监听它来做 fitView */
  const canvasVersion = ref(0)

  const nodeCount = computed(() => nodes.value.length)

  function addNode(type: NodeKind, position?: { x: number; y: number }): string {
    const schema = nodeRegistry[type]
    nodeSeq += 1
    const id = `node-${crypto.randomUUID()}`
    nodes.value.push({
      id,
      type,
      position: position ?? { x: 120 + (nodeSeq % 6) * 48, y: 100 + (nodeSeq % 6) * 48 },
      data: {
        label: schema.label,
        params: defaultParams(schema.fields),
        status: 'idle',
      },
    })
    return id
  }

  function removeNode(id: string) {
    nodes.value = nodes.value.filter((n) => n.id !== id)
    edges.value = edges.value.filter((e) => e.source !== id && e.target !== id)
  }

  function updateParam(id: string, key: string, value: unknown) {
    const node = nodes.value.find((n) => n.id === id)
    if (node) node.data.params[key] = value
  }

  function setStatus(id: string, status: NodeRunStatus, error?: string) {
    const node = nodes.value.find((n) => n.id === id)
    if (!node) return
    node.data.status = status
    node.data.error = error
  }

  function setResult(id: string, result?: NodeResult) {
    const node = nodes.value.find((n) => n.id === id)
    if (node) node.data.result = result
  }

  function resetRunState() {
    for (const node of nodes.value) {
      node.data.status = 'idle'
      node.data.error = undefined
      node.data.result = undefined
    }
  }

  function loadPreset(preset: PresetDef) {
    workflowId.value = ''
    workflowName.value = preset.name
    const graph = preset.build()
    nodes.value = graph.nodes
    edges.value = graph.edges
    canvasVersion.value += 1
  }

  function loadWorkflow(saved: { id: string; name: string; nodes: FlowNode[]; edges: FlowEdge[] }) {
    workflowId.value = saved.id
    workflowName.value = saved.name
    nodes.value = saved.nodes
    edges.value = saved.edges
    resetRunState()
    canvasVersion.value += 1
  }

  function clearCanvas() {
    workflowId.value = ''
    workflowName.value = '未命名工作流'
    nodes.value = []
    edges.value = []
    canvasVersion.value += 1
  }

  return {
    workflowId,
    workflowName,
    loadWorkflow,
    nodes,
    edges,
    canvasVersion,
    nodeCount,
    addNode,
    removeNode,
    updateParam,
    setStatus,
    setResult,
    resetRunState,
    loadPreset,
    clearCanvas,
  }
})

