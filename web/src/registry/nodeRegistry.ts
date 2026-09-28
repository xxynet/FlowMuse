import { BrainCircuit, Images, ImageUp, Sparkles } from 'lucide-vue-next'
import type { FieldSchema, NodeKind, NodeTypeSchema } from '@/types/flow'

/**
 * 节点类型注册表：画布渲染、连接校验、参数表单、执行分发全部以此为准。
 * 新增节点类型 = 在这里登记一项 + （可选）在 FlowNodeCard 里加特殊渲染。
 */
export const nodeRegistry: Record<NodeKind, NodeTypeSchema> = {
  'image-upload': {
    type: 'image-upload',
    label: '上传图片',
    description: '从本地上传一张参考图',
    icon: ImageUp,
    accent: '#0ea5e9',
    inputs: [],
    outputs: [{ key: 'image', label: '图片', kind: 'image' }],
    fields: [{ key: 'image', label: '图片文件', type: 'image' }],
  },

  llm: {
    type: 'llm',
    label: 'LLM 节点',
    description: '调用大模型改写 / 生成提示词',
    icon: BrainCircuit,
    accent: '#8b5cf6',
    inputs: [
      { key: 'text', label: '文本', kind: 'text' },
      { key: 'image', label: '图片', kind: 'image' },
    ],
    outputs: [{ key: 'text', label: '文本', kind: 'text' }],
    fields: [
      { key: 'baseUrl', label: 'Base URL', type: 'text', placeholder: 'https://api.example.com/v1' },
      { key: 'apiKey', label: 'API Key', type: 'password', placeholder: '留空使用服务端默认密钥' },
      { key: 'model', label: '模型', type: 'text', default: 'gpt-4o-mini' },
      { key: 'system', label: '系统提示词', type: 'textarea', rows: 2, placeholder: '你是一位…' },
      {
        key: 'prompt',
        label: '用户提示词',
        type: 'textarea',
        rows: 3,
        placeholder: '请输入提示词…',
        hint: '支持 {{text}} 变量引用上游文本',
      },
      { key: 'temperature', label: '温度', type: 'number', default: 0.7, min: 0, max: 2, step: 0.1 },
    ],
  },

  'image-gen': {
    type: 'image-gen',
    label: '生图节点',
    description: '接入 v1/images 或 v1/chat 生图',
    icon: Sparkles,
    accent: '#ec4899',
    inputs: [
      { key: 'prompt', label: '提示词', kind: 'text' },
      { key: 'image', label: '参考图', kind: 'image' },
    ],
    outputs: [{ key: 'images', label: '图片组', kind: 'images' }],
    fields: [
      {
        key: 'apiType',
        label: '接口类型',
        type: 'select',
        default: 'images',
        options: [
          { label: 'Images API（/v1/images）', value: 'images' },
          { label: 'Chat 生图（/v1/chat）', value: 'chat' },
        ],
      },
      { key: 'baseUrl', label: 'Base URL', type: 'text', placeholder: 'https://api.example.com/v1' },
      { key: 'apiKey', label: 'API Key', type: 'password', placeholder: '留空使用服务端默认密钥' },
      { key: 'model', label: '模型', type: 'text', default: 'gpt-image-1' },
      {
        key: 'prompt',
        label: '提示词',
        type: 'textarea',
        rows: 3,
        placeholder: '描述想要的画面…',
        hint: '支持 {{text}} 变量；连入上游提示词时以上游为准',
      },
      {
        key: 'size',
        label: '尺寸',
        type: 'select',
        default: '1024x1024',
        options: [
          { label: '1:1（1024×1024）', value: '1024x1024' },
          { label: '2:3（1024×1536）', value: '1024x1536' },
          { label: '3:2（1536×1024）', value: '1536x1024' },
        ],
      },
      { key: 'count', label: '生成数量', type: 'number', default: 1, min: 1, max: 9, step: 1 },
    ],
  },

  'output-gallery': {
    type: 'output-gallery',
    label: '输出画廊',
    description: '汇总展示生成的图片',
    icon: Images,
    accent: '#10b981',
    inputs: [{ key: 'images', label: '图片组', kind: 'images' }],
    outputs: [],
    fields: [],
  },
}

export const nodeTypeList = Object.values(nodeRegistry)

/** 按字段声明生成默认参数 */
export function defaultParams(fields: FieldSchema[]): Record<string, unknown> {
  const params: Record<string, unknown> = {}
  for (const field of fields) {
    if (field.default !== undefined) params[field.key] = field.default
    else if (field.type === 'number') params[field.key] = field.min ?? 0
    else params[field.key] = ''
  }
  return params
}

