import type { XYPosition } from '@vue-flow/core'
import type { Component } from 'vue'

/** 连线端口的数据种类，连接时校验：只有 kind 相同才能连 */
export type PortKind = 'image' | 'text' | 'images' | 'variables'

export interface PortSchema {
  key: string
  label: string
  kind: PortKind
}

export interface VariableBinding {
  name: string
  value: string
}

export type FieldType = 'text' | 'password' | 'textarea' | 'number' | 'select' | 'image' | 'variables'

export interface FieldOption {
  label: string
  value: string
}

/** 节点参数声明，前端按此渲染表单，后续后端也复用同一份 schema */
export interface FieldSchema {
  key: string
  label: string
  type: FieldType
  placeholder?: string
  default?: string | number | VariableBinding[]
  options?: FieldOption[]
  min?: number
  max?: number
  step?: number
  rows?: number
  hint?: string
}

export type NodeKind = 'image-upload' | 'text-input' | 'variable-set' | 'llm' | 'image-gen' | 'output-gallery'

/** 节点类型注册表条目：UI 与执行都围绕它声明式驱动 */
export interface NodeTypeSchema {
  type: NodeKind
  label: string
  description: string
  icon: Component
  /** 分类色，不随主题切换，用于在画布上区分节点类型 */
  accent: string
  inputs: PortSchema[]
  outputs: PortSchema[]
  fields: FieldSchema[]
}

export type NodeRunStatus = 'idle' | 'running' | 'success' | 'error'

/** 节点运行产物：图片统一归一为 images 数组 */
export interface NodeResult {
  text?: string
  variables?: Record<string, string>
  images?: string[]
  /** Same-origin downloads for persisted run images, aligned with images. */
  downloadUrls?: string[]
}

export interface FlowNodeData {
  label: string
  params: Record<string, unknown>
  status: NodeRunStatus
  error?: string
  result?: NodeResult
}

/**
 * 业务侧节点类型：data 必有。
 * Vue Flow 自带的 Node.data 是可选字段，边界处（CanvasView 的 v-model）做一次类型转换，
 * 项目内部一律使用 FlowNode，避免到处判空。
 */
export interface FlowNode {
  id: string
  type?: string
  position: XYPosition
  data: FlowNodeData
  selected?: boolean
  dragging?: boolean
}

/**
 * 业务侧连线类型（Vue Flow Edge 的精简版）。
 * 不直接复用 Vue Flow 的 Node / Edge：它们的类型里带 VNode 联合，
 * 被 ref 深解包时会触发 TS2589，统一在 CanvasView 边界做转换。
 */
export interface FlowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
  type?: string
  animated?: boolean
}

/** 玩法模板 = 一份预置工作流 */
export interface PresetDef {
  id: string
  name: string
  description: string
  icon: Component
  accent: string
  instructions?: string[]
  build: () => { nodes: FlowNode[]; edges: FlowEdge[] }
}
