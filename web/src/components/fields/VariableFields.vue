<script setup lang="ts">
import { computed } from 'vue'
import { Plus, X } from 'lucide-vue-next'
import type { VariableBinding } from '@/types/flow'

const props = defineProps<{ modelValue: unknown }>()
const emit = defineEmits<{ 'update:modelValue': [value: VariableBinding[]] }>()
const bindings = computed<VariableBinding[]>(() => Array.isArray(props.modelValue) ? props.modelValue : [])

function update(index: number, key: keyof VariableBinding, event: Event) {
  const value = (event.target as HTMLInputElement).value
  emit('update:modelValue', bindings.value.map((item, i) => i === index ? { ...item, [key]: value } : { ...item }))
}
function add() {
  if (bindings.value.length >= 50) return
  emit('update:modelValue', [...bindings.value.map((item) => ({ ...item })), { name: '', value: '' }])
}
function remove(index: number) {
  emit('update:modelValue', bindings.value.filter((_, i) => i !== index).map((item) => ({ ...item })))
}
</script>

<template>
  <div class="nodrag nowheel space-y-2" @keydown.stop>
    <div v-for="(binding, index) in bindings" :key="index" class="space-y-1.5 rounded-lg border border-border p-2">
      <div class="flex items-center gap-1">
        <input
          class="fm-input min-w-0 flex-1"
          :value="binding.name"
          :aria-label="'变量 ' + (index + 1) + ' 名称'"
          placeholder="变量名，例如 story、风格"
          maxlength="64"
          @input="update(index, 'name', $event)"
        />
        <button type="button" class="fm-icon-btn shrink-0" :aria-label="'删除变量 ' + (index + 1)" @click="remove(index)">
          <X :size="12" />
        </button>
      </div>
      <textarea
        class="fm-input resize-y"
        :value="binding.value"
        :aria-label="'变量 ' + (index + 1) + ' 值'"
        placeholder="输入变量内容…"
        rows="4"
        maxlength="32000"
        @input="update(index, 'value', $event)"
      />
    </div>
    <button type="button" class="fm-btn-ghost w-full justify-center" :disabled="bindings.length >= 50" @click="add">
      <Plus :size="13" />添加变量
    </button>
  </div>
</template>
