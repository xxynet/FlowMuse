import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/template.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const { resolveTemplate, mergeVariables } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'))
const cases = JSON.parse(readFileSync(new URL('./fixtures/templateCases.json', import.meta.url), 'utf8'))

test('placeholder syntax and literal values match the shared backend cases', () => {
  for (const item of cases) {
    if (item.error) assert.throws(() => resolveTemplate(item.source, item.context), /未定义变量/)
    else assert.equal(resolveTemplate(item.source, item.context), item.expected)
  }
})

test('variable chains preserve inherited names and explicitly override duplicates', () => {
  const inherited = mergeVariables({}, [{ name: 'story', value: '原剧情' }, { name: '风格', value: '水彩' }])
  const result = mergeVariables(inherited, [{ name: 'story', value: '新剧情' }])
  assert.equal(result.story, '新剧情')
  assert.equal(result['风格'], '水彩')
  assert.equal(inherited.story, '原剧情')
})

test('invalid names, duplicate entries, blank values and expansion budgets fail safely', () => {
  assert.throws(() => mergeVariables({}, []), /添加变量/)
  for (const name of ['1name', 'with space', 'a'.repeat(65)]) {
    assert.throws(() => mergeVariables({}, [{ name, value: 'value' }]), /变量名/)
  }
  assert.throws(() => mergeVariables({}, [{ name: 'x', value: '1' }, { name: 'x', value: '2' }]), /不得重复/)
  assert.throws(() => mergeVariables({}, [{ name: 'x', value: ' \n' }]), /变量值/)
  assert.throws(() => mergeVariables({}, [{ name: 'x', value: 'a'.repeat(32001) }]), /超过限制/)
  assert.throws(() => mergeVariables({}, Array.from({ length: 51 }, (_, i) => ({ name: 'v' + i, value: 'x' }))), /超过限制/)
  assert.throws(() => resolveTemplate('{x}{x}', { x: 'a'.repeat(20000) }), /32000/)
})
