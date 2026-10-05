<script setup lang="ts">
import { computed } from 'vue'
import { Plus } from 'lucide-vue-next'
import { presetList } from '@/presets'
import { nodeTypeList } from '@/registry/nodeRegistry'
import { useFlowStore } from '@/stores/flowStore'
import { useRunStore } from '@/stores/runStore'
import type { NodeKind, PresetDef } from '@/types/flow'

const flow = useFlowStore()
const run = useRunStore()
const activePreset = computed(() => presetList.find((preset) => preset.name === flow.workflowName))

function onDragStart(event: DragEvent, type: NodeKind) {
  event.dataTransfer?.setData('application/flowmuse', type)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function onPreset(preset: PresetDef) {
  if (run.running) return
  flow.loadPreset(preset)
  run.reset()
  run.log('info', '玩法', `已载入「${preset.name}」模板。${preset.instructions?.join(' ') ?? '上传图片并配置模型后点击「运行」'}`)
}
</script>

<template>
  <aside :inert="run.running" class="flex w-64 shrink-0 flex-col gap-5 overflow-y-auto border-r border-border bg-surface p-3">
    <section>
      <h3 class="fm-side-title">玩法模板</h3>
      <div class="space-y-2">
        <button v-for="preset in presetList" :key="preset.id" class="fm-preset-card" :class="{ '!border-primary !bg-primary-soft': activePreset?.id === preset.id }" :disabled="run.running" :aria-pressed="activePreset?.id === preset.id" @click="onPreset(preset)">
          <span class="fm-preset-icon" :style="{ '--node-accent': preset.accent }">
            <component :is="preset.icon" :size="16" />
          </span>
          <span class="min-w-0 flex-1 text-left">
            <span class="block text-[13px] font-medium">{{ preset.name }}</span>
            <span class="block text-[11px] leading-4 text-text-muted">{{ preset.description }}</span>
          </span>
        </button>
      </div>
    </section>

    <section v-if="activePreset?.instructions?.length" class="rounded-lg border border-border bg-surface-2 p-3">
      <h3 class="fm-side-title">使用步骤</h3>
      <ol class="list-decimal space-y-2 pl-4 text-[11px] leading-5 text-text-muted">
        <li v-for="step in activePreset.instructions" :key="step">{{ step }}</li>
      </ol>
    </section>

    <section>
      <h3 class="fm-side-title">节点 · 点击或拖入画布</h3>
      <div class="space-y-2">
        <div
          v-for="schema in nodeTypeList"
          :key="schema.type"
          class="fm-palette-item"
          draggable="true"
          @dragstart="onDragStart($event, schema.type)"
        >
          <span class="fm-preset-icon" :style="{ '--node-accent': schema.accent }">
            <component :is="schema.icon" :size="15" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-[13px] font-medium">{{ schema.label }}</span>
            <span class="block truncate text-[11px] text-text-muted">{{ schema.description }}</span>
          </span>
          <button class="fm-icon-btn" title="添加到画布" @click.stop="flow.addNode(schema.type)">
            <Plus :size="14" />
          </button>
        </div>
      </div>
    </section>
  </aside>
</template>


