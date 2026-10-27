import test from 'node:test'
import assert from 'node:assert/strict'
import {createHash} from 'node:crypto'
import {readFileSync,existsSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import {resolve,dirname} from 'node:path'
import {runInNewContext} from 'node:vm'

const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..')
const manifest=JSON.parse(readFileSync(resolve(root,'docs/sprint7/S6_ASSET_RESTORE_MANIFEST_20261025.json'),'utf8'))
const digest=(kind,bytes)=>createHash(kind).update(bytes).digest('hex')

test('restored resources retain exact source Blob SHA1, SHA256, size and safe paths',()=>{
 assert.equal(manifest.source_commit,'4d935bb88475560617b2a6014192012407f78e9c')
 assert.equal(manifest.restored_files.length,113)
 for(const entry of manifest.restored_files){
  assert.ok(!entry.path.includes('..') && !entry.path.startsWith('/'))
  const bytes=readFileSync(resolve(root,entry.path));assert.equal(bytes.length,entry.bytes,entry.path)
  assert.equal(digest('sha256',bytes),entry.sha256,entry.path)
  assert.equal(digest('sha1',Buffer.concat([Buffer.from(`blob ${bytes.length}\0`),bytes])),entry.git_blob_sha1,entry.path)
 }
})

test('restored PNG dimensions and SVG content match verified media rather than LFS pointers',()=>{
 for(const entry of manifest.restored_files){
  const bytes=readFileSync(resolve(root,entry.path))
  if(entry.path.endsWith('.png')){assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');assert.equal(bytes.readUInt32BE(16),entry.width);assert.equal(bytes.readUInt32BE(20),entry.height)}
  if(entry.path.endsWith('.svg')){assert.match(bytes.toString(),/<svg\b/);assert.doesNotMatch(bytes.toString(),/<script\b|\bon\w+\s*=|(?:href|src)\s*=\s*["'](?:https?:|javascript:|data:)/i)}
 }
})

test('rejected draft stays absent; original protection and two exact Owner-approved page revisions stay pinned',()=>{
 const revisions=JSON.parse(readFileSync(resolve(root,'docs/sprint7/APPROVED_SOURCE_REVISIONS_20261027.json'),'utf8'))
 const approved={
  'frontend/pages/v3-player/v3-player.vue':'0e98d0af3f774927aa4672e0c1e0e3199836bde538edc3cc965ba37c5648c087',
  'frontend/pages/v3-profile/v3-profile.vue':'cb2d0c7057b7246909de8751cdb75ad39da1d8dc1d3a874e9a0e015c3ec8680e',
 }
 assert.equal(revisions.schema_version,'owner_approved_source_revisions_v1')
 assert.equal(revisions.approved_commit,'44cbda17f43c17b0cbf356b89de74f5cb6b5f3f4')
 assert.equal(revisions.owner_approval,'docs/sprint7/OWNER_APPROVAL_20261027_SOURCE_SHA_REVISION.md')
 assert.ok(existsSync(resolve(root,revisions.owner_approval)))
 assert.equal(revisions.original_manifest_lf_sha256,'c4cc2a5030e6e252840b246d37f47b2f381a9f55b254c9ef9a07c85d7ad09e6f')
 assert.equal(digest('sha256',readFileSync(resolve(root,'docs/sprint7/S6_ASSET_RESTORE_MANIFEST_20261025.json'),'utf8').replace(/\r\n/g,'\n')),revisions.original_manifest_lf_sha256)
 assert.deepEqual(revisions.changes.map(row=>row.path).sort(),Object.keys(approved).sort())
 for(const row of revisions.changes){assert.equal(row.original_sha256,manifest.protected_source_sha256[row.path]);assert.equal(row.approved_sha256,approved[row.path])}
 for(const excluded of manifest.excluded)assert.equal(existsSync(resolve(root,excluded.path)),false,excluded.path)
 for(const [path,sha] of Object.entries(manifest.protected_source_sha256))assert.equal(digest('sha256',readFileSync(resolve(root,path),'utf8').replace(/\r\n/g,'\n')),approved[path]||sha,path)
})

test('all literal runtime and tab static references resolve to restored formal assets',()=>{
 for(const path of Object.keys(manifest.protected_source_sha256).filter(p=>p.endsWith('.vue'))){
  const text=readFileSync(resolve(root,path),'utf8')
  for(const match of text.matchAll(/\/?static\/[A-Za-z0-9_./-]+\.(?:png|svg|wav)/g))assert.ok(existsSync(resolve(root,'frontend',match[0].replace(/^\//,''))),`${path}: ${match[0]}`)
 }
 const pages=JSON.parse(readFileSync(resolve(root,'frontend/pages.json'),'utf8'))
 for(const tab of pages.tabBar.list)for(const path of [tab.iconPath,tab.selectedIconPath])assert.ok(existsSync(resolve(root,'frontend',path)),path)
})

test('every actual Q1-Q10 option resolves its existing dynamic illustration',()=>{
 const src=readFileSync(resolve(root,'frontend/pages/v3-questionnaire/v3-questionnaire.vue'),'utf8')
 const script=src.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/import\s*\{([\s\S]*?)\}\s*from\s*["'][^"']+["'];?/g,(_,names)=>`const {${names}}=deps;`).replace('export default {','options = {')
 const box={deps:{},options:null};runInNewContext(script,box)
 const methods=box.options.methods,page={};for(const [name,fn] of Object.entries(methods))page[name]=fn.bind(page)
 const schema=JSON.parse(readFileSync(resolve(root,'knowledge/v3/questionnaire-v3.0.1.json'),'utf8'))
 for(const q of schema.questions)q.options.forEach((option,index)=>{const path=page.optionImage(q,option,index);assert.ok(path,`${q.question_id}: ${index}`);assert.ok(existsSync(resolve(root,'frontend',path.replace(/^\//,''))),path)})
})

test('demo WAV stays explicitly mock-only and matches the original fixture duration',()=>{
 const entry=manifest.restored_files.find(e=>e.path.endsWith('jiao-demo.wav')),bytes=readFileSync(resolve(root,entry.path))
 assert.equal(entry.usage,'mock_test_only');assert.equal(bytes.toString('ascii',0,4),'RIFF');assert.equal(bytes.toString('ascii',8,12),'WAVE')
 assert.ok(Math.abs(entry.frames/entry.sample_rate-60.881632653061224)<0.000001)
 const facade=readFileSync(resolve(root,'frontend/common/api-v3.js'),'utf8');assert.match(facade,/仅显式 mock\/hybrid 模式/)
})
