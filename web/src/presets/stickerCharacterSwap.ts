import { UserRoundPen } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

export const stickerCharacterSwap: PresetDef = {
  id: 'sticker-character-swap',
  name: '表情包人物替换',
  description: '保留表情、文字与排版，换成指定角色',
  icon: UserRoundPen,
  accent: '#f97316',
  instructions: [
    '「原表情包」上传要修改的单张表情包或整套拼图。',
    '「目标人物」上传要替换进去的人物或角色，两张图片都需要选择。',
    '配置支持多图编辑的模型后运行；可修改提示词指定只替换其中一个人物。',
  ],
  build: () => {
    const original = makeNode('p-original', 'image-upload', { x: 0, y: 0 })
    original.data.label = '原表情包 · 参考图 1'
    const character = makeNode('p-character', 'image-upload', { x: 0, y: 350 })
    character.data.label = '目标人物 · 参考图 2'
    return {
      nodes: [
        original,
        character,
        makeNode('p-gen', 'image-gen', { x: 420, y: 0 }, {
          prompt: [
            '这是一次表情包人物替换编辑。参考图 1 是需要编辑的原表情包，参考图 2 是目标人物的身份参考。',
            '将图 1 中的主要角色替换为图 2 的人物，保留图 2 的脸型、发型、发色和标志性外观，使其可辨认。',
            '按图 1 的画风重新绘制目标人物，不把图 2 整张照片或背景粘贴进去。',
            '严格保留图 1 每个角色原有的表情、视线、姿势、动作、道具关系和情绪强度。',
            '保留图 1 的背景、文字内容、字体、气泡、边框、构图与排版，不增删文字，不新增无关元素。',
            '如果图 1 是多格表情包，对每一格执行同样替换，保持格数、顺序和统一的人物身份。',
            '只输出编辑后的完整表情包，画面比例按生图节点的尺寸设置。',
          ].join('\n'),
          count: 1,
        }),
        makeNode('p-output', 'output-gallery', { x: 840, y: 180 }),
      ],
      edges: [
        makeEdge('p-original', 'image', 'p-gen', 'image'),
        makeEdge('p-character', 'image', 'p-gen', 'image2'),
        makeEdge('p-gen', 'images', 'p-output', 'images'),
      ],
    }
  },
}
