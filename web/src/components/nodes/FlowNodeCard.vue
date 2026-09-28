<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { CheckCircle2, CircleDashed, Loader2, X, XCircle } from 'lucide-vue-next'
import { nodeRegistry } from '@/registry/nodeRegistry'
import { useFlowStore } from '@/stores/flowStore'
import type { FlowNodeData, NodeKind } from '@/types/flow'
import FieldRenderer from '@/components/fields/FieldRenderer.vue'

/**
 * 通用节点卡片：所有节点类型共用，按注册表 schema 渲染端口与参数表单。
 * 头部 52px + 端口行每行 26px，连接点按同样节奏对齐（71px 起，每行 +26px）。
 */
const props = defineProps<{
  id: string
  type?: string
  data?: FlowNodeData
  selected?: boolean
}>()

const flow = useFlowStore()

const schema = computed(() => (props.type ? nodeRegistry[props.type as NodeKind] : undefined))
const status = computed(() => props.data?.status ?? 'idle')
const resultImages = computed(() => props.data?.result?.images ?? [])
const resultText = computed(() => props.data?.result?.text ?? '')
// 上传节点的图片已由参数表单预览，不再重复展示产物
const showResultImages = computed(() => resultImages.value.length > 0 && props.type !== 'image-upload')

const statusMeta = computed(() => {
  switch (status.value) {
    case 'running':
      return { label: '运行中', cls: 'text-primary', icon: Loader2, spin: true }
    case 'success':
      return { label: '完成', cls: 'text-success', icon: CheckCircle2, spin: false }
    case 'error':
      return { label: '失败', cls: 'text-danger', icon: XCircle, spin: false }
    default:
      return { label: '待运行', cls: 'text-text-muted', icon: CircleDashed, spin: false }
  }
})

const HANDLE_BASE_TOP = 71
const HANDLE_ROW_HEIGHT = 26
const handleTop = (index: number) => `${HANDLE_BASE_TOP + index * HANDLE_ROW_HEIGHT}px`

function setParam(key: string, value: unknown) {
  flow.updateParam(props.id, key, value)
}
</script>

<template>
  <div
    v-if="schema && data"
    class="fm-node group"
    :class="[`is-${status}`, { 'is-selected': selected }]"
    :style="{ '--node-accent': schema.accent }"
  >
    <Handle
      v-for="(port, i) in schema.inputs"
      :id="port.key"
      :key="`in-${port.key}`"
      type="target"
      :position="Position.Left"
      :style="{ top: handleTop(i), transform: 'translateY(-50%)' }"
    />
    <Handle
      v-for="(port, i) in schema.outputs"
      :id="port.key"
      :key="`out-${port.key}`"
      type="source"
      :position="Position.Right"
      :style="{ top: handleTop(i), transform: 'translateY(-50%)' }"
    />

    <button
      type="button"
      class="absolute -right-2 -top-2 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-danger text-white opacity-0 shadow transition group-hover:opacity-100"
      title="删除节点"
      @click="flow.removeNode(id)"
    >
      <X :size="11" />
    </button>

    <header class="fm-node-header">
      <span class="fm-node-icon">
        <component :is="schema.icon" :size="15" />
      </span>
      <div class="min-w-0 flex-1">
        <p class="truncate text-[13px] font-semibold leading-4">{{ data.label }}</p>
        <p class="truncate text-[11px] text-text-muted">{{ schema.description }}</p>
      </div>
      <span class="inline-flex shrink-0 items-center gap-1 text-[11px]" :class="statusMeta.cls">
        <component :is="statusMeta.icon" :size="13" :class="{ 'animate-spin': statusMeta.spin }" />
        {{ statusMeta.label }}
      </span>
    </header>

    <div v-if="schema.inputs.length || schema.outputs.length" class="flex justify-between px-3 pb-2 pt-1.5">
      <div>
        <p v-for="port in schema.inputs" :key="port.key" class="fm-port-label">◂ {{ port.label }}</p>
      </div>
      <div class="text-right">
        <p v-for="port in schema.outputs" :key="port.key" class="fm-port-label justify-end">{{ port.label }} ▸</p>
      </div>
    </div>

    <div v-if="schema.fields.length" class="space-y-2.5 border-t border-border px-3 py-2.5">
      <FieldRenderer
        v-for="field in schema.fields"
        :key="field.key"
        :field="field"
        :model-value="data.params[field.key]"
        @update:model-value="setParam(field.key, $event)"
      />
    </div>

    <div v-if="resultText && schema.outputs.some((p) => p.kind === 'text')" class="fm-result-text nodrag nowheel">{{ resultText }}</div>

    <div v-if="showResultImages" class="px-3 pb-3">
      <a
        v-if="resultImages.length === 1"
        :href="resultImages[0]"
        download="flowmuse-result.svg"
        title="点击下载"
        class="block"
      >
        <img :src="resultImages[0]" alt="生成结果" class="w-full rounded-lg border border-border" />
      </a>
      <div v-else class="grid grid-cols-3 gap-1.5">
        <a
          v-for="(img, i) in resultImages.slice(0, 9)"
          :key="i"
          :href="img"
          :download="`flowmuse-${id}-${i + 1}.svg`"
          title="点击下载"
          class="block overflow-hidden rounded-md border border-border"
        >
          <img :src="img" :alt="`结果 ${i + 1}`" class="aspect-square w-full object-cover" />
        </a>
      </div>
    </div>

    <p v-if="status === 'error' && data.error" class="fm-error-text nodrag">{{ data.error }}</p>
  </div>
</template>
