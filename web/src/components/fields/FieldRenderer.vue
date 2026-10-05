<script setup lang="ts">
import { X } from 'lucide-vue-next'
import type { FieldSchema } from '@/types/flow'
import VariableFields from '@/components/fields/VariableFields.vue'

/**
 * 按字段 schema 渲染对应的表单控件。
 * nodrag / nowheel / @keydown.stop 是为了让输入操作不被画布劫持。
 */
defineProps<{ field: FieldSchema; modelValue: unknown }>()
const emit = defineEmits<{ 'update:modelValue': [value: unknown] }>()

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

function onNumber(event: Event) {
  const value = (event.target as HTMLInputElement).valueAsNumber
  emit('update:modelValue', Number.isNaN(value) ? '' : value)
}

function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => emit('update:modelValue', String(reader.result))
  reader.readAsDataURL(file)
  input.value = ''
}
</script>

<template>
  <div v-if="field.type === 'variables'" class="block">
    <span class="fm-field-label">{{ field.label }}</span>
    <VariableFields :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" />
    <p v-if="field.hint" class="mt-1 text-[11px] leading-4 text-text-muted">{{ field.hint }}</p>
  </div>
  <label v-else class="block">
    <span class="fm-field-label">{{ field.label }}</span>

    <input
      v-if="field.type === 'text'"
      class="fm-input nodrag"
      type="text"
      :value="String(modelValue ?? '')"
      :placeholder="field.placeholder"
      @input="onInput"
      @keydown.stop
    />

    <input
      v-else-if="field.type === 'password'"
      class="fm-input nodrag"
      type="password"
      :value="String(modelValue ?? '')"
      :placeholder="field.placeholder"
      autocomplete="off"
      @input="onInput"
      @keydown.stop
    />

    <textarea
      v-else-if="field.type === 'textarea'"
      class="fm-input nodrag nowheel resize-y"
      :rows="field.rows ?? 3"
      :value="String(modelValue ?? '')"
      :placeholder="field.placeholder"
      @input="onInput"
      @keydown.stop
    />

    <input
      v-else-if="field.type === 'number'"
      class="fm-input nodrag"
      type="number"
      :value="modelValue === '' || modelValue === undefined ? '' : Number(modelValue)"
      :min="field.min"
      :max="field.max"
      :step="field.step"
      @input="onNumber"
      @keydown.stop
    />

    <select
      v-else-if="field.type === 'select'"
      class="fm-input nodrag"
      :value="String(modelValue ?? '')"
      @change="onInput"
      @keydown.stop
    >
      <option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>

    <div v-else-if="field.type === 'image'">
      <div v-if="modelValue" class="relative">
        <img
          :src="String(modelValue)"
          alt="已上传图片"
          class="h-28 w-full rounded-lg border border-border object-cover"
        />
        <button
          type="button"
          class="fm-icon-btn absolute right-1.5 top-1.5 !bg-black/50 !text-white hover:!bg-black/70"
          title="移除图片"
          @click.prevent="emit('update:modelValue', '')"
        >
          <X :size="12" />
        </button>
      </div>
      <label v-else class="fm-upload nodrag">
        <input type="file" accept="image/*" class="hidden" @change="onFile" />
        <span>点击选择图片</span>
      </label>
    </div>

    <p v-if="field.hint" class="mt-1 text-[11px] leading-4 text-text-muted">{{ field.hint }}</p>
  </label>
</template>
