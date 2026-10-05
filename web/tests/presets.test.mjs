import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import ts from 'typescript'

// Load the actual TypeScript templates and registry with the project's compiler.
const require = createRequire(import.meta.url)
const modules = new Map()
function loadSource(name) {
  if (modules.has(name)) return modules.get(name)
  const source = readFileSync(new URL('../src/' + name + '.ts', import.meta.url), 'utf8')
  const compiled = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText
  const module = { exports: {} }
  const resolve = (specifier) => specifier.startsWith('@/')
    ? loadSource(specifier.slice(2))
    : require(specifier)
  new Function('require', 'module', 'exports', compiled)(resolve, module, module.exports)
  modules.set(name, module.exports)
  return module.exports
}
const { presetList } = loadSource('presets/index')
const { nodeRegistry } = loadSource('registry/nodeRegistry')

test('every preset builds a fresh, connected graph with valid unique ports', () => {
  assert.equal(new Set(presetList.map((preset) => preset.id)).size, presetList.length)
  for (const preset of presetList) {
    const graph = preset.build()
    const nodes = new Map(graph.nodes.map((node) => [node.id, node]))
    assert.equal(nodes.size, graph.nodes.length, preset.id)
    assert.equal(new Set(graph.edges.map((edge) => edge.id)).size, graph.edges.length, preset.id)
    const occupied = new Set()
    for (const edge of graph.edges) {
      const source = nodeRegistry[nodes.get(edge.source)?.type]
      const target = nodeRegistry[nodes.get(edge.target)?.type]
      const output = source?.outputs.find((port) => port.key === edge.sourceHandle)
      const input = target?.inputs.find((port) => port.key === edge.targetHandle)
      assert.ok(output && input, preset.id)
      assert.equal(output.kind, input.kind, preset.id)
      const port = edge.target + ':' + edge.targetHandle
      assert.ok(!occupied.has(port), preset.id)
      occupied.add(port)
    }
    for (const node of graph.nodes) {
      if (node.type === 'image-upload') {
        assert.ok(graph.edges.some((edge) => edge.source === node.id), preset.id)
      }
      if (node.type === 'output-gallery') assert.ok(occupied.has(node.id + ':images'), preset.id)
    }
    graph.nodes[0].data.params.image = 'changed'
    assert.notEqual(preset.build().nodes[0].data.params.image, 'changed', preset.id)
  }
})

test('LINE pack requests one 16-cell sheet and preserves its local instructions', () => {
  const preset = presetList.find((preset) => preset.id === 'line-sticker-pack')
  const graph = preset.build()
  const generator = graph.nodes.find((node) => node.type === 'image-gen')
  assert.equal(generator.data.params.count, 1)
  assert.match(generator.data.params.prompt, /4 行 × 4 列/)
  assert.match(generator.data.params.prompt, /16/)
  // A connected upstream prompt would override the layout constraints.
  assert.ok(!graph.edges.some((edge) => edge.target === generator.id && edge.targetHandle === 'prompt'))
  assert.equal(graph.nodes.filter((node) => node.type === 'image-upload').length, 1)
  assert.ok(preset.instructions.length)
})

test('character swap and style transfer distinguish the two reference roles', () => {
  for (const id of ['sticker-character-swap', 'style-transfer']) {
    const preset = presetList.find((preset) => preset.id === id)
    const graph = preset.build()
    const generator = graph.nodes.find((node) => node.type === 'image-gen')
    const first = graph.edges.find((edge) => edge.target === generator.id && edge.targetHandle === 'image')
    const second = graph.edges.find((edge) => edge.target === generator.id && edge.targetHandle === 'image2')
    assert.ok(first && second, id)
    assert.notEqual(first.source, second.source, id)
    assert.match(graph.nodes.find((node) => node.id === first.source).data.label, /参考图 1/)
    assert.match(graph.nodes.find((node) => node.id === second.source).data.label, /参考图 2/)
    assert.match(generator.data.params.prompt, /参考图 1/)
    assert.match(generator.data.params.prompt, /参考图 2/)
    assert.ok(preset.instructions.length)
  }
})

test('comic uses generic named variables while retaining sheet instructions', () => {
  const graph = presetList.find((preset) => preset.id === 'four-panel-comic').build()
  const generator = graph.nodes.find((node) => node.type === 'image-gen')
  const story = graph.nodes.find((node) => node.type === 'variable-set')
  assert.ok(story)
  assert.equal(story.data.label, '变量设置')
  assert.deepEqual(story.data.params.variables, [{ name: '剧情', value: '' }])
  assert.ok(graph.edges.some((edge) => edge.source === story.id && edge.sourceHandle === 'variables'
    && edge.target === generator.id && edge.targetHandle === 'variables'))
  assert.ok(!graph.edges.some((edge) => edge.target === generator.id && edge.targetHandle === 'prompt'))
  assert.equal(generator.data.params.count, 1)
  assert.match(generator.data.params.prompt, /2 行 × 2 列/)
  assert.match(generator.data.params.prompt, /左上、右上、左下、右下/)
  assert.match(generator.data.params.prompt, /{{ 剧情 }}/)
  story.data.params.variables[0].value = '第一格：主角登上月球。'
  const { graphPayload } = loadSource('services/api')
  const saved = graphPayload(graph.nodes, graph.edges, false)
  assert.deepEqual(saved.nodes.find((node) => node.id === story.id).data.params.variables, story.data.params.variables)
  assert.deepEqual(presetList.find((preset) => preset.id === 'four-panel-comic').build()
    .nodes.find((node) => node.type === 'variable-set').data.params.variables, [{ name: '剧情', value: '' }])
})

test('variable-node defaults are independent across instances', () => {
  const { makeNode } = loadSource('presets/utils')
  const first = makeNode('first', 'variable-set', { x: 0, y: 0 })
  const second = makeNode('second', 'variable-set', { x: 0, y: 0 })
  first.data.params.variables[0].name = 'changed'
  assert.equal(second.data.params.variables[0].name, '')
})
