import { mapStatusToProgress } from './progress.js';

const chat = document.getElementById('chat');
const form = document.getElementById('ask-form');
const input = document.getElementById('question');
const newChatBtn = document.getElementById('new-chat');
const docList = document.getElementById('doc-list');

// --- Upload panel state ---
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const fileCount = document.getElementById('file-count');
const progressList = document.getElementById('progress-list');
const POLL_INTERVAL_MS = 2500;

/** @type {Map<string, {fileName: string, el: HTMLElement, status: string, terminal: boolean}>} */
const uploadTasks = new Map();
let pollTimer = null;

fileInput.addEventListener('change', () => {
    const n = fileInput.files.length;
    uploadBtn.disabled = n === 0;
    fileCount.textContent = n === 0 ? '选择文件' : `已选 ${n} 个文件`;
});

uploadBtn.addEventListener('click', async () => {
    const files = fileInput.files;
    if (files.length === 0) return;

    const formData = new FormData();
    for (const f of files) formData.append('files', f);

    uploadBtn.disabled = true;

    let resp;
    try {
        resp = await fetch('/api/upload', { method: 'POST', body: formData });
    } catch (e) {
        uploadBtn.disabled = false;
        appendMessage('error', `上传请求失败: ${e.message}`);
        return;
    }

    if (!resp.ok) {
        uploadBtn.disabled = false;
        const err = await resp.json().catch(() => ({}));
        appendMessage('error', `上传失败: ${err.detail || resp.statusText}`);
        return;
    }

    const data = await resp.json();
    fileInput.value = '';
    fileCount.textContent = '选择文件';

    // Render one progress row per task
    for (const task of data.tasks) {
        const el = document.createElement('div');
        el.className = 'progress-row';
        el.innerHTML = `
            <span class="prog-file"></span>
            <span class="prog-badge"></span>
            <div class="prog-bar-track"><div class="prog-bar-fill"></div></div>
            <span class="prog-pct"></span>
            <span class="prog-error"></span>
        `;
        el.querySelector('.prog-file').textContent = task.file_name;
        progressList.appendChild(el);

        uploadTasks.set(task.task_id, {
            fileName: task.file_name,
            el,
            status: task.status,
            terminal: false,
        });

        updateRow(task.task_id, task.status, null);
    }

    uploadBtn.disabled = false;
    startPolling();
});

function updateRow(taskId, status, error) {
    const task = uploadTasks.get(taskId);
    if (!task) return;

    task.status = status;
    const { percent, label, terminal, kind } = mapStatusToProgress(status);
    task.terminal = terminal;

    const badge = task.el.querySelector('.prog-badge');
    const fill = task.el.querySelector('.prog-bar-fill');
    const pct = task.el.querySelector('.prog-pct');
    const errEl = task.el.querySelector('.prog-error');

    badge.textContent = label;
    badge.className = `prog-badge badge-${kind}`;

    if (status === 'failed') {
        fill.style.width = '100%';
        fill.classList.add('bar-error');
        pct.textContent = '✗';
        task.el.classList.add('row-error');
    } else if (status === 'done') {
        fill.style.width = '100%';
        fill.classList.add('bar-done');
        pct.textContent = '100%';
    } else {
        fill.style.width = `${percent}%`;
        pct.textContent = `${percent}%`;
    }

    if (error) {
        errEl.textContent = error;
    }
}

function allTerminal() {
    if (uploadTasks.size === 0) return false;
    for (const t of uploadTasks.values()) {
        if (!t.terminal) return false;
    }
    return true;
}

async function pollOnce() {
    for (const [taskId] of uploadTasks) {
        try {
            const resp = await fetch(`/api/upload/${taskId}`);
            if (!resp.ok) continue;
            const data = await resp.json();
            updateRow(taskId, data.status, data.error || null);
        } catch (_) {
            // network hiccup — skip, next tick retries
        }
    }

    if (allTerminal()) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

function startPolling() {
    if (pollTimer) return; // already running
    pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
}

let sessionId = crypto.randomUUID();

function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function removeLoading() {
    const el = chat.querySelector('.msg.loading');
    if (el) el.remove();
}

async function ask(question) {
    appendMessage('user', question);
    const loading = appendMessage('bot', '思考中...');
    loading.classList.add('loading');

    try {
        const resp = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, session_id: sessionId }),
        });
        removeLoading();
        if (!resp.ok) {
            const err = await resp.json();
            appendMessage('error', `错误: ${err.detail || resp.statusText}`);
            return;
        }
        const data = await resp.json();
        appendMessage('bot', data.answer);
    } catch (e) {
        removeLoading();
        appendMessage('error', `请求失败: ${e.message}`);
    }
}

form.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    ask(q);
});

newChatBtn.addEventListener('click', () => {
    sessionId = crypto.randomUUID();
    chat.innerHTML = '';
});

async function loadDocuments() {
    try {
        const resp = await fetch('/api/documents');
        if (!resp.ok) return;
        const docs = await resp.json();
        renderDocumentList(docs);
    } catch (e) {
        console.error('加载文档列表失败:', e);
    }
}

function renderDocumentList(docs) {
    if (!docs || docs.length === 0) {
        docList.innerHTML = '<li class="doc-empty">暂无文档</li>';
        return;
    }
    docList.innerHTML = '';
    for (const doc of docs) {
        const li = document.createElement('li');
        li.className = 'doc-item';

        const name = document.createElement('span');
        name.className = 'doc-name';
        name.textContent = doc.file_name || doc.task_id || '未知';

        const status = document.createElement('span');
        status.className = `doc-status status-${doc.status}`;
        status.textContent = doc.status;

        const delBtn = document.createElement('button');
        delBtn.className = 'doc-delete';
        delBtn.textContent = '删除';
        delBtn.addEventListener('click', () => deleteDocument(doc.file_name || doc.task_id));

        li.appendChild(name);
        li.appendChild(status);
        li.appendChild(delBtn);
        docList.appendChild(li);
    }
}

async function deleteDocument(docName) {
    if (!confirm(`确定要删除文档「${docName}」吗?`)) return;
    try {
        const resp = await fetch(`/api/documents/${encodeURIComponent(docName)}`, {
            method: 'DELETE',
        });
        if (!resp.ok) {
            const err = await resp.json();
            alert(`删除失败: ${err.detail || resp.statusText}`);
            return;
        }
        await loadDocuments();
    } catch (e) {
        alert(`删除失败: ${e.message}`);
    }
}

// 页面加载时拉取文档列表
loadDocuments();
