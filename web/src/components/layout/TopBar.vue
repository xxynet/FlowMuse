<script setup lang="ts">
import { Loader2, Play, RotateCcw, Trash2, Workflow } from 'lucide-vue-next'
import { useFlowStore } from '@/stores/flowStore'
import { useRunStore } from '@/stores/runStore'
import { useRunner } from '@/composables/useRunner'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'

const flow = useFlowStore()
const run = useRunStore()
const { runAll, cancel } = useRunner()

function onResetState() {
  flow.resetRunState()
  run.log('info', '运行', '已重置所有节点状态')
}

function onClear() {
  flow.clearCanvas()
  run.reset()
}
</script>

<template>
  <header class="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-4">
    <div class="flex items-center gap-2.5">
      <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-fg">
        <Workflow :size="18" />
      </span>
      <div class="leading-tight">
        <p class="text-[15px] font-bold tracking-wide">FlowMuse</p>
        <p class="text-[11px] text-text-muted">缪斯流 · 图片玩法工作流</p>
      </div>
    </div>

    <div class="ml-auto flex items-center gap-1.5">
      <ThemeSwitcher />
      <span class="mx-1 h-5 w-px bg-border" />
      <button class="fm-btn-ghost" :disabled="run.running" @click="onResetState">
        <RotateCcw :size="15" />
        重置状态
      </button>
      <button class="fm-btn-ghost" :disabled="run.running" @click="onClear">
        <Trash2 :size="15" />
        清空画布
      </button>
      <button v-if="run.running" class="fm-btn-ghost" :disabled="!run.activeRunId" @click="cancel">取消运行</button>
      <button class="fm-btn-primary" :disabled="run.running || !flow.nodeCount" @click="runAll">
        <Loader2 v-if="run.running" :size="15" class="animate-spin" />
        <Play v-else :size="15" />
        {{ run.running ? '运行中…' : '运行' }}
      </button>
    </div>
  </header>
</template>

