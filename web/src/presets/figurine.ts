import { ToyBrick } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

/** 手办化：上传图片 → LLM 提炼人物特征 → 生图（手办提示词 + 参考图）→ 输出画廊 */
export const figurine: PresetDef = {
  id: 'figurine',
  name: '手办化',
  description: '照片一键变 1/7 比例手办产品图',
  icon: ToyBrick,
  accent: '#8b5cf6',
  build: () => ({
    nodes: [
      makeNode('p-upload', 'image-upload', { x: 0, y: 220 }),
      makeNode('p-llm', 'llm', { x: 380, y: 0 }, {
        system: '你是资深手办原型师，擅长把人物照片转写为手办生图提示词。',
        prompt:
          '观察参考图中的人物，输出一段用于生成「1/7 比例 PVC 手办」的详细提示词：包含脸型、发型、服装、姿势、底座与涂装质感，中文输出。',
      }),
      makeNode('p-gen', 'image-gen', { x: 760, y: 120 }, {
        prompt:
          '以参考图为原型制作精美手办：{{text}}。1/7 比例，PVC 涂装质感，圆形展示底座，摄影棚柔光，产品摄影',
      }),
      makeNode('p-output', 'output-gallery', { x: 1160, y: 240 }),
    ],
    edges: [
      makeEdge('p-upload', 'image', 'p-llm', 'image'),
      makeEdge('p-llm', 'text', 'p-gen', 'prompt'),
      makeEdge('p-upload', 'image', 'p-gen', 'image'),
      makeEdge('p-gen', 'images', 'p-output', 'images'),
    ],
  }),
}
