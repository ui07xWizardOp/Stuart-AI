/**
 * Agent Chat Module (Phase 8)
 * 
 * Handles the PCA Agent chat view — sending messages to /api/agent/chat,
 * rendering responses, managing autonomy toggles, and status polling.
 */

class AgentChat {
    constructor() {
        this.messagesContainer = null;
        this.inputField = null;
        this.sendBtn = null;
        this.typingIndicator = null;
        this.statusPill = null;
        this.welcomeEl = null;

        // Bento Metrics
        this.tokenProgress = null;
        this.tokenPercent = null;
        this.tokenDetail = null;
        this.memoryBar = null;

        this.isWaiting = false;

        this._pollInterval = null;
    }

    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.messagesContainer = document.getElementById('agent-messages');
        this.inputField = document.getElementById('agent-input');
        this.sendBtn = document.getElementById('agent-send-btn');
        this.typingIndicator = document.getElementById('agent-typing');
        this.statusPill = document.getElementById('agent-status-pill');
        this.welcomeEl = document.getElementById('agent-welcome');

        // Bento Elements
        this.tokenProgress = document.getElementById('token-progress');
        this.tokenPercent = document.getElementById('token-percent');
        this.tokenDetail = document.getElementById('token-detail');
        this.memoryBar = document.getElementById('memory-bar');

        if (!this.inputField) return;

        // Send on Enter (Shift+Enter for newline)
        this.inputField.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.inputField.addEventListener('input', () => {
            this.inputField.style.height = 'auto';
            this.inputField.style.height = Math.min(this.inputField.scrollHeight, 120) + 'px';
        });

        // Send button click
        this.sendBtn?.addEventListener('click', () => this.sendMessage());

        // Autonomy toggle buttons
        document.querySelectorAll('.autonomy-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setAutonomy(btn.dataset.level));
        });

        // Mode toggle (Final/Focus) - narrowed to avoid collision with main nav
        document.querySelectorAll('.mode-toggle-inline .mode-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
        });

        // Start status polling
        this.pollStatus();
        this.pollBudget(); // Initial budget pull
        this._pollInterval = setInterval(() => {
            this.pollStatus();
            this.pollBudget();
        }, 10000); // 10s polling for health/metrics
    }

    async sendMessage() {
        if (this.isWaiting) return;

        const text = this.inputField.value.trim();
        if (!text) return;

        // Hide welcome screen on first message
        if (this.welcomeEl) {
            this.welcomeEl.style.display = 'none';
        }

        // Render user bubble
        this.appendMessage('user', text);
        this.inputField.value = '';
        this.inputField.style.height = 'auto';

        // Show typing indicator
        this.setTyping(true);
        this.isWaiting = true;
        this.sendBtn.disabled = true;

        try {
            const res = await fetch('/api/agent/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            const data = await res.json();

            if (!res.ok) {
                this.appendMessage('agent', `⚠️ Error: ${data.detail || 'Unknown error'}`, null);
            } else {
                this.appendMessage('agent', data.response, data.elapsed_ms);
            }
        } catch (err) {
            this.appendMessage('agent', `⚠️ Connection failed: ${err.message}`, null);
        } finally {
            this.setTyping(false);
            this.isWaiting = false;
            this.sendBtn.disabled = false;
            this.inputField.focus();
        }
    }

    appendMessage(role, content, elapsedMs) {
        const msgEl = document.createElement('div');
        msgEl.className = `agent-msg ${role}`;

        const label = document.createElement('span');
        label.className = 'msg-label';
        label.textContent = role === 'user' ? 'You' : 'Stuart Agent';

        const body = document.createElement('div');
        body.className = 'msg-body';

        // Basic markdown rendering
        body.innerHTML = this.renderMarkdown(content);

        msgEl.appendChild(label);
        msgEl.appendChild(body);

        // Elapsed time badge for agent responses
        if (role === 'agent' && elapsedMs !== null && elapsedMs !== undefined) {
            const elapsed = document.createElement('span');
            elapsed.className = 'msg-elapsed';
            elapsed.textContent = `${(elapsedMs / 1000).toFixed(1)}s`;
            msgEl.appendChild(elapsed);
        }

        this.messagesContainer.appendChild(msgEl);

        // Auto-scroll to bottom
        requestAnimationFrame(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        });
    }

    renderMarkdown(text) {
        if (!text) return '';
        let html = text;

        // Code blocks (```lang\n...\n```)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
            const escaped = code.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return `<pre><code class="language-${lang || 'text'}">${escaped}</code></pre>`;
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

        // Headers
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // Unordered lists
        html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        // Line breaks (double newline = paragraph break)
        html = html.replace(/\n\n/g, '<br><br>');
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    setTyping(show) {
        if (this.typingIndicator) {
            this.typingIndicator.classList.toggle('show', show);
        }
    }

    async pollStatus() {
        try {
            const res = await fetch('/api/agent/status');
            const data = await res.json();

            if (this.statusPill) {
                const dotEl = this.statusPill.querySelector('.agent-status-dot');
                const textEl = this.statusPill.querySelector('.agent-status-text');

                if (data.status === 'online') {
                    this.statusPill.className = 'agent-status-pill online';
                    if (textEl) textEl.textContent = 'Online';
                } else {
                    this.statusPill.className = 'agent-status-pill offline';
                    if (textEl) textEl.textContent = 'Offline';
                }
            }

            // Sync autonomy UI
            if (data.autonomy_level) {
                document.querySelectorAll('.autonomy-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.level === data.autonomy_level);
                });
            }

            // Sync Security Perimeter
            this.updateSecurityPerimeter(data);
        } catch (e) {
            // Silently fail — agent might not be booted yet
        }
    }

    async pollBudget() {
        try {
            const res = await fetch('/api/agent/budget');
            const data = await res.json();
            this.updateBudgetWidget(data);
        } catch (e) {
            console.warn('Budget poll failed:', e);
        }
    }

    updateBudgetWidget(data) {
        if (!data || !this.tokenProgress) return;

        // Daily Tokens calculation
        const consumed = data.daily_tokens || 0;
        const total = data.daily_limit || 500000;
        const percent = Math.min(Math.round((consumed / total) * 100), 100);

        // Update Ring
        const radius = 42;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference - (percent / 100) * circumference;
        
        this.tokenProgress.style.strokeDashoffset = offset;

        // Update Text
        if (this.tokenPercent) this.tokenPercent.textContent = `${percent}%`;
        if (this.tokenDetail) {
            this.tokenDetail.textContent = `${(consumed / 1000).toFixed(1)}K / ${(total / 1000).toFixed(0)}K Tokens`;
        }

        // Memory usage simulation/proxy (using uptime or session count for now)
        if (this.memoryBar) {
            const memPercent = Math.min(10 + (consumed / 5000), 95);
            this.memoryBar.style.width = `${memPercent}%`;
        }
    }

    updateSecurityPerimeter(healthData) {
        const guardEl = document.getElementById('guard-status');
        const dlpEl = document.getElementById('dlp-status');

        if (healthData && healthData.subsystems) {
            const fileGuard = healthData.subsystems.file_guard;
            if (guardEl) {
                const active = fileGuard && !fileGuard.error;
                guardEl.textContent = active ? 'Secured' : 'Offline';
                guardEl.classList.toggle('active', active);
            }
        }
    }

    async setAutonomy(level) {
        try {
            await fetch('/api/agent/autonomy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level })
            });

            // Update UI immediately
            document.querySelectorAll('.autonomy-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.level === level);
            });
        } catch (e) {
            console.warn('Failed to set autonomy:', e);
        }
    }

    setMode(mode) {
        const container = document.querySelector('.agent-chat-container');
        if (!container) return;

        const isFocus = mode === 'focus';
        container.classList.toggle('focus-mode', isFocus);

        document.querySelectorAll('.mode-toggle-inline .mode-toggle-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
    }

    destroy() {
        if (this._pollInterval) {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
        }
    }
}

const agentChat = new AgentChat();
export default agentChat;
export { AgentChat };
