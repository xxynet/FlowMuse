<script setup lang="ts">
import { ref } from 'vue'
import { Check, Palette } from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'

const { themes, current, setTheme } = useTheme()
const open = ref(false)

function onSelect(id: string) {
  setTheme(id)
  open.value = false
}
</script>

<template>
  <div class="relative">
    <button class="fm-btn-ghost" @click="open = !open">
      <Palette :size="15" />
      主题
    </button>
    <div v-if="open" class="fixed inset-0 z-30" @click="open = false" />
    <div v-if="open" class="fm-menu">
      <button v-for="t in themes" :key="t.id" class="fm-menu-item" @click="onSelect(t.id)">
        <span class="h-3.5 w-3.5 rounded-full border border-black/10" :style="{ backgroundColor: t.swatch }" />
        <span class="flex-1 text-left">{{ t.label }}</span>
        <Check v-if="t.id === current" :size="14" class="text-primary" />
      </button>
    </div>
  </div>
</template>
