<script setup lang="ts">
import { useRunStore } from '@/stores/runStore'
import WorkflowBar from '@/components/layout/WorkflowBar.vue'
import TopBar from '@/components/layout/TopBar.vue'
import SidebarLeft from '@/components/layout/SidebarLeft.vue'
import RunPanel from '@/components/layout/RunPanel.vue'
import CanvasView from '@/components/canvas/CanvasView.vue'
const run = useRunStore()
</script>

<template>
  <div class="flex h-screen flex-col overflow-hidden bg-canvas text-text">
    <TopBar />
    <WorkflowBar />
    <div class="flex min-h-0 flex-1">
      <SidebarLeft />
      <main class="relative min-w-0 flex-1" :inert="run.running">
        <CanvasView />
      </main>
      <RunPanel />
    </div>
  </div>
</template>


