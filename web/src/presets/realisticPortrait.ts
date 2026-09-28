import { UserRound } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

/** 真人化：上传图片 → 生图（写实人像提示词）→ 输出画廊 */
export const realisticPortrait: PresetDef = {
  id: 'realistic-portrait',
  name: '真人化',
  description: '照片 / 二次元形象转超写实真人摄影',
  icon: UserRound,
  accent: '#0ea5e9',
  build: () => ({
    nodes: [
      makeNode('p-upload', 'image-upload', { x: 0, y: 140 }),
      makeNode('p-gen', 'image-gen', { x: 400, y: 60 }, {
        prompt:
          '将参考图中的人物转化为超写实真人摄影风格：自然肤质与毛孔细节、真实光影、85mm 人像镜头、浅景深、影棚柔光、高清画质',
      }),
      makeNode('p-output', 'output-gallery', { x: 800, y: 160 }),
    ],
    edges: [
      makeEdge('p-upload', 'image', 'p-gen', 'image'),
      makeEdge('p-gen', 'images', 'p-output', 'images'),
    ],
  }),
}
