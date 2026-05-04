/**
 * Toast Notification System — Stuart-AI
 * 
 * A non-blocking, stacking notification system that replaces all alert() calls.
 * Supports: success, error, warning, info types with auto-dismiss.
 * 
 * Usage:
 *   import toast from './toast.js';
 *   toast.success('Model updated', 'Switched to GPT-4o');
 *   toast.error('Connection failed', 'WebSocket closed unexpectedly');
 *   toast.warning('Missing field', 'Please select an AI provider');
 *   toast.info('Tip', 'Press Alt+V to enter vision mode');
 */

class ToastManager {
    constructor() {
        this.container = null;
        this.queue = [];
        this.maxVisible = 5;
        this.defaultDuration = 4000; // 4 seconds
    }

    _ensureContainer() {
        if (this.container) return;
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.setAttribute('role', 'alert');
        this.container.setAttribute('aria-live', 'polite');
        document.body.appendChild(this.container);
    }

    /**
     * Show a toast notification.
     * @param {'success'|'error'|'warning'|'info'} type
     * @param {string} title - Bold heading text
     * @param {string} [message] - Optional detail text
     * @param {number} [duration] - Auto-dismiss in ms (0 = no auto-dismiss)
     */
    show(type, title, message = '', duration = this.defaultDuration) {
        this._ensureContainer();

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;

        // Icon
        const iconEl = document.createElement('div');
        iconEl.className = 'toast-icon';
        iconEl.textContent = icons[type] || 'ℹ';

        // Body
        const bodyEl = document.createElement('div');
        bodyEl.className = 'toast-body';

        const titleEl = document.createElement('div');
        titleEl.className = 'toast-title';
        titleEl.textContent = title;
        bodyEl.appendChild(titleEl);

        if (message) {
            const msgEl = document.createElement('div');
            msgEl.className = 'toast-message';
            msgEl.textContent = message;
            bodyEl.appendChild(msgEl);
        }

        // Close button
        const closeEl = document.createElement('button');
        closeEl.className = 'toast-close';
        closeEl.innerHTML = '✕';
        closeEl.addEventListener('click', () => this._dismiss(toast));

        toast.appendChild(iconEl);
        toast.appendChild(bodyEl);
        toast.appendChild(closeEl);

        // Progress bar for auto-dismiss
        if (duration > 0) {
            const progressEl = document.createElement('div');
            progressEl.className = 'toast-progress';
            progressEl.style.animationDuration = `${duration}ms`;
            toast.appendChild(progressEl);
        }

        // Prepend (newest on top)
        this.container.prepend(toast);
        this.queue.push(toast);

        // Enforce max visible
        while (this.queue.length > this.maxVisible) {
            const oldest = this.queue.shift();
            this._dismiss(oldest);
        }

        // Auto-dismiss
        if (duration > 0) {
            toast._dismissTimer = setTimeout(() => {
                this._dismiss(toast);
            }, duration);
        }

        return toast;
    }

    _dismiss(toast) {
        if (!toast || toast._dismissed) return;
        toast._dismissed = true;

        if (toast._dismissTimer) {
            clearTimeout(toast._dismissTimer);
        }

        toast.classList.add('exiting');

        toast.addEventListener('animationend', () => {
            toast.remove();
            const idx = this.queue.indexOf(toast);
            if (idx > -1) this.queue.splice(idx, 1);
        }, { once: true });

        // Fallback removal if animation doesn't fire
        setTimeout(() => {
            if (toast.parentNode) toast.remove();
        }, 300);
    }

    // Convenience methods
    success(title, message, duration) {
        return this.show('success', title, message, duration);
    }

    error(title, message, duration = 6000) {
        return this.show('error', title, message, duration);
    }

    warning(title, message, duration = 5000) {
        return this.show('warning', title, message, duration);
    }

    info(title, message, duration) {
        return this.show('info', title, message, duration);
    }
}

const toast = new ToastManager();
export default toast;
export { ToastManager };
