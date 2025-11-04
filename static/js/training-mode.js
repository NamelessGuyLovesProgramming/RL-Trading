/**
 * Training Mode UI
 * Manages AI Trading Mode with automatic feedback
 */

class TrainingModeUI {
    constructor() {
        this.isActive = false;
        this.stats = {
            trades_count: 0,
            long_count: 0,
            short_count: 0,
            hold_count: 0,
            avg_confidence: 0.0
        };
        this.session_id = null;

        this.init();
    }

    init() {
        // Create UI Elements
        this.createUI();

        // Event Listeners
        this.setupEventListeners();

        // WebSocket Listeners
        this.setupWebSocketListeners();

        console.log('[TrainingMode] UI initialized');
    }

    createUI() {
        // Training Mode Toggle Button
        const button = document.createElement('button');
        button.id = 'aiModeToggleBtn';
        button.className = 'ai-mode-toggle-btn';
        button.innerHTML = `
            <span class="ai-icon">🤖</span>
            <span class="ai-text">KI Modus</span>
            <span class="ai-status"></span>
        `;

        // Stats Panel
        const statsPanel = document.createElement('div');
        statsPanel.id = 'aiStatsPanel';
        statsPanel.className = 'ai-stats-panel';
        statsPanel.style.display = 'none';
        statsPanel.innerHTML = `
            <div class="ai-stats-header">
                <span>🤖 KI Training Session</span>
                <span class="ai-session-id"></span>
            </div>
            <div class="ai-stats-grid">
                <div class="ai-stat">
                    <div class="ai-stat-label">Trades</div>
                    <div class="ai-stat-value" id="aiStatTrades">0</div>
                </div>
                <div class="ai-stat">
                    <div class="ai-stat-label">Long</div>
                    <div class="ai-stat-value green" id="aiStatLong">0</div>
                </div>
                <div class="ai-stat">
                    <div class="ai-stat-label">Short</div>
                    <div class="ai-stat-value red" id="aiStatShort">0</div>
                </div>
                <div class="ai-stat">
                    <div class="ai-stat-label">Hold</div>
                    <div class="ai-stat-value gray" id="aiStatHold">0</div>
                </div>
                <div class="ai-stat">
                    <div class="ai-stat-label">⭐ Confidence</div>
                    <div class="ai-stat-value" id="aiStatConfidence">0%</div>
                </div>
            </div>
        `;

        // Append to body
        document.body.appendChild(button);
        document.body.appendChild(statsPanel);
    }

    setupEventListeners() {
        const button = document.getElementById('aiModeToggleBtn');
        button.addEventListener('click', () => {
            this.toggle();
        });
    }

    setupWebSocketListeners() {
        // Listen for WebSocket messages
        window.addEventListener('websocket-message', (event) => {
            const message = event.detail;

            switch (message.type) {
                case 'ai_mode_toggled':
                    this.onModeToggled(message);
                    break;

                case 'ai_trade_executed':
                    this.onAITradeExecuted(message);
                    break;

                case 'ai_status':
                    this.onStatusUpdate(message);
                    break;
            }
        });

        console.log('[TrainingMode] WebSocket listeners registered');
    }

    toggle() {
        if (!window.chartWs || window.chartWs.readyState !== WebSocket.OPEN) {
            alert('Fehler: Keine Verbindung zum Server!');
            return;
        }

        console.log('[TrainingMode] Toggling AI Mode...');

        // Send toggle command
        window.chartWs.send(JSON.stringify({
            type: 'toggle_ai_mode'
        }));
    }

    onModeToggled(data) {
        this.isActive = data.is_active;
        this.session_id = data.session_id;
        this.stats = data.stats;

        console.log(`[TrainingMode] Mode toggled: ${this.isActive}`);

        // Update UI
        this.updateUI();

        // Show notification
        if (this.isActive) {
            this.showNotification('🤖 KI Modus AKTIV - KI analysiert jeden Skip!', 'success');
        } else {
            this.showNotification('KI Modus deaktiviert', 'info');
        }
    }

    onAITradeExecuted(data) {
        console.log(`[TrainingMode] AI Trade executed: ${data.trade_id}`);
        console.log(`[TrainingMode] Action: ${data.action}, Confidence: ${data.confidence}`);
        console.log(`[TrainingMode] Reasoning: ${data.reasoning}`);

        // Update Stats
        this.stats.trades_count++;
        if (data.action === 'long') this.stats.long_count++;
        if (data.action === 'short') this.stats.short_count++;

        this.updateUI();

        // Show Trade Notification
        this.showTradeNotification(data);

        // Auto-Open Feedback Modal
        if (data.auto_open_modal && window.feedbackModal) {
            // Warte 1 Sekunde damit User den Trade sieht
            setTimeout(() => {
                const tradeData = {
                    trade_id: data.trade_id,
                    source: 'ai',
                    action: data.action,
                    entry_price: data.position.entry_price,
                    sl_price: data.position.sl_price,
                    tp_price: data.position.tp_price,
                    hints: data.hints,
                    reasoning: data.reasoning,
                    confidence: data.confidence
                };

                window.feedbackModal.show(tradeData);
                console.log('[TrainingMode] Feedback Modal opened automatically');
            }, 1000);
        }
    }

    onStatusUpdate(data) {
        this.isActive = data.is_active;
        this.session_id = data.session_id;
        this.stats = data.stats;

        this.updateUI();
    }

    updateUI() {
        const button = document.getElementById('aiModeToggleBtn');
        const statsPanel = document.getElementById('aiStatsPanel');

        if (this.isActive) {
            button.classList.add('active');
            button.querySelector('.ai-status').textContent = 'AN';
            statsPanel.style.display = 'block';

            // Update Stats
            document.querySelector('.ai-session-id').textContent = this.session_id || '';
            document.getElementById('aiStatTrades').textContent = this.stats.trades_count;
            document.getElementById('aiStatLong').textContent = this.stats.long_count;
            document.getElementById('aiStatShort').textContent = this.stats.short_count;
            document.getElementById('aiStatHold').textContent = this.stats.hold_count;
            document.getElementById('aiStatConfidence').textContent =
                `${(this.stats.avg_confidence * 100).toFixed(0)}%`;
        } else {
            button.classList.remove('active');
            button.querySelector('.ai-status').textContent = 'AUS';
            statsPanel.style.display = 'none';
        }
    }

    showNotification(message, type = 'info') {
        // Simple notification at top of screen
        const notification = document.createElement('div');
        notification.className = `ai-notification ${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // Fade in
        setTimeout(() => notification.classList.add('show'), 10);

        // Remove after 3 seconds
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    showTradeNotification(data) {
        const actionEmoji = data.action === 'long' ? '📈' : '📉';
        const message = `${actionEmoji} KI ${data.action.toUpperCase()} @ $${data.position.entry_price.toFixed(2)}`;

        this.showNotification(message, 'trade');
    }

    requestStatus() {
        if (!window.chartWs || window.chartWs.readyState !== WebSocket.OPEN) {
            return;
        }

        window.chartWs.send(JSON.stringify({
            type: 'get_ai_status'
        }));
    }
}

// Initialize on page load
let trainingModeUI;
document.addEventListener('DOMContentLoaded', () => {
    trainingModeUI = new TrainingModeUI();
    window.trainingModeUI = trainingModeUI; // Make globally accessible

    console.log('[TrainingMode] Ready');

    // Request initial status after 2 seconds
    setTimeout(() => {
        if (window.chartWs && window.chartWs.readyState === WebSocket.OPEN) {
            trainingModeUI.requestStatus();
        }
    }, 2000);
});
