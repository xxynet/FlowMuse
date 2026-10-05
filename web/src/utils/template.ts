import type { VariableBinding } from '@/types/flow'

const variableName = /^[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff-]{0,63}$/
const placeholder = /(?<!\{)(?:\{\{\s*([A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff-]{0,63})\s*\}\}|\{\s*([A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff-]{0,63})\s*\})(?!\})/g

export function mergeVariables(inherited: Record<string, string>, bindings: VariableBinding[]): Record<string, string> {
  const context = Object.assign(Object.create(null) as Record<string, string>, inherited)
  const names = new Set<string>()
  if (!bindings.length) throw new Error('请先为变量设置节点添加变量')
  for (const { name, value } of bindings) {
    if (!variableName.test(name)) throw new Error('变量名须以字母、中文或下划线开头，只能包含字母、中文、数字、下划线或连字符，最多 64 字符')
    if (names.has(name)) throw new Error('同一节点中的变量名不得重复')
    if (!value.trim()) throw new Error('请先为变量设置节点填写变量值')
    names.add(name)
    context[name] = value
  }
  if (Object.keys(context).length > 50 || Object.values(context).reduce((sum, value) => sum + value.length, 0) > 32000) {
    throw new Error('变量数量或内容超过限制（最多 50 个变量、合计 32000 字符）')
  }
  return context
}

/** Resolve named placeholders once; inserted values are never interpreted as templates. */
export function resolveTemplate(tpl: unknown, ctx: Record<string, string>): string {
  const source = typeof tpl === 'string' ? tpl : ''
  let expandedLength = 0
  let previousEnd = 0
  const resolved = source.replace(placeholder, (match, doubleName: string | undefined, singleName: string | undefined, offset: number) => {
    const name = (doubleName ?? singleName) as string
    if (!Object.prototype.hasOwnProperty.call(ctx, name)) {
      throw new Error('未定义变量：' + name + '，请连接变量设置节点并检查变量名')
    }
    const replacement = ctx[name] ?? ''
    expandedLength += offset - previousEnd + replacement.length
    previousEnd = offset + match.length
    if (expandedLength > 32000) throw new Error('替换变量后的提示词超过 32000 字符')
    return replacement
  })
  if (resolved.trim().length > 32000) throw new Error('替换变量后的提示词超过 32000 字符')
  return resolved
}
