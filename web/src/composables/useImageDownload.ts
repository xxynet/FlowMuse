import { ref } from 'vue'
import { downloadImage } from '@/services/resultImages'
import { useRunStore } from '@/stores/runStore'

export function useImageDownload() {
  const pending = ref(new Set<string>())
  const run = useRunStore()

  async function download(source: string, name: string, downloadUrl?: string) {
    if (pending.value.has(name)) return
    pending.value.add(name)
    try { await downloadImage(source, name, downloadUrl) }
    catch (error) { run.log('error', '下载', error instanceof Error ? error.message : '图片下载失败') }
    finally { pending.value.delete(name) }
  }

  return { download, pending }
}
