<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { FolderOpen, RefreshCw, Save, Trash2 } from 'lucide-vue-next'
import { api, graphPayload, type SavedWorkflow, type WorkflowSummary } from '@/services/api'
import { useFlowStore } from '@/stores/flowStore'
import { useRunStore } from '@/stores/runStore'

const flow = useFlowStore()
const run = useRunStore()
const workflows = ref<WorkflowSummary[]>([])
const selected = ref('')
const busy = ref(false)

async function refresh() {
  workflows.value = await api<WorkflowSummary[]>('/workflows?limit=100')
}

async function perform(action: () => Promise<void>) {
  if (busy.value || run.running) return
  busy.value = true
  try { await action() }
  catch (error) { run.log('error', '工作流', error instanceof Error ? error.message : '操作失败') }
  finally { busy.value = false }
}

async function save() {
  await perform(async () => {
    const path = flow.workflowId ? `/workflows/${encodeURIComponent(flow.workflowId)}` : '/workflows'
    const saved = await api<SavedWorkflow>(path, {
      method: flow.workflowId ? 'PUT' : 'POST',
      body: JSON.stringify({ name: flow.workflowName, ...graphPayload(flow.nodes, flow.edges, false) }),
    })
    flow.workflowId = saved.id
    selected.value = saved.id
    await refresh()
    run.log('success', '工作流', '已保存；API Key 仅保留在当前页面')
  })
}

async function load() {
  if (!selected.value) return
  await perform(async () => {
    const saved = await api<SavedWorkflow>(`/workflows/${encodeURIComponent(selected.value)}`)
    flow.loadWorkflow(saved)
    run.reset()
    run.log('info', '工作流', '已载入，请配置节点 API Key 或使用服务端默认密钥')
  })
}

async function remove() {
  if (!selected.value || !window.confirm('确认删除所选工作流？运行历史会保留。')) return
  await perform(async () => {
    await api(`/workflows/${encodeURIComponent(selected.value)}`, { method: 'DELETE' })
    if (flow.workflowId === selected.value) flow.workflowId = ''
    selected.value = ''
    await refresh()
    run.log('success', '工作流', '已删除工作流')
  })
}

onMounted(() => perform(refresh))
</script>

<template>
  <div class="flex shrink-0 flex-wrap items-center gap-2 border-b border-border bg-surface px-4 py-2">
    <input v-model="flow.workflowName" class="fm-input !w-40" aria-label="工作流名称" maxlength="100" :disabled="busy || run.running" />
    <button class="fm-btn-ghost" :disabled="busy || run.running || !flow.workflowName.trim()" @click="save">
      <Save :size="14" />保存工作流
    </button>
    <select v-model="selected" class="fm-input !w-44" aria-label="已保存的工作流" :disabled="busy || run.running">
      <option value="">选择已保存工作流</option>
      <option v-for="item in workflows" :key="item.id" :value="item.id">{{ item.name }}</option>
    </select>
    <button class="fm-btn-ghost" :disabled="busy || run.running || !selected" @click="load"><FolderOpen :size="14" />载入</button>
    <button class="fm-icon-btn" title="刷新工作流" :disabled="busy || run.running" @click="perform(refresh)"><RefreshCw :size="14" /></button>
    <button class="fm-icon-btn" title="删除所选工作流" :disabled="busy || run.running || !selected" @click="remove"><Trash2 :size="14" /></button>
  </div>
</template>
