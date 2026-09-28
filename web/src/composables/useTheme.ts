import { computed, ref } from 'vue'

export interface ThemeDef {
  id: string
  label: string
  /** 主题选择器里展示的色板 */
  swatch: string
  /** 画布背景圆点颜色（与 CSS 令牌配套，供 Vue Flow Background 使用） */
  dot: string
}

/**
 * 主题登记表。
 * 新增主题：在 styles/main.css 加一组 :root[data-theme='xxx'] 变量后，来这里加一项即可。
 */
export const themes: ThemeDef[] = [
  { id: 'blue', label: '海洋蓝（默认）', swatch: '#2563eb', dot: '#c3d0e4' },
  { id: 'blue-dark', label: '深夜蓝', swatch: '#3b82f6', dot: '#22304f' },
  { id: 'violet', label: '鸢尾紫', swatch: '#7c3aed', dot: '#ddd3f5' },
  { id: 'emerald', label: '青翠绿', swatch: '#059669', dot: '#c4ddcf' },
]

const STORAGE_KEY = 'flowmuse:theme'

const currentTheme = ref<string>('blue')
let initialized = false

export function useTheme() {
  function applyTheme(id: string) {
    if (!themes.some((t) => t.id === id)) return
    currentTheme.value = id
    document.documentElement.dataset.theme = id
    localStorage.setItem(STORAGE_KEY, id)
  }

  function initTheme() {
    if (initialized) return
    initialized = true
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) applyTheme(saved)
    else document.documentElement.dataset.theme = currentTheme.value
  }

  const current = computed(() => currentTheme.value)

  return { themes, current, setTheme: applyTheme, initTheme }
}
