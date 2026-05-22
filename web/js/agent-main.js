import { StateManager } from './state-manager.js';
import { WebSocketHandler } from './websocket-handler.js';
import { ProviderManager } from './provider-manager.js';
import { ConfigManager } from './config-manager.js';
import agentChat from './agent-chat.js';
import hilPanel from './hil-panel.js';

// Initialize managers
const stateManager = new StateManager();
const webSocketHandler = new WebSocketHandler(stateManager);
const providerManager = new ProviderManager(stateManager, webSocketHandler);
const configManager = new ConfigManager(stateManager);

// Expose to window for inter-module integration
window.providerManager = providerManager;
window.configManager = configManager;

// --- Dependency Injection ---
webSocketHandler.setProviderManager(providerManager);

// Connect to backend
async function initAgent() {
    try {
        await webSocketHandler.connect();
        console.log("Agent Dashboard connected to backend.");
    } catch (error) {
        console.error("Failed to connect agent dashboard:", error);
    }

    // Initialize agent chat
    agentChat.init();
    
    // Initialize HIL Panel
    if (!window._hilPanelInitialized) {
        hilPanel.init();
        window.hilPanel = hilPanel;
        window._hilPanelInitialized = true;
    }
}

document.addEventListener('DOMContentLoaded', initAgent);
