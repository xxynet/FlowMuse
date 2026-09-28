import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import '@/styles/main.css'

import App from './App.vue'
import { useTheme } from '@/composables/useTheme'
import { useFlowStore } from '@/stores/flowStore'

// 挂载前初始化主题，避免闪烁
useTheme().initTheme()

const pinia = createPinia()
createApp(App).use(pinia).mount('#app')

// 开发调试：便于在控制台检查画布状态
if (import.meta.env.DEV) {
  ;(window as unknown as { __flowStore: unknown }).__flowStore = useFlowStore(pinia)
}
