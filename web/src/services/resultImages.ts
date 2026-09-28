import type { FlowNode } from '../types/flow.ts'

/** Count each generated image once, excluding reference uploads and gallery mirrors. */
export function generatedImages(nodes: FlowNode[]) {
  return nodes
    .filter((node) => node.type === 'image-gen' && node.data.status === 'success')
    .flatMap((node) => (node.data.result?.images ?? []).map((src, index) => ({
      key: `${node.id}-${index}`,
      src,
      downloadUrl: node.data.result?.downloadUrls?.[index],
      label: node.data.label,
    })))
}

/** Fetch to a Blob so clicking never navigates the workflow page, even on failure. */
export async function downloadImage(source: string, name: string, downloadUrl?: string): Promise<void> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 65000)
  try {
    const response = await fetch(downloadUrl || source, {
      signal: controller.signal, cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer',
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: unknown }
      throw new Error(typeof body.detail === 'string' ? body.detail : `下载失败（HTTP ${response.status}）`)
    }
    const blob = await response.blob()
    const extensions: Record<string, string> = {
      'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif', 'image/svg+xml': 'svg',
    }
    const extension = extensions[blob.type.split(';')[0] ?? '']
    if (!extension || !blob.size) throw new Error('下载地址未返回有效图片')
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${name.replace(/[^a-zA-Z0-9_-]/g, '_')}.${extension}`
    document.body.appendChild(anchor)
    try { anchor.click() }
    finally {
      anchor.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('下载图片超时，请稍后重试')
    if (error instanceof TypeError) throw new Error('无法下载图片，请检查网络或图片链接是否已失效')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
