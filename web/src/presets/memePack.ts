import { Sticker } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

/** 表情包：上传图片 → LLM 设计 9 个神态 → 生图（×9）→ 九宫格输出 */
export const memePack: PresetDef = {
  id: 'meme-pack',
  name: '表情包',
  description: '一个角色生成九宫格表情包',
  icon: Sticker,
  accent: '#ec4899',
  build: () => ({
    nodes: [
      makeNode('p-upload', 'image-upload', { x: 0, y: 220 }),
      makeNode('p-llm', 'llm', { x: 380, y: 0 }, {
        system: '你是表情包策划，擅长为角色设计一组夸张有趣的神态动作。',
        prompt:
          '根据参考图中的角色，设计 9 个适合做表情包的神态 / 动作（如开心、委屈、震惊、无语、加油、暗中观察……），用编号列表逐条输出，每条不超过 12 个字。',
      }),
      makeNode('p-gen', 'image-gen', { x: 760, y: 120 }, {
        prompt: '把参考图角色画成 Q 版表情包贴纸：{{text}}。纯白背景、粗描边、扁平卡通风格、表情夸张',
        count: 9,
        size: '1024x1024',
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
