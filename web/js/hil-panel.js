/**
 * HIL Panel — Dynamic Human-In-The-Loop Control
 * Phase 10 · Stuart Personal Cognitive Agent
 *
 * Provides:
 *  - Autonomy level slider (3-stop: Restricted / Moderate / Full)
 *  - Per-risk-tier threshold buttons (Auto / Prompt / Block)
 *  - Live approval queue with allow/deny + countdown timer
 *  - Risk event stream log
 *  - Session stats (approved, denied, auto-ran)
 *  - Polling sync with /api/agent/status and /api/hil/queue
 */

class HILPanel {
    constructor() {
        this.panel      = null;
        this.trigger    = null;
        this.countBadge = null;
        this.isOpen     = false;

        // Live state
        this.currentAutonomy = 'moderate';
        this.pendingApprovals = [];   // [{id, tool, action, risk, ts, timeout}]
        this.eventLog = [];           // [{type, text, ts}]
        this.stats = { auto: 0, approved: 0, denied: 0 };

        // Threshold map: LOW, MEDIUM, HIGH, CRITICAL → 'auto'|'prompt'|'block'
        this.thresholds = {
            LOW:      'auto',
            MEDIUM:   'auto',
            HIGH:     'prompt',
            CRITICAL: 'prompt',
        };

        this._pollTimer = null;
        this._countdownTimers = {};
    }

    /* ── Bootstrap ─────────────────────────────────────────────────── */
    init() {
        this._inject();
        this._bindEvents();
        this._syncAutonomyFromServer();
        this._startPolling();
    }

    /* ── DOM injection ──────────────────────────────────────────────── */
    _inject() {
        // Trigger button (always visible tab on edge)
        const trigger = document.createElement('div');
        trigger.id = 'hil-panel-trigger';
        trigger.innerHTML = `
            <span class="hil-trigger-icon">🛡️</span>
            <span class="hil-trigger-label">HIL</span>
            <span class="hil-trigger-count" id="hil-count-badge">0</span>
        `;
        document.body.appendChild(trigger);
        this.trigger    = trigger;
        this.countBadge = trigger.querySelector('#hil-count-badge');

        // Panel
        const panel = document.createElement('div');
        panel.id = 'hil-panel';
        panel.innerHTML = this._buildPanelHTML();
        document.body.appendChild(panel);
        this.panel = panel;
    }

    _buildPanelHTML() {
        return `
        <!-- Header -->
        <div class="hil-panel-header">
            <div class="hil-title">
                <div class="hil-title-icon">🧠</div>
                <div>
                    <p class="hil-title h3" style="margin:0;font-size:13px;font-weight:700;color:#e8e8ed;">HIL Control</p>
                    <p class="hil-title-sub" style="margin:0;">Human-In-The-Loop</p>
                </div>
            </div>
            <button class="hil-close-btn" id="hil-close-btn" title="Close panel">✕</button>
        </div>

        <!-- Body -->
        <div class="hil-panel-body">

            <!-- 1. Autonomy Slider -->
            <div class="hil-card">
                <div class="hil-card-header">
                    <span class="hil-card-title">Autonomy Level</span>
                    <span class="hil-card-badge indigo" id="hil-autonomy-badge">Moderate</span>
                </div>
                <div class="hil-autonomy-body">
                    <!-- three-marker labels -->
                    <div class="autonomy-labels">
                        <div class="autonomy-label-item restricted" id="albl-restricted">
                            <span class="autonomy-label-icon">🔒</span>
                            <span class="autonomy-label-text">Restricted</span>
                        </div>
                        <div class="autonomy-label-item moderate active" id="albl-moderate">
                            <span class="autonomy-label-icon">🛡️</span>
                            <span class="autonomy-label-text">Moderate</span>
                        </div>
                        <div class="autonomy-label-item full" id="albl-full">
                            <span class="autonomy-label-icon">⚡</span>
                            <span class="autonomy-label-text">Full Auto</span>
                        </div>
                    </div>

                    <!-- slider -->
                    <div class="autonomy-slider-wrap">
                        <input type="range" id="autonomy-range" class="autonomy-slider"
                               min="0" max="2" step="1" value="1" data-level="1">
                    </div>

                    <!-- current state pill -->
                    <div class="autonomy-current-state" id="autonomy-state-box">
                        <div class="autonomy-state-dot moderate" id="autonomy-state-dot"></div>
                        <div class="autonomy-state-desc">
                            <div class="autonomy-state-name" id="autonomy-state-name">Moderate</div>
                            <div class="autonomy-state-detail" id="autonomy-state-detail">
                                Auto-allows LOW/MEDIUM risk. Prompts on HIGH/CRITICAL.
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 2. Per-Risk Thresholds -->
            <div class="hil-card">
                <div class="hil-card-header">
                    <span class="hil-card-title">Risk Thresholds</span>
                    <span class="hil-card-badge indigo">Per-Tier</span>
                </div>
                <div class="hil-thresholds-body">
                    ${this._buildThresholdRow('LOW')}
                    ${this._buildThresholdRow('MEDIUM')}
                    ${this._buildThresholdRow('HIGH')}
                    ${this._buildThresholdRow('CRITICAL')}
                </div>
            </div>

            <!-- 3. Stats Row -->
            <div class="hil-card">
                <div class="hil-card-header">
                    <span class="hil-card-title">Session Stats</span>
                </div>
                <div class="hil-stats-row">
                    <div class="hil-stat">
                        <span class="hil-stat-value" id="hil-stat-auto">0</span>
                        <span class="hil-stat-label">Auto-ran</span>
                    </div>
                    <div class="hil-stat">
                        <span class="hil-stat-value" id="hil-stat-approved" style="color:#34d399">0</span>
                        <span class="hil-stat-label">Approved</span>
                    </div>
                    <div class="hil-stat">
                        <span class="hil-stat-value" id="hil-stat-denied" style="color:#ef4444">0</span>
                        <span class="hil-stat-label">Denied</span>
                    </div>
                </div>
                <div class="hil-budget-row" style="padding: 0 14px 12px; display:flex; gap:10px; font-size:10px;">
                    <div style="flex:1; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:6px; text-align:center;">
                        <span style="color:rgba(255,255,255,0.4)">Tokens:</span> <strong id="hil-stat-tokens" style="color:#e8e8ed">0</strong>
                    </div>
                    <div style="flex:1; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.05); border-radius:6px; padding:6px; text-align:center;">
                        <span style="color:rgba(255,255,255,0.4)">API Calls:</span> <strong id="hil-stat-apicalls" style="color:#e8e8ed">0</strong>
                    </div>
                </div>
            </div>

            <!-- Scheduled Cron Jobs -->
            <div class="hil-card">
                <div class="hil-card-header">
                    <span class="hil-card-title">Scheduled Jobs</span>
                    <button style="font-size:9px;background:none;border:none;color:rgba(255,255,255,0.25);cursor:pointer;padding:2px 6px;" onclick="hilPanel._fetchCronJobs()">Refresh</button>
                </div>
                <div class="hil-cron-body" id="hil-cron-body" style="padding:0; max-height:160px; overflow-y:auto; scrollbar-width:thin; scrollbar-color:rgba(99,102,241,0.2) transparent;">
                    <div class="hil-empty-queue">
                        <span class="hil-empty-icon">⏳</span>
                        <span>Loading jobs...</span>
                    </div>
                </div>
            </div>

            <!-- 4. Approval Queue -->
            <div class="hil-card">
                <div class="hil-card-header">
                    <span class="hil-card-title">Approval Queue</span>
                    <span class="hil-card-badge orange" id="hil-queue-count-badge">0 Pending</span>
                </div>
                <div class="hil-queue-body" id="hil-queue-body">
                    <div class="hil-empty-queue">
                        <span class="hil-empty-icon">✅</span>
                        <span>No pending approvals</span>
                    </div>
                </div>
            </div>

            <!-- 5. Risk Event Log -->
            <div class="hil-card">
                <div class="hil-card-header">
                    <span class="hil-card-title">Risk Event Stream</span>
                    <button style="font-size:9px;background:none;border:none;color:rgba(255,255,255,0.25);cursor:pointer;padding:2px 6px;" id="hil-clear-log">Clear</button>
                </div>
                <div class="hil-log-body" id="hil-log-body">
                    <div class="hil-empty-queue" style="padding:20px">
                        <span class="hil-empty-icon">📡</span>
                        <span>Waiting for events...</span>
                    </div>
                </div>
            </div>

        </div>
        `;
    }

    _buildThresholdRow(risk) {
        const colours = { LOW: 'low', MEDIUM: 'medium', HIGH: 'high', CRITICAL: 'critical' };
        const icons   = { LOW: '🟢', MEDIUM: '🟡', HIGH: '🟠', CRITICAL: '🔴' };
        const current = this.thresholds[risk];
        return `
        <div class="threshold-row" id="thr-row-${risk}">
            <div class="threshold-row-header">
                <label class="threshold-label">
                    ${icons[risk]}
                    <span>${risk}</span>
                    <span class="risk-badge-sm ${colours[risk]}">${risk}</span>
                </label>
                <span class="threshold-value-badge ${current}" id="thr-val-${risk}">${current.toUpperCase()}</span>
            </div>
            <div class="threshold-controls">
                <button class="threshold-btn ${current === 'auto' ? 'active-auto' : ''}"
                        data-risk="${risk}" data-action="auto" id="thr-${risk}-auto">Auto</button>
                <button class="threshold-btn ${current === 'prompt' ? 'active-prompt' : ''}"
                        data-risk="${risk}" data-action="prompt" id="thr-${risk}-prompt">Prompt</button>
                <button class="threshold-btn ${current === 'block' ? 'active-block' : ''}"
                        data-risk="${risk}" data-action="block" id="thr-${risk}-block">Block</button>
            </div>
        </div>`;
    }

    /* ── Events ─────────────────────────────────────────────────────── */
    _bindEvents() {
        // Trigger tab
        this.trigger.addEventListener('click', () => this.togglePanel());

        // Close btn
        document.getElementById('hil-close-btn')?.addEventListener('click', () => this.closePanel());

        // Autonomy slider
        const slider = document.getElementById('autonomy-range');
        slider?.addEventListener('input', (e) => {
            const lvl = ['restricted', 'moderate', 'full'][parseInt(e.target.value)];
            this._applyAutonomyUI(lvl);
        });
        slider?.addEventListener('change', (e) => {
            const lvl = ['restricted', 'moderate', 'full'][parseInt(e.target.value)];
            this._sendAutonomy(lvl);
        });

        // Threshold buttons (delegated)
        document.getElementById('hil-panel')?.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-risk][data-action]');
            if (btn) {
                const risk   = btn.dataset.risk;
                const action = btn.dataset.action;
                this._setThreshold(risk, action);
            }
        });

        // Clear log
        document.getElementById('hil-clear-log')?.addEventListener('click', () => {
            this.eventLog = [];
            this._renderLog();
        });
    }

    /* ── Panel open/close ───────────────────────────────────────────── */
    togglePanel() {
        this.isOpen ? this.closePanel() : this.openPanel();
    }

    openPanel() {
        this.isOpen = true;
        this.panel.classList.add('open');
        this.trigger.classList.add('panel-open');
        this._syncAutonomyFromServer();
    }

    closePanel() {
        this.isOpen = false;
        this.panel.classList.remove('open');
        this.trigger.classList.remove('panel-open');
    }

    /* ── Autonomy Logic ─────────────────────────────────────────────── */
    _applyAutonomyUI(level) {
        this.currentAutonomy = level;
        const indexMap = { restricted: 0, moderate: 1, full: 2 };
        const idx = indexMap[level] ?? 1;

        const slider = document.getElementById('autonomy-range');
        if (slider) {
            slider.value = idx;
            slider.dataset.level = idx;
        }

        // Badge
        const badge = document.getElementById('hil-autonomy-badge');
        if (badge) badge.textContent = level.charAt(0).toUpperCase() + level.slice(1);

        // Label icons
        ['restricted', 'moderate', 'full'].forEach(l => {
            document.getElementById(`albl-${l}`)?.classList.toggle('active', l === level);
        });

        // State box
        const dot  = document.getElementById('autonomy-state-dot');
        const name = document.getElementById('autonomy-state-name');
        const desc = document.getElementById('autonomy-state-detail');

        if (dot) { dot.className = `autonomy-state-dot ${level}`; }
        if (name) name.textContent = level.charAt(0).toUpperCase() + level.slice(1);

        const descs = {
            restricted: 'Pauses before every action, even trivial ones.',
            moderate:   'Auto-allows LOW/MEDIUM risk. Prompts on HIGH/CRITICAL.',
            full:       'Fully autonomous. All tools auto-execute without prompting.',
        };
        if (desc) desc.textContent = descs[level] || '';

        // Also sync the autonomy-btn elements in the main agent chat header
        document.querySelectorAll('.autonomy-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.level === level);
        });
    }

    async _sendAutonomy(level) {
        try {
            await fetch('/api/agent/autonomy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level }),
            });
            this._addLog('auto', `Autonomy set to ${level.toUpperCase()}`);
        } catch (err) {
            console.warn('[HIL] autonomy send failed:', err);
        }
    }

    async _syncAutonomyFromServer() {
        try {
            const r = await fetch('/api/agent/status');
            if (!r.ok) return;
            const d = await r.json();
            if (d.autonomy_level) this._applyAutonomyUI(d.autonomy_level);
        } catch { /* offline */ }
    }

    /* ── Thresholds ──────────────────────────────────────────────────── */
    _setThreshold(risk, action) {
        this.thresholds[risk] = action;

        // Update button styles
        ['auto', 'prompt', 'block'].forEach(a => {
            const btn = document.getElementById(`thr-${risk}-${a}`);
            if (!btn) return;
            btn.className = `threshold-btn${action === a ? ` active-${a}` : ''}`;
        });

        // Value badge
        const vb = document.getElementById(`thr-val-${risk}`);
        if (vb) {
            vb.className = `threshold-value-badge ${action}`;
            vb.textContent = action.toUpperCase();
        }

        this._addLog('auto', `${risk} risk → ${action.toUpperCase()}`);
        this._pushThresholdsToServer();
    }

    async _pushThresholdsToServer() {
        try {
            await fetch('/api/hil/thresholds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.thresholds),
            });
        } catch { /* server may not have this endpoint yet */ }
    }

    /* ── Approval Queue ──────────────────────────────────────────────── */
    addPendingApproval({ id, tool, action, risk, timeout_secs = 30 }) {
        const item = { id, tool, action, risk, timeout_secs, startTs: Date.now() };
        this.pendingApprovals.push(item);
        this._renderQueue();
        this._updateCountBadge();
        if (!this.isOpen && this.pendingApprovals.length > 0) this.openPanel();
        this._startCountdown(item);
    }

    _startCountdown(item) {
        const timer = setInterval(() => {
            const elapsed = (Date.now() - item.startTs) / 1000;
            const pct = Math.max(0, 100 - (elapsed / item.timeout_secs) * 100);
            const fill = document.getElementById(`atf-${item.id}`);
            if (fill) fill.style.width = `${pct}%`;

            const ct = document.getElementById(`act-${item.id}`);
            const remaining = Math.max(0, item.timeout_secs - elapsed);
            if (ct) ct.textContent = `${Math.ceil(remaining)}s`;

            if (elapsed >= item.timeout_secs) {
                clearInterval(timer);
                this._resolveApproval(item.id, 'auto-deny');
            }
        }, 1000);
        this._countdownTimers[item.id] = timer;
    }

    _resolveApproval(id, verdict) {
        clearInterval(this._countdownTimers[id]);
        delete this._countdownTimers[id];

        const idx = this.pendingApprovals.findIndex(a => a.id === id);
        if (idx === -1) return;
        const item = this.pendingApprovals.splice(idx, 1)[0];

        if (verdict === 'allow') {
            this.stats.approved++;
            this._addLog('allowed', `${item.tool}.${item.action} allowed`);
        } else {
            this.stats.denied++;
            this._addLog('denied', `${item.tool}.${item.action} denied`);
        }

        this._renderQueue();
        this._renderStats();
        this._updateCountBadge();

        // Notify server of the decision
        this._sendApprovalDecision(id, verdict === 'allow');
    }

    async _sendApprovalDecision(id, approved) {
        try {
            await fetch('/api/hil/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request_id: id, approved }),
            });
        } catch { /* server may not have endpoint yet */ }
    }

    _renderQueue() {
        const body = document.getElementById('hil-queue-body');
        const dashQueue = document.getElementById('hil-dash-queue');
        const dashCount = document.getElementById('hil-count');

        if (dashCount) dashCount.textContent = this.pendingApprovals.length;

        if (dashQueue) {
            if (this.pendingApprovals.length === 0) {
                dashQueue.innerHTML = `
                    <div class="hil-empty-dash">
                        <span class="empty-icon">☕</span>
                        <p>No pending approvals. Stuart is operating within autonomy limits.</p>
                    </div>`;
            } else {
                dashQueue.innerHTML = this.pendingApprovals.map(item => `
                    <div class="hil-dash-card">
                        <div class="dash-card-header">
                            <span class="dash-card-tool">${item.tool}</span>
                            <span class="dash-card-risk ${item.risk}">${item.risk}</span>
                        </div>
                        <div class="dash-card-action">Requested: ${item.action}</div>
                        <div class="dash-card-btns">
                            <button class="dash-btn allow" onclick="hilPanel._resolveApproval('${item.id}','allow')">APPROVE</button>
                            <button class="dash-btn deny" onclick="hilPanel._resolveApproval('${item.id}','deny')">DENY</button>
                        </div>
                    </div>
                `).join('');
            }
        }

        if (!body) return;

        const countBadge = document.getElementById('hil-queue-count-badge');
        if (countBadge) countBadge.textContent = `${this.pendingApprovals.length} Pending`;

        if (this.pendingApprovals.length === 0) {
            body.innerHTML = `<div class="hil-empty-queue">
                <span class="hil-empty-icon">✅</span>
                <span>No pending approvals</span>
            </div>`;
            return;
        }

        body.innerHTML = this.pendingApprovals.map(item => `
            <div class="hil-approval-item" id="aitem-${item.id}">
                <div class="approval-meta">
                    <div>
                        <div class="approval-tool">${item.tool}</div>
                        <div class="approval-action-text">.${item.action}</div>
                    </div>
                    <span class="approval-risk-pill ${item.risk}">${item.risk}</span>
                </div>
                <div class="approval-timer-bar">
                    <div class="approval-timer-fill" id="atf-${item.id}" style="width:100%"></div>
                </div>
                <div class="approval-countdown">
                    ⏱ Auto-deny in <strong id="act-${item.id}">${item.timeout_secs}s</strong>
                </div>
                <div class="approval-actions">
                    <button class="approval-btn allow" onclick="hilPanel._resolveApproval('${item.id}','allow')">✅ Allow</button>
                    <button class="approval-btn deny"  onclick="hilPanel._resolveApproval('${item.id}','deny')">❌ Deny</button>
                </div>
            </div>
        `).join('');
    }

    _updateCountBadge() {
        const n = this.pendingApprovals.length;
        if (!this.countBadge) return;
        this.countBadge.textContent = n;
        this.countBadge.classList.toggle('visible', n > 0);
    }

    /* ── Event Log ───────────────────────────────────────────────────── */
    _addLog(type, text) {
        const ts = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        this.eventLog.unshift({ type, text, ts });
        if (this.eventLog.length > 50) this.eventLog.pop();
        this._renderLog();
    }

    _renderLog() {
        const body = document.getElementById('hil-log-body');
        if (!body) return;
        if (this.eventLog.length === 0) {
            body.innerHTML = `<div class="hil-empty-queue" style="padding:20px">
                <span class="hil-empty-icon">📡</span>
                <span>Waiting for events...</span>
            </div>`;
            return;
        }
        body.innerHTML = this.eventLog.slice(0, 20).map(e => `
            <div class="hil-log-entry">
                <div class="log-dot ${e.type}"></div>
                <div class="log-content">
                    <div class="log-text">${e.text}</div>
                    <div class="log-time">${e.ts}</div>
                </div>
            </div>
        `).join('');
    }

    /* ── Stats ───────────────────────────────────────────────────────── */
    _renderStats() {
        const s = this.stats;
        ['auto', 'approved', 'denied'].forEach(k => {
            const el = document.getElementById(`hil-stat-${k}`);
            if (el) el.textContent = s[k];
        });
    }
    
    /* ── Cron & Budget ───────────────────────────────────────────────── */
    async _fetchCronJobs() {
        try {
            const res = await fetch('/api/agent/cron');
            if (!res.ok) return;
            const data = await res.json();
            this._renderCronJobs(data.jobs || []);
        } catch { /* silent */ }
    }

    _renderCronJobs(jobs) {
        const container = document.getElementById('hil-cron-body');
        if (!container) return;

        if (jobs.length === 0) {
            container.innerHTML = `
                <div class="hil-empty-queue" style="padding:20px;">
                    <span class="hil-empty-icon">🛌</span>
                    <span>No scheduled jobs.</span>
                </div>`;
            return;
        }

        container.innerHTML = jobs.map(j => `
            <div style="padding:10px 14px; border-bottom:1px solid rgba(255,255,255,0.04); display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div style="font-size:11px; font-weight:700; color:#e8e8ed; margin-bottom:4px;">${j.prompt}</div>
                    <div style="font-size:9px; color:rgba(255,255,255,0.4); font-family:monospace;">${j.time_str} • ${j.job_type}</div>
                </div>
                <button onclick="hilPanel.deleteCronJob('${j.id}')" style="background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.25); border-radius:6px; padding:4px 8px; font-size:9px; font-weight:700; cursor:pointer;">✕</button>
            </div>
        `).join('');
    }

    async deleteCronJob(jobId) {
        try {
            const res = await fetch(\`/api/agent/cron/\${jobId}\`, { method: 'DELETE' });
            if (res.ok) {
                this._addLog('auto', \`Cron job \${jobId.substring(0,8)} removed.\`);
                this._fetchCronJobs();
            }
        } catch(e) {
            console.error('Failed to delete cron', e);
        }
    }

    /* ── Server Polling ──────────────────────────────────────────────── */
    _startPolling() {
        this._pollTimer = setInterval(() => this._poll(), 8000);
        this._poll();
    }

    async _poll() {
        try {
            // Sync autonomy level
            const r = await fetch('/api/agent/status');
            if (r.ok) {
                const d = await r.json();
                if (d.autonomy_level && d.autonomy_level !== this.currentAutonomy) {
                    this._applyAutonomyUI(d.autonomy_level);
                }
            }
        } catch { /* silent */ }

        try {
            // Poll for pending approval requests from server
            const r2 = await fetch('/api/hil/queue');
            if (r2.ok) {
                const d2 = await r2.json();
                if (d2.pending && Array.isArray(d2.pending)) {
                    for (const item of d2.pending) {
                        const alreadyExists = this.pendingApprovals.some(a => a.id === item.id);
                        if (!alreadyExists) {
                            this.addPendingApproval(item);
                        }
                    }
                }
            }
        } catch { /* server endpoint may not be ready */ }

        try {
            // Poll budget stats
            const rb = await fetch('/api/agent/budget');
            if (rb.ok) {
                const db = await rb.json();
                const tok = document.getElementById('hil-stat-tokens');
                const api = document.getElementById('hil-stat-apicalls');
                if (tok) tok.textContent = (db.session_used || 0).toLocaleString();
                if (api) api.textContent = (db.total_api_calls || 0).toLocaleString();
            }
        } catch { /* silent */ }
        
        // Auto-refresh cron jobs periodically if panel is open
        if (this.isOpen) {
            this._fetchCronJobs();
        }
    }

    destroy() {
        if (this._pollTimer) clearInterval(this._pollTimer);
        Object.values(this._countdownTimers).forEach(clearInterval);
    }
}

const hilPanel = new HILPanel();
window.hilPanel = hilPanel;
export default hilPanel;
export { HILPanel };
