function escapeXml(text: string): string {
  const map: Record<string, string> = {
    '<': '&lt;',
    '>': '&gt;',
    '&': '&amp;',
    "'": '&apos;',
    '"': '&quot;',
  }
  return text.replace(/[<>&'"]/g, (c) => map[c] ?? c)
}

export interface PlaceholderOptions {
  text: string
  seed: number
  width?: number
  height?: number
}

/**
 * 生成一张本地 SVG 占位图（data URL），用于 Mock 生图结果。
 * 纯前端阶段不请求任何真实接口，也能完整演示工作流。
 */
export function placeholderImage({ text, seed, width = 512, height = 512 }: PlaceholderOptions): string {
  const hue = (seed * 47 + 205) % 360
  const hue2 = (hue + 46) % 360
  const label = escapeXml((text || 'FlowMuse').slice(0, 18))
  const r1 = Math.round(Math.min(width, height) * 0.22)
  const r2 = Math.round(Math.min(width, height) * 0.3)

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0" stop-color="hsl(${hue}, 72%, 58%)"/>` +
    `<stop offset="1" stop-color="hsl(${hue2}, 68%, 42%)"/>` +
    `</linearGradient></defs>` +
    `<rect width="${width}" height="${height}" fill="url(#g)"/>` +
    `<circle cx="${Math.round(width * 0.82)}" cy="${Math.round(height * 0.18)}" r="${r1}" fill="hsla(${hue2}, 80%, 88%, 0.28)"/>` +
    `<circle cx="${Math.round(width * 0.15)}" cy="${Math.round(height * 0.85)}" r="${r2}" fill="hsla(${hue}, 80%, 20%, 0.18)"/>` +
    `<text x="50%" y="46%" text-anchor="middle" font-family="system-ui, sans-serif" font-size="${Math.round(width / 14)}" font-weight="700" fill="rgba(255,255,255,0.95)">${label}</text>` +
    `<text x="50%" y="58%" text-anchor="middle" font-family="system-ui, sans-serif" font-size="${Math.round(width / 26)}" fill="rgba(255,255,255,0.75)">FlowMuse Mock #${seed}</text>` +
    `</svg>`

  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

/** 简单字符串 hash，让同一段提示词生成的占位图色调稳定 */
export function hashString(input: string): number {
  let hash = 0
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}
