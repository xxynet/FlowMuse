import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

// Use the project's compiler so these tests also run on the supported Node 20 versions.
const source = readFileSync(new URL('../src/services/resultImages.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText
const { generatedImages, downloadImage } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

const node = (id, type, images, status = 'success') => ({
  id, type, position: { x: 0, y: 0 },
  data: { label: id, params: {}, status, result: { images } },
})

test('counts generated images once, excluding uploads and gallery mirrors', () => {
  const items = generatedImages([
    node('upload', 'image-upload', ['reference.png']),
    node('gen', 'image-gen', ['result.png']),
    node('gallery', 'output-gallery', ['result.png']),
  ])
  assert.deepEqual(items.map((item) => item.src), ['result.png'])
})

test('includes multiple generators without requiring a gallery and ignores failed results', () => {
  const first = node('one', 'image-gen', ['one.png', 'two.png'])
  first.data.result.downloadUrls = ['/api/download/one', '/api/download/two']
  const items = generatedImages([first, node('two', 'image-gen', ['three.png']),
    node('failed', 'image-gen', ['stale.png'], 'error')])
  assert.equal(items.length, 3)
  assert.equal(items[1].downloadUrl, '/api/download/two')
  assert.equal(new Set(items.map((item) => item.key)).size, 3)
})

function downloadEnvironment(t, response) {
  const clicked = []
  const fetched = []
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
  t.after(() => {
    if (original) Object.defineProperty(globalThis, 'document', original)
    else delete globalThis.document
  })
  globalThis.document = {
    body: { appendChild() {} },
    createElement() { return { click() { clicked.push({ href: this.href, download: this.download }) }, remove() {} } },
  }
  t.mock.method(globalThis, 'fetch', async (url, options) => { fetched.push({ url, options }); return response })
  t.mock.method(URL, 'createObjectURL', () => 'blob:download-test')
  t.mock.method(URL, 'revokeObjectURL', () => {})
  t.mock.method(globalThis, 'setTimeout', () => 1)
  t.mock.method(globalThis, 'clearTimeout', () => {})
  return { clicked, fetched }
}

test('downloads remote images through the recorded same-origin URL and a Blob link', async (t) => {
  const { clicked, fetched } = downloadEnvironment(t, new Response('image-bytes', { headers: { 'Content-Type': 'image/png' } }))
  await downloadImage('https://cdn.example/image', 'flowmuse-result', '/api/runs/run/images/3/0')
  assert.equal(fetched[0].url, '/api/runs/run/images/3/0')
  assert.equal(fetched[0].options.credentials, 'omit')
  assert.deepEqual(clicked, [{ href: 'blob:download-test', download: 'flowmuse-result.png' }])
})

test('inline images use the actual MIME extension', async (t) => {
  const { clicked } = downloadEnvironment(t, new Response('image-bytes', { headers: { 'Content-Type': 'image/jpeg' } }))
  await downloadImage('data:image/jpeg;base64,test', 'flowmuse-result')
  assert.equal(clicked[0].download, 'flowmuse-result.jpg')
})

test('download failures do not click an external link or navigate away', async (t) => {
  const { clicked } = downloadEnvironment(t, new Response(JSON.stringify({ detail: 'Expired image' }), { status: 502 }))
  await assert.rejects(downloadImage('https://cdn.example/expired', 'result', '/api/runs/run/images/3/0'), /Expired image/)
  assert.equal(clicked.length, 0)
})

test('rejects non-image responses instead of saving HTML as an image', async (t) => {
  const { clicked } = downloadEnvironment(t, new Response('<html>error</html>', { headers: { 'Content-Type': 'text/html' } }))
  await assert.rejects(downloadImage('https://cdn.example/expired', 'result'), /有效图片/)
  assert.equal(clicked.length, 0)
})
