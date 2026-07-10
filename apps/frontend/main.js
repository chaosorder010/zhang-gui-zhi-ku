const chat = document.getElementById('chat');
const form = document.getElementById('ask-form');
const input = document.getElementById('question');
const newChatBtn = document.getElementById('new-chat');

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
