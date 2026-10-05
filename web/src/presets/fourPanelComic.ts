import { PanelsTopLeft } from 'lucide-vue-next'
import type { PresetDef } from '@/types/flow'
import { makeEdge, makeNode } from '@/presets/utils'

export const fourPanelComic: PresetDef = {
  id: 'four-panel-comic',
  name: '角色四格漫画',
  description: '输入自己的剧情，参考角色主演四格漫画',
  icon: PanelsTopLeft,
  accent: '#eab308',
  instructions: [
    '在「主角参考图」上传角色图片。',
    '在「变量设置」节点填写「剧情」的值；也可添加风格等变量，并在生图提示词中用 {变量名} 或 {{ 变量名 }} 引用。',
    '配置生图模型后运行，输出按左上、右上、左下、右下阅读的 2×2 四格漫画。',
  ],
  build: () => {
    const character = makeNode('p-character', 'image-upload', { x: 0, y: 0 })
    character.data.label = '主角参考图'
    const story = makeNode('p-story', 'variable-set', { x: 0, y: 330 }, {
      variables: [{ name: '剧情', value: '' }],
    })
    return {
      nodes: [
        character,
        story,
        makeNode('p-gen', 'image-gen', { x: 420, y: 0 }, {
          prompt: [
            '以参考图 1 的角色为主角，画一张 2 行 × 2 列的四格漫画，阅读顺序为左上、右上、左下、右下。',
            '按照以下用户剧情绘制；如果是故事梗概，将其组织为连贯的四格；如果已逐格描述，遵循用户的顺序和事件。',
            '用户剧情：',
            '{{ 剧情 }}',
            '四格中的主角脸型、发型、服饰、比例与配色保持一致，保留参考角色的标志性特征。',
            '温暖日系漫画画风，清晰分格，简洁场景，动作连贯，通过表情与动作讲清故事。',
            '用户提供对白时使用对应对白，否则通过动作讲述。不添加额外标题、序号或水印，只输出完整四格漫画。',
          ].join('\n'),
          count: 1,
        }),
        makeNode('p-output', 'output-gallery', { x: 840, y: 180 }),
      ],
      edges: [
        makeEdge('p-character', 'image', 'p-gen', 'image'),
        makeEdge('p-story', 'variables', 'p-gen', 'variables'),
        makeEdge('p-gen', 'images', 'p-output', 'images'),
      ],
    }
  },
}
