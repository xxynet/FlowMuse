import { useFlowStore } from '@/stores/flowStore'
import { useRunStore } from '@/stores/runStore'
import { runFlow, cancelRun } from '@/services/apiRunner'

/** 将后端增量运行事件映射到画布状态。 */
export function useRunner() {
  const flow = useFlowStore()
  const run = useRunStore()

  async function runAll() {
    if (run.running) return
    flow.resetRunState()
    run.reset()
    run.running = true
    try {
      await runFlow(flow.nodes, flow.edges, {
        onNodeStart: (node) => {
          flow.setStatus(node.id, 'running')
          run.log('info', node.data.label, '开始执行')
        },
        onNodeSuccess: (node, result) => {
          flow.setStatus(node.id, 'success')
          flow.setResult(node.id, result)
          const extra = result.images?.length ? `，产出 ${result.images.length} 张图片` : ''
          run.log('success', node.data.label, `执行完成${extra}`)
        },
        onNodeError: (node, error) => {
          flow.setStatus(node.id, 'error', error)
        },
        log: (level, label, message) => run.log(level, label, message),
      }, (id) => { run.activeRunId = id }, flow.workflowId || undefined)
    } finally {
      run.running = false
      run.activeRunId = ''
    }
  }

  async function cancel() {
    if (!run.activeRunId) return
    try { await cancelRun(run.activeRunId) }
    catch (error) { run.log('error', '运行', error instanceof Error ? error.message : '取消失败') }
  }

  return { runAll, cancel }
}

