<script setup lang="ts">
import { computed } from 'vue'
import { Download, Eraser, ScrollText } from 'lucide-vue-next'
import { useFlowStore } from '@/stores/flowStore'
import { useRunStore } from '@/stores/runStore'
import { generatedImages } from '@/services/resultImages'
import { useImageDownload } from '@/composables/useImageDownload'
import type { LogLevel } from '@/stores/runStore'

const flow = useFlowStore()
const run = useRunStore()

const levelCls: Record<LogLevel, string> = {
  info: 'text-text-muted',
  success: 'text-success',
  error: 'text-danger',
}

const gallery = computed(() => generatedImages(flow.nodes))
const { download, pending } = useImageDownload()
</script>

<template>
  <aside class="flex w-72 shrink-0 flex-col border-l border-border bg-surface">
    <div class="flex h-11 shrink-0 items-center gap-2 border-b border-border px-3">
      <ScrollText :size="15" class="text-primary" />
      <span class="text-[13px] font-semibold">运行日志</span>
      <button class="fm-icon-btn ml-auto" title="清空日志" @click="run.reset()">
        <Eraser :size="14" />
      </button>
    </div>

    <div class="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3 font-mono text-[11px] leading-4">
      <p v-if="!run.logs.length" class="text-text-muted">暂无日志。载入玩法模板并点击「运行」试试。</p>
      <p v-for="log in run.logs" :key="log.id">
        <span class="text-text-muted">{{ log.time }}</span>
        <span :class="levelCls[log.level]"> [{{ log.label }}]</span>
        <span> {{ log.message }}</span>
      </p>
    </div>

    <div class="max-h-[42%] shrink-0 overflow-y-auto border-t border-border p-3">
      <p class="mb-2 text-[12px] font-semibold text-text-muted">生成结果（{{ gallery.length }}）</p>
      <div v-if="gallery.length" class="grid grid-cols-3 gap-1.5">
        <button
          v-for="item in gallery"
          :key="item.key"
          type="button"
          :disabled="pending.has(`flowmuse-${item.key}`)"
          @click="download(item.src, `flowmuse-${item.key}`, item.downloadUrl)"
          :title="`${item.label} · 点击下载`"
          class="group relative block overflow-hidden rounded-md border border-border disabled:opacity-50"
        >
          <img :src="item.src" :alt="item.label" class="aspect-square w-full object-cover" />
          <span
            class="absolute inset-0 flex items-center justify-center bg-black/45 opacity-0 transition group-hover:opacity-100"
          >
            <Download :size="16" class="text-white" />
          </span>
        </button>
      </div>
      <p v-else class="text-[11px] text-text-muted">运行后这里会汇总展示生成的图片。</p>
    </div>
  </aside>
</template>
