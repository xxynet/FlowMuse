/** 将模板字符串中的 {{var}} 替换为上下文变量，未命中则替换为空串 */
export function resolveTemplate(tpl: unknown, ctx: Record<string, string>): string {
  const source = typeof tpl === 'string' ? tpl : ''
  return source.replace(/\{\{\s*([\w-]+)\s*\}\}/g, (_, key: string) => ctx[key] ?? '')
}
