import type { FlowEdge, FlowNode, NodeKind } from '@/types/flow'
import { defaultParams, nodeRegistry } from '@/registry/nodeRegistry'

export function makeNode(
  id: string,
  type: NodeKind,
  position: { x: number; y: number },
  overrides: Record<string, unknown> = {},
): FlowNode {
  const schema = nodeRegistry[type]
  return {
    id,
    type,
    position,
    data: {
      label: schema.label,
      params: { ...defaultParams(schema.fields), ...overrides },
      status: 'idle',
    },
  }
}

export function makeEdge(source: string, sourceHandle: string, target: string, targetHandle: string): FlowEdge {
  return {
    id: `e-${source}.${sourceHandle}-${target}.${targetHandle}`,
    source,
    sourceHandle,
    target,
    targetHandle,
  }
}
