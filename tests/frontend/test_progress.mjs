import { strict as assert } from 'node:assert';
import { mapStatusToProgress } from '../../apps/frontend/progress.js';

let passed = 0;

function test(name, fn) {
  fn();
  passed++;
  console.log(`  ✅ ${name}`);
}

console.log('mapStatusToProgress — status mapping');

test('uploaded → 5% pending', () => {
  const r = mapStatusToProgress('uploaded');
  assert.equal(r.percent, 5);
  assert.equal(r.label, '上传完成');
  assert.equal(r.terminal, false);
  assert.equal(r.kind, 'pending');
});

test('extracting → 20%', () => {
  const r = mapStatusToProgress('extracting');
  assert.equal(r.percent, 20);
  assert.equal(r.label, '解析中');
  assert.equal(r.terminal, false);
});

test('recognizing → 40%', () => {
  const r = mapStatusToProgress('recognizing');
  assert.equal(r.percent, 40);
  assert.equal(r.label, '识别中');
  assert.equal(r.terminal, false);
});

test('chunking → 60%', () => {
  const r = mapStatusToProgress('chunking');
  assert.equal(r.percent, 60);
  assert.equal(r.label, '分块中');
  assert.equal(r.terminal, false);
});

test('embedding → 80%', () => {
  const r = mapStatusToProgress('embedding');
  assert.equal(r.percent, 80);
  assert.equal(r.label, '嵌入中');
  assert.equal(r.terminal, false);
});

test('storing → 90%', () => {
  const r = mapStatusToProgress('storing');
  assert.equal(r.percent, 90);
  assert.equal(r.label, '入库中');
  assert.equal(r.terminal, false);
});

test('done → 100% terminal success', () => {
  const r = mapStatusToProgress('done');
  assert.equal(r.percent, 100);
  assert.equal(r.label, '完成');
  assert.equal(r.terminal, true);
  assert.equal(r.kind, 'success');
});

test('failed → -1 terminal error', () => {
  const r = mapStatusToProgress('failed');
  assert.equal(r.percent, -1);
  assert.equal(r.label, '失败');
  assert.equal(r.terminal, true);
  assert.equal(r.kind, 'error');
});

test('unknown status → 0% fallback', () => {
  const r = mapStatusToProgress('nonexistent');
  assert.equal(r.percent, 0);
  assert.equal(r.label, '未知');
  assert.equal(r.terminal, false);
});

console.log(`\n${passed}/9 passed`);
