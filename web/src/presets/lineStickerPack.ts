import { Grid2X2 } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

export const lineStickerPack: PresetDef = {
  id: 'line-sticker-pack',
  name: 'LINE 风格表情包 4×4',
  description: '同一角色的 16 种表情，一张贴纸整图',
  icon: Grid2X2,
  accent: '#22c55e',
  instructions: [
    '在「角色参考图」上传人物、宠物或原创角色图片。',
    '可在生图提示词中修改 16 种表情；配置支持参考图编辑的模型后运行。',
    '输出是一张 4×4 整图，共 16 格；生成数量代表整图数量。点击结果可下载。',
  ],
  build: () => {
    const character = makeNode('p-character', 'image-upload', { x: 0, y: 180 })
    character.data.label = '角色参考图'
    return {
      nodes: [
        character,
        makeNode('p-gen', 'image-gen', { x: 400, y: 0 }, {
          prompt: [
            '根据参考图 1 的角色，生成一张 LINE 风格聊天表情贴纸整图。',
            '画面严格为 4 行 × 4 列的等尺寸网格，共 16 个独立贴纸，从左到右、从上到下依次为：',
            '第 1 行：开心大笑、委屈哭泣、震惊、无语；',
            '第 2 行：加油、感谢、抱歉、OK；',
            '第 3 行：生气、害羞、晚安、早安；',
            '第 4 行：暗中观察、比心、庆祝、累瘫。',
            '每格只出现同一个角色的一种表情动作，保留参考角色的脸型、发型或毛色、服饰和标志性特征。',
            '日系 Q 版、粗而圆润的描边、简洁扁平配色、夸张可爱的肢体语言，风格与比例在 16 格中一致。',
            '每个角色完整落在自己的格子内，四周留足空白，不跨格、不裁切、不重叠。统一纯白背景，不画网格线。',
            '不添加文字、序号、水印、品牌标志或界面元素。只输出这张 4×4 贴纸整图。',
          ].join('\n'),
          count: 1,
          size: '1024x1024',
        }),
        makeNode('p-output', 'output-gallery', { x: 820, y: 180 }),
      ],
      edges: [
        makeEdge('p-character', 'image', 'p-gen', 'image'),
        makeEdge('p-gen', 'images', 'p-output', 'images'),
      ],
    }
  },
}
