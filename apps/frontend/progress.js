/**
 * Pure status → progress mapping for the upload panel.
 * No DOM / network side-effects — safe to unit-test in Node.js.
 */

const STATUS_MAP = {
  uploaded: { percent: 5, label: '上传完成', terminal: false, kind: 'pending' },
  extracting: { percent: 20, label: '解析中', terminal: false, kind: 'pending' },
  recognizing: { percent: 40, label: '识别中', terminal: false, kind: 'pending' },
  chunking: { percent: 60, label: '分块中', terminal: false, kind: 'pending' },
  embedding: { percent: 80, label: '嵌入中', terminal: false, kind: 'pending' },
  storing: { percent: 90, label: '入库中', terminal: false, kind: 'pending' },
  done: { percent: 100, label: '完成', terminal: true, kind: 'success' },
  failed: { percent: -1, label: '失败', terminal: true, kind: 'error' },
};

export function mapStatusToProgress(status) {
  return STATUS_MAP[status] || { percent: 0, label: '未知', terminal: false, kind: 'pending' };
}
