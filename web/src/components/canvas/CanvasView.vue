<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { Panel, PanelPosition, VueFlow, useVueFlow, type Connection, type Edge, type Node } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import { useFlowStore } from '@/stores/flowStore'
import { nodeRegistry } from '@/registry/nodeRegistry'
import { useTheme } from '@/composables/useTheme'
import type { FlowEdge, FlowNode, NodeKind } from '@/types/flow'
import FlowNodeCard from '@/components/nodes/FlowNodeCard.vue'

const flow = useFlowStore()

// Vue Flow 的 Node.data 是可选的，且其 Node/Edge 类型会引起 ref 深解包爆炸，
// 统一在这里与业务类型（FlowNode / FlowEdge）做一次双向转换
const nodes = computed<Node[]>({
  get: () => flow.nodes,
  set: (value) => {
    flow.nodes = value as FlowNode[]
  },
})
const edges = computed<Edge[]>({
  get: () => flow.edges,
  set: (value) => {
    flow.edges = value as FlowEdge[]
  },
})
const { themes, current } = useTheme()

const dotColor = computed(() => themes.find((t) => t.id === current.value)?.dot ?? '#c3d0e4')

const vueFlow = useVueFlow()
const { onConnect, addEdges, screenToFlowCoordinate, fitView } = vueFlow

if (import.meta.env.DEV) {
  ;(window as unknown as { __vueFlow: unknown }).__vueFlow = vueFlow
}

onConnect((connection) => {
  addEdges({ ...connection, type: 'smoothstep' })
})

/** 连接校验：端口 kind 必须一致，且每个输入口只允许一条连线 */
function isValidConnection(connection: Connection): boolean {
  if (!connection.source || !connection.target || connection.source === connection.target) return false
  const sourceNode = nodes.value.find((n) => n.id === connection.source)
  const targetNode = nodes.value.find((n) => n.id === connection.target)
  if (!sourceNode?.type || !targetNode?.type) return false

  const sourceSchema = nodeRegistry[sourceNode.type as NodeKind]
  const targetSchema = nodeRegistry[targetNode.type as NodeKind]
  const output = sourceSchema?.outputs.find((p) => p.key === connection.sourceHandle)
  const input = targetSchema?.inputs.find((p) => p.key === connection.targetHandle)
  if (!output || !input || output.kind !== input.kind) return false

  // 输入口唯一性：排除正在校验的这条边自身（预设载入时 Vue Flow 会用它重验已有边）
  return !edges.value.some(
    (e) =>
      e.target === connection.target &&
      e.targetHandle === connection.targetHandle &&
      !(e.source === connection.source && e.sourceHandle === connection.sourceHandle),
  )
}

function onDrop(event: DragEvent) {
  const type = event.dataTransfer?.getData('application/flowmuse') as NodeKind | ''
  if (!type || !nodeRegistry[type]) return
  const position = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
  flow.addNode(type, { x: position.x - 145, y: position.y - 40 })
}

watch(
  () => flow.canvasVersion,
  async () => {
    await nextTick()
    fitView({ padding: 0.2, duration: 300 })
  },
)
</script>

<template>
  <VueFlow
    v-model:nodes="nodes"
    v-model:edges="edges"
    class="fm-canvas"
    fit-view-on-init
    :min-zoom="0.2"
    :max-zoom="1.6"
    :delete-key-code="['Backspace', 'Delete']"
    :is-valid-connection="isValidConnection"
    :connection-radius="28"
    @drop="onDrop"
    @dragover.prevent
  >
    <Background :pattern-color="dotColor" :gap="22" />
    <Controls />
    <MiniMap pannable zoomable />

    <template #node-image-upload="props"><FlowNodeCard v-bind="props" /></template>
    <template #node-text-input="props"><FlowNodeCard v-bind="props" /></template>
    <template #node-variable-set="props"><FlowNodeCard v-bind="props" /></template>
    <template #node-llm="props"><FlowNodeCard v-bind="props" /></template>
    <template #node-image-gen="props"><FlowNodeCard v-bind="props" /></template>
    <template #node-output-gallery="props"><FlowNodeCard v-bind="props" /></template>

    <Panel v-if="!nodes.length" :position="PanelPosition.TopCenter" class="pointer-events-none">
      <div class="mt-14 rounded-xl border border-dashed border-border-strong bg-surface/80 px-6 py-4 text-center">
        <p class="text-sm font-medium">从左侧拖入节点，或点击「玩法模板」一键开始</p>
        <p class="mt-1 text-xs text-text-muted">配置模型服务后，运行将调用真实接口</p>
      </div>
    </Panel>
  </VueFlow>
</template>

