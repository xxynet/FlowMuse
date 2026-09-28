import { ref } from 'vue'
import { defineStore } from 'pinia'

export type LogLevel = 'info' | 'success' | 'error'

export interface RunLog {
  id: number
  time: string
  level: LogLevel
  label: string
  message: string
}

let logSeq = 0

export const useRunStore = defineStore('run', () => {
  const running = ref(false)
  const activeRunId = ref('')
  const logs = ref<RunLog[]>([])

  function log(level: LogLevel, label: string, message: string) {
    logSeq += 1
    logs.value.push({
      id: logSeq,
      time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      level,
      label,
      message,
    })
  }

  function reset() {
    logs.value = []
  }

  return { running, activeRunId, logs, log, reset }
})

