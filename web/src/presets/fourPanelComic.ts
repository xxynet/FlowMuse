import { PanelsTopLeft } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

export const fourPanelComic: PresetDef = {
  id: 'four-panel-comic',
  name: '角色四格漫画',
  description: '参考角色主演的 2×2 连贯小故事',
  icon: PanelsTopLeft,
  accent: '#eab308',
  instructions: [
    '在「主角参考图」上传角色图片。',
    '修改生图提示词中的四格剧情，配置支持参考图编辑的模型后运行。',
    '输出一张 2×2 四格漫画，按左上、右上、左下、右下阅读。',
  ],
  build: () => {
    const character = makeNode('p-character', 'image-upload', { x: 0, y: 180 })
    character.data.label = '主角参考图'
    return {
      nodes: [
        character,
        makeNode('p-gen', 'image-gen', { x: 400, y: 0 }, {
          prompt: [
            '以参考图 1 的角色为唯一主角，画一张 2 行 × 2 列的四格漫画，阅读顺序为左上、右上、左下、右下。',
            '剧情：第一格，主角认真准备做一份早餐；第二格，煎蛋时手忙脚乱，鸡蛋飞起来；',
            '第三格，主角以为失败而垂头丧气；第四格，鸡蛋恰好落成爱心形状，主角惊喜庆祝。',
            '四格中的主角脸型、发型、服饰、比例与配色保持一致，保留参考角色的标志性特征。',
            '温暖日系漫画画风，清晰分格，简洁场景，动作连贯，通过表情与动作讲清故事。',
            '不添加对白、标题、序号或水印。只输出这一张完整四格漫画。',
          ].join('\n'),
          count: 1,
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
