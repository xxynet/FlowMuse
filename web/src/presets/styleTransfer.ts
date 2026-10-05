import { Palette } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

export const styleTransfer: PresetDef = {
  id: 'style-transfer',
  name: '参考图风格迁移',
  description: '保留原图内容，采用另一张图的画风',
  icon: Palette,
  accent: '#06b6d4',
  instructions: [
    '「内容原图」上传要重新绘制的照片或插画。',
    '「风格参考」上传喜欢的画风示例，两张图片都需要选择。',
    '配置支持多图编辑的模型；提示词中可调整对颜色、笔触和构图的保留要求。',
  ],
  build: () => {
    const original = makeNode('p-original', 'image-upload', { x: 0, y: 0 })
    original.data.label = '内容原图 · 参考图 1'
    const style = makeNode('p-style', 'image-upload', { x: 0, y: 350 })
    style.data.label = '风格参考 · 参考图 2'
    return {
      nodes: [
        original,
        style,
        makeNode('p-gen', 'image-gen', { x: 420, y: 0 }, {
          prompt: [
            '以参考图 1 为内容原图、参考图 2 为绘画风格参考，重新绘制图 1。',
            '保留图 1 的人物身份、主体数量、姿势、物体关系、场景和整体构图。',
            '仅从图 2 提取线条、笔触、材质表现、色彩倾向、光影处理和造型语言。',
            '不要将图 2 的人物身份、物体、文字或背景内容混入图 1，不做两张图的拼接。',
            '输出一张画风统一、细节完整的作品，不添加文字、水印或品牌标志。',
          ].join('\n'),
          count: 1,
        }),
        makeNode('p-output', 'output-gallery', { x: 840, y: 180 }),
      ],
      edges: [
        makeEdge('p-original', 'image', 'p-gen', 'image'),
        makeEdge('p-style', 'image', 'p-gen', 'image2'),
        makeEdge('p-gen', 'images', 'p-output', 'images'),
      ],
    }
  },
}
