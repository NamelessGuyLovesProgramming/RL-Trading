/**
 * Feedback Modal System
 * 5-Level Rating: 👍👍 / 👍 / 😐 / 👎 / 👎👎
 */

class FeedbackModal {
    constructor() {
        this.isOpen = false;
        this.currentTrade = null;
        this.rating = null; // "very_good", "good", "ok", "bad", "very_bad"

        this.init();
    }

    init() {
        // Create modal HTML
        this.createModal();

        // Event listeners
        this.setupEventListeners();

        console.log('[FeedbackModal] Initialized');
    }

    createModal() {
        const modalHTML = `
            <!-- Notification Button -->
            <button class="trade-notification-button" id="tradeNotificationBtn">
                <span>🤖</span>
                <span>Trade bewerten</span>
            </button>

            <!-- Modal Overlay -->
            <div class="feedback-modal-overlay" id="feedbackModalOverlay">
                <div class="feedback-modal" id="feedbackModal">
                    <!-- Header -->
                    <div class="feedback-modal-header">
                        <h2 class="feedback-modal-title">
                            <span class="icon">⭐</span>
                            <span id="feedbackModalTitleText">Trade Bewertung</span>
                        </h2>
                        <p class="feedback-modal-subtitle" id="feedbackModalSubtitle">
                            Wie war dieser Trade?
                        </p>
                    </div>

                    <!-- Trade Info -->
                    <div class="feedback-trade-info" id="feedbackTradeInfo">
                        <div class="trade-info-grid">
                            <div class="trade-info-item">
                                <div class="trade-info-label">Aktion</div>
                                <div class="trade-info-value" id="tradeAction">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">Entry Preis</div>
                                <div class="trade-info-value" id="tradeEntry">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">Entry Zeit</div>
                                <div class="trade-info-value" id="tradeEntryTime">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">Exit Preis</div>
                                <div class="trade-info-value" id="tradeExit">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">Exit Zeit</div>
                                <div class="trade-info-value" id="tradeExitTime">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">Stop Loss</div>
                                <div class="trade-info-value" id="tradeSL">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">Take Profit</div>
                                <div class="trade-info-value" id="tradeTP">-</div>
                            </div>
                            <div class="trade-info-item">
                                <div class="trade-info-label">R:R Ratio</div>
                                <div class="trade-info-value" id="tradeRR">-</div>
                            </div>
                        </div>
                    </div>

                    <!-- Body -->
                    <div class="feedback-modal-body">
                        <!-- 5-Level Rating Buttons -->
                        <div class="feedback-rating-buttons">
                            <button class="rating-btn rating-btn-very-good" data-rating="very_good">
                                <span class="rating-icon">👍👍</span>
                                <span class="rating-label">Sehr gut</span>
                                <span class="rating-desc">Perfektes Setup - Lehrbuch-Trade</span>
                            </button>
                            <button class="rating-btn rating-btn-good" data-rating="good">
                                <span class="rating-icon">👍</span>
                                <span class="rating-label">Gut</span>
                                <span class="rating-desc">Solide Entscheidung</span>
                            </button>
                            <button class="rating-btn rating-btn-ok" data-rating="ok">
                                <span class="rating-icon">😐</span>
                                <span class="rating-label">OK</span>
                                <span class="rating-desc">Neutral - weder gut noch schlecht</span>
                            </button>
                            <button class="rating-btn rating-btn-bad" data-rating="bad">
                                <span class="rating-icon">👎</span>
                                <span class="rating-label">Schlecht</span>
                                <span class="rating-desc">Fehler - nicht wiederholen</span>
                            </button>
                            <button class="rating-btn rating-btn-very-bad" data-rating="very_bad">
                                <span class="rating-icon">👎👎</span>
                                <span class="rating-label">Sehr schlecht</span>
                                <span class="rating-desc">Schwerer Fehler - wichtige Lektion</span>
                            </button>
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="feedback-modal-footer">
                        <button class="btn btn-danger" id="feedbackDeleteBtn" style="margin-right: auto;">
                            <span>🗑️</span>
                            <span>Löschen</span>
                        </button>
                        <button class="btn btn-secondary" id="feedbackCancelBtn">
                            <span>Abbrechen</span>
                        </button>
                        <button class="btn btn-primary" id="feedbackSaveBtn">
                            <span>💾</span>
                            <span>Speichern</span>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Append to body
        const container = document.createElement('div');
        container.innerHTML = modalHTML;
        document.body.appendChild(container);
    }

    setupEventListeners() {
        // Notification button
        const notifBtn = document.getElementById('tradeNotificationBtn');
        notifBtn.addEventListener('click', () => this.show());

        // ⚠️ FIX: Modal darf NICHT durch Außenklick geschlossen werden
        // Modal kann nur durch X-Button, Speichern oder Löschen geschlossen werden
        // (Overlay Click Listener entfernt)

        // Cancel button
        document.getElementById('feedbackCancelBtn').addEventListener('click', () => {
            this.hide();
        });

        // Save button
        document.getElementById('feedbackSaveBtn').addEventListener('click', () => {
            this.save();
        });

        // Delete button
        document.getElementById('feedbackDeleteBtn').addEventListener('click', () => {
            this.delete();
        });

        // Rating buttons
        document.querySelectorAll('.rating-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const rating = btn.dataset.rating;
                this.setRating(rating);
            });
        });
    }

    setRating(rating) {
        // Remove active class from all buttons
        document.querySelectorAll('.rating-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        // Add active class to selected button
        const selectedBtn = document.querySelector(`.rating-btn[data-rating="${rating}"]`);
        if (selectedBtn) {
            selectedBtn.classList.add('active');
        }

        // Store rating
        this.rating = rating;

        console.log(`[FeedbackModal] Rating set to: ${rating}`);
    }

    showNotification(tradeData) {
        const btn = document.getElementById('tradeNotificationBtn');
        btn.classList.add('active');
        this.currentTrade = tradeData;

        // Auto-open after 2 seconds if not clicked
        setTimeout(() => {
            if (btn.classList.contains('active')) {
                this.show();
            }
        }, 2000);
    }

    hideNotification() {
        document.getElementById('tradeNotificationBtn').classList.remove('active');
    }

    show(tradeData = null) {
        if (tradeData) {
            this.currentTrade = tradeData;
        }

        if (!this.currentTrade) {
            console.error('[FeedbackModal] No trade data');
            return;
        }

        // Update modal content
        this.updateModalContent();

        // Show modal
        document.getElementById('feedbackModalOverlay').classList.add('active');
        this.isOpen = true;

        // Hide notification
        this.hideNotification();

        console.log('[FeedbackModal] Opened for trade:', this.currentTrade.trade_id);
    }

    hide() {
        document.getElementById('feedbackModalOverlay').classList.remove('active');
        this.isOpen = false;
        this.reset();
    }

    updateModalContent() {
        const trade = this.currentTrade;

        // Title
        const isAI = trade.source === 'ai' || trade.source === 'training';
        document.getElementById('feedbackModalTitleText').textContent =
            isAI ? `🤖 KI Trade Bewertung - ${trade.trade_id}` : `⭐ Dein Trade - ${trade.trade_id}`;

        // Trade Info
        document.getElementById('tradeAction').textContent = trade.action.toUpperCase();
        document.getElementById('tradeAction').className = `trade-info-value ${trade.action}`;

        document.getElementById('tradeEntry').textContent = `$${trade.entry_price.toFixed(2)}`;

        // Entry Zeit (von entry_time oder timestamp)
        const entryTime = trade.entry_time || trade.timestamp || '-';
        document.getElementById('tradeEntryTime').textContent = entryTime !== '-' ? new Date(entryTime).toLocaleString('de-DE') : '-';

        // Exit Preis und Zeit
        document.getElementById('tradeExit').textContent = trade.close_price ? `$${trade.close_price.toFixed(2)}` : '-';
        const exitTime = trade.close_time || trade.exit_time || '-';
        document.getElementById('tradeExitTime').textContent = exitTime !== '-' ? new Date(exitTime).toLocaleString('de-DE') : '-';

        document.getElementById('tradeSL').textContent = `$${trade.sl_price.toFixed(2)}`;
        document.getElementById('tradeTP').textContent = `$${trade.tp_price.toFixed(2)}`;

        // Calculate R:R
        const slDist = Math.abs(trade.entry_price - trade.sl_price);
        const tpDist = Math.abs(trade.tp_price - trade.entry_price);
        const rr = tpDist / slDist;
        document.getElementById('tradeRR').textContent = `1:${rr.toFixed(1)}`;
        document.getElementById('tradeRR').className = `trade-info-value ${rr >= 2 ? 'positive' : ''}`;

        // Hints (if available)
        if (trade.hints) {
            this.updateHints(trade.hints);
        }
    }

    save() {
        // Validate rating
        if (!this.rating) {
            alert('Bitte bewerte den Trade!');
            return;
        }

        // Convert rating to numerical value (-1.0 to +1.0)
        const ratingValue = {
            'very_good': +1.0,
            'good': +0.5,
            'ok': 0.0,
            'bad': -0.5,
            'very_bad': -1.0
        }[this.rating];

        const evaluation = {
            trade_id: this.currentTrade.trade_id,
            rating: this.rating,  // "very_good", "good", "ok", "bad", "very_bad"
            rating_value: ratingValue,  // +1.0, +0.5, 0.0, -0.5, -1.0
            timestamp: new Date().toISOString(),
            // Trade-Daten für vollständige Speicherung
            action: this.currentTrade.action,
            entry_price: this.currentTrade.entry_price,
            sl_price: this.currentTrade.sl_price,
            tp_price: this.currentTrade.tp_price,
            close_price: this.currentTrade.close_price,
            realized_pnl: this.currentTrade.realized_pnl,
            source: this.currentTrade.source || 'user'
        };

        console.log('[FeedbackModal] Saving evaluation:', evaluation);

        // Emit to server via WebSocket
        if (window.chartWs && window.chartWs.readyState === WebSocket.OPEN) {
            window.chartWs.send(JSON.stringify({
                type: 'trade_feedback',
                data: evaluation
            }));
        }

        // Callback if defined
        if (this.onSave) {
            this.onSave(evaluation);
        }

        this.hide();
    }

    delete() {
        if (!this.currentTrade) {
            console.error('[FeedbackModal] No trade to delete');
            return;
        }

        // Confirmation Dialog
        if (!confirm(`Feedback für Trade ${this.currentTrade.trade_id} wirklich löschen?\n\nDieser Vorgang kann nicht rückgängig gemacht werden.`)) {
            return;
        }

        console.log('[FeedbackModal] Deleting feedback:', this.currentTrade.trade_id);

        // Send delete command via WebSocket
        if (window.chartWs && window.chartWs.readyState === WebSocket.OPEN) {
            window.chartWs.send(JSON.stringify({
                type: 'delete_feedback',
                trade_id: this.currentTrade.trade_id
            }));

            console.log('[FeedbackModal] Delete request sent');
        } else {
            console.error('[FeedbackModal] WebSocket not connected');
            alert('Fehler: Keine Verbindung zum Server!');
            return;
        }

        // Callback if defined
        if (this.onDelete) {
            this.onDelete(this.currentTrade.trade_id);
        }

        this.hide();
    }

    reset() {
        // Reset rating
        this.rating = null;

        // Remove active class from all buttons
        document.querySelectorAll('.rating-btn').forEach(btn => {
            btn.classList.remove('active');
        });

        console.log('[FeedbackModal] Reset');
    }
}

// Initialize
let feedbackModal;
document.addEventListener('DOMContentLoaded', () => {
    feedbackModal = new FeedbackModal();
    window.feedbackModal = feedbackModal; // Make globally accessible

    console.log('[FeedbackModal] Ready');
});

// Global function for batch trading workflow
function openAIFeedbackModal(tradeData) {
    if (!window.feedbackModal) {
        console.error('[openAIFeedbackModal] Feedback modal not initialized');
        return;
    }

    // Convert batch trade data to modal format
    const modalTradeData = {
        trade_id: tradeData.trade_id,
        action: tradeData.action,
        entry_price: tradeData.position.entry_price,
        sl_price: tradeData.position.sl_price,
        tp_price: tradeData.position.tp_price,
        source: 'ai',
        reasoning: tradeData.reasoning,
        confidence: tradeData.confidence
    };

    console.log('[openAIFeedbackModal] Opening modal for batch trade:', modalTradeData);

    // Open modal
    window.feedbackModal.show(modalTradeData);

    // Hook: After save, resume chart playback
    window.feedbackModal.onSave = function(evaluation) {
        console.log('[openAIFeedbackModal] Feedback saved, resuming chart...');

        // Resume chart playback
        if (window.togglePlay && !window.isPlaying) {
            setTimeout(() => {
                togglePlay(); // Resume chart
                console.log('[openAIFeedbackModal] Chart resumed');
            }, 500);
        }

        // Send feedback to training service (5-Level System)
        if (window.chartWs && window.chartWs.readyState === WebSocket.OPEN) {
            window.chartWs.send(JSON.stringify({
                type: 'batch_feedback',
                trade_id: evaluation.trade_id,
                rating: evaluation.rating,  // "very_good", "good", "ok", "bad", "very_bad"
                rating_value: evaluation.rating_value  // +1.0, +0.5, 0.0, -0.5, -1.0
            }));
        }

        // Clear hook
        delete window.feedbackModal.onSave;
    };
}

// Make globally accessible
window.openAIFeedbackModal = openAIFeedbackModal;
