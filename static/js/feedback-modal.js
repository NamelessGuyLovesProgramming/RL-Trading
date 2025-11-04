/**
 * Feedback Modal System
 * Handles 6-criteria trade evaluation with star ratings
 */

class FeedbackModal {
    constructor() {
        this.isOpen = false;
        this.currentTrade = null;
        this.ratings = {
            entry_timing: 0,
            pattern_recognition: 0,
            sl_placement: 0,
            tp_placement: 0,
            liquidity_sweeps: 0,
            volume_analysis: 0
        };
        this.notes = '';

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
                            Bewerte diesen Trade nach 6 Kriterien
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
                                <div class="trade-info-label">Entry</div>
                                <div class="trade-info-value" id="tradeEntry">-</div>
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
                        <!-- Criteria -->
                        <div class="feedback-criteria">
                            <!-- Entry Timing -->
                            <div class="feedback-criterion">
                                <div class="criterion-header">
                                    <span class="criterion-icon">📍</span>
                                    <span class="criterion-title">Entry-Timing</span>
                                </div>
                                <div class="criterion-description">
                                    Hat die KI auf Session-Grenzen geachtet?
                                </div>
                                <div class="star-rating" data-criterion="entry_timing">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                                <div class="criterion-hint" id="hint-entry_timing"></div>
                            </div>

                            <!-- Pattern Recognition -->
                            <div class="feedback-criterion">
                                <div class="criterion-header">
                                    <span class="criterion-icon">📈</span>
                                    <span class="criterion-title">Pattern-Erkennung</span>
                                </div>
                                <div class="criterion-description">
                                    Wurden FVG, Order Blocks richtig erkannt?
                                </div>
                                <div class="star-rating" data-criterion="pattern_recognition">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                                <div class="criterion-hint" id="hint-pattern_recognition"></div>
                            </div>

                            <!-- Stop Loss -->
                            <div class="feedback-criterion">
                                <div class="criterion-header">
                                    <span class="criterion-icon">🛑</span>
                                    <span class="criterion-title">Stop-Loss Platzierung</span>
                                </div>
                                <div class="criterion-description">
                                    Ist SL unter/über Session H/L platziert?
                                </div>
                                <div class="star-rating" data-criterion="sl_placement">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                                <div class="criterion-hint" id="hint-sl_placement"></div>
                            </div>

                            <!-- Take Profit -->
                            <div class="feedback-criterion">
                                <div class="criterion-header">
                                    <span class="criterion-icon">🎯</span>
                                    <span class="criterion-title">Take-Profit Platzierung</span>
                                </div>
                                <div class="criterion-description">
                                    TP bei Liquidity Zone / realistisch?
                                </div>
                                <div class="star-rating" data-criterion="tp_placement">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                                <div class="criterion-hint" id="hint-tp_placement"></div>
                            </div>

                            <!-- Liquidity Sweeps -->
                            <div class="feedback-criterion">
                                <div class="criterion-header">
                                    <span class="criterion-icon">💧</span>
                                    <span class="criterion-title">Liquidity Sweeps</span>
                                </div>
                                <div class="criterion-description">
                                    Wurden Sweeps erkannt und genutzt?
                                </div>
                                <div class="star-rating" data-criterion="liquidity_sweeps">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                                <div class="criterion-hint" id="hint-liquidity_sweeps"></div>
                            </div>

                            <!-- Volume Analysis -->
                            <div class="feedback-criterion">
                                <div class="criterion-header">
                                    <span class="criterion-icon">📊</span>
                                    <span class="criterion-title">Volume Analyse</span>
                                </div>
                                <div class="criterion-description">
                                    Volume-Spikes beachtet?
                                </div>
                                <div class="star-rating" data-criterion="volume_analysis">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                                <div class="criterion-hint" id="hint-volume_analysis"></div>
                            </div>
                        </div>

                        <!-- Notes -->
                        <div class="feedback-notes">
                            <label for="feedbackNotes">Notizen (optional)</label>
                            <textarea
                                id="feedbackNotes"
                                placeholder="Z.B. 'Zu früh eingestiegen, sollte auf Session Close warten...'"
                            ></textarea>
                        </div>

                        <!-- Overall Score -->
                        <div class="feedback-overall-score">
                            <div class="overall-score-label">Gesamt-Score</div>
                            <div class="overall-score-value">
                                <span id="overallScoreValue">0.0</span>
                                <span>/</span>
                                <span>5.0</span>
                                <span class="overall-score-stars" id="overallScoreStars"></span>
                            </div>
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

        // Modal overlay (close on outside click)
        const overlay = document.getElementById('feedbackModalOverlay');
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.hide();
            }
        });

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

        // Star ratings
        document.querySelectorAll('.star-rating').forEach(container => {
            const criterion = container.dataset.criterion;
            const stars = container.querySelectorAll('.star');

            stars.forEach(star => {
                // Click
                star.addEventListener('click', () => {
                    const value = parseInt(star.dataset.value);
                    this.setRating(criterion, value);
                });

                // Hover
                star.addEventListener('mouseenter', () => {
                    const value = parseInt(star.dataset.value);
                    this.highlightStars(criterion, value);
                });
            });

            // Mouse leave - restore actual rating
            container.addEventListener('mouseleave', () => {
                this.highlightStars(criterion, this.ratings[criterion]);
            });
        });

        // Notes
        document.getElementById('feedbackNotes').addEventListener('input', (e) => {
            this.notes = e.target.value;
        });
    }

    setRating(criterion, value) {
        this.ratings[criterion] = value;
        this.highlightStars(criterion, value);
        this.updateOverallScore();
    }

    highlightStars(criterion, value) {
        const container = document.querySelector(`.star-rating[data-criterion="${criterion}"]`);
        const stars = container.querySelectorAll('.star');

        stars.forEach((star, index) => {
            if (index < value) {
                star.textContent = '★';
                star.classList.add('active');
            } else {
                star.textContent = '☆';
                star.classList.remove('active');
            }
        });
    }

    updateOverallScore() {
        const ratings = Object.values(this.ratings);
        const avg = ratings.reduce((a, b) => a + b, 0) / ratings.length;

        document.getElementById('overallScoreValue').textContent = avg.toFixed(1);

        // Update stars
        const fullStars = Math.floor(avg);
        let starsHTML = '';
        for (let i = 0; i < 5; i++) {
            starsHTML += i < fullStars ? '★' : '☆';
        }
        document.getElementById('overallScoreStars').textContent = starsHTML;
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

    updateHints(hints) {
        Object.keys(hints).forEach(criterion => {
            const hintEl = document.getElementById(`hint-${criterion}`);
            if (!hintEl) return;

            const hintData = hints[criterion];
            const suggested = hintData.suggested_stars;

            // Determine hint class
            let hintClass = '';
            if (suggested >= 4) hintClass = '';
            else if (suggested === 3) hintClass = 'warning';
            else hintClass = 'error';

            hintEl.className = `criterion-hint ${hintClass}`;
            hintEl.innerHTML = `
                <span class="icon">💡</span>
                <span>${hintData.hint}</span>
            `;

            // Auto-set suggested rating
            this.setRating(criterion, suggested);
        });
    }

    save() {
        const evaluation = {
            trade_id: this.currentTrade.trade_id,
            ratings: { ...this.ratings },
            notes: this.notes,
            overall_score: Object.values(this.ratings).reduce((a, b) => a + b, 0) / 6,
            timestamp: new Date().toISOString()
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
        // Reset ratings
        Object.keys(this.ratings).forEach(key => {
            this.ratings[key] = 0;
            this.highlightStars(key, 0);
        });

        // Reset notes
        this.notes = '';
        document.getElementById('feedbackNotes').value = '';

        // Reset overall score
        this.updateOverallScore();

        // Clear hints
        document.querySelectorAll('.criterion-hint').forEach(el => {
            el.innerHTML = '';
            el.className = 'criterion-hint';
        });
    }
}

// Initialize
let feedbackModal;
document.addEventListener('DOMContentLoaded', () => {
    feedbackModal = new FeedbackModal();
    window.feedbackModal = feedbackModal; // Make globally accessible

    console.log('[FeedbackModal] Ready');
});
