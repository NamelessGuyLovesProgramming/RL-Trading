/**
 * Intelligent Zoom System für LightweightCharts
 * Garantiert dass beim Auszoomen immer Kerzen sichtbar sind
 */

class IntelligentZoomSystem {
    constructor(chart, candlestickSeries, currentTimeframe = '5m') {
        this.chart = chart;
        this.candlestickSeries = candlestickSeries;
        this.currentTimeframe = currentTimeframe;
        this.currentCandles = 200; // Aktuelle Anzahl geladener Kerzen
        this.minVisibleCandles = 50; // Minimum sichtbare Kerzen
        this.maxVisibleCandles = 2000; // Maximum für Performance
        this.isLoading = false;
        this.lastVisibleRange = null;

        this.setupZoomMonitoring();
    }

    setupZoomMonitoring() {
        // Überwache Änderungen der sichtbaren Zeitspanne
        this.chart.timeScale().subscribeVisibleLogicalRangeChange((newVisibleLogicalRange) => {
            if (newVisibleLogicalRange === null) return;

            this.handleVisibleRangeChange(newVisibleLogicalRange);
        });

        console.log('🔍 Intelligent Zoom System aktiviert');
    }

    handleVisibleRangeChange(visibleLogicalRange) {
        const { from, to } = visibleLogicalRange;
        const visibleCandleCount = Math.ceil(to - from);

        console.log(`📊 Sichtbare Kerzen: ${visibleCandleCount}, Geladen: ${this.currentCandles}`);

        // Check if we need more candles (user zoomed out)
        if (this.shouldLoadMoreCandles(visibleCandleCount)) {
            this.loadMoreCandles(visibleCandleCount);
        }

        // Check if we're running out of candles on the left side
        if (this.isNearLeftEdge(from)) {
            this.loadHistoricalCandles();
        }

        this.lastVisibleRange = visibleLogicalRange;
    }

    shouldLoadMoreCandles(visibleCandleCount) {
        // Lade mehr Kerzen wenn:
        // 1. User weit ausgezoomt hat (mehr als 80% der geladenen Kerzen sichtbar)
        // 2. Noch nicht das Maximum erreicht
        // 3. Nicht bereits am Laden
        const visibilityRatio = visibleCandleCount / this.currentCandles;

        return visibilityRatio > 0.8 &&
               this.currentCandles < this.maxVisibleCandles &&
               !this.isLoading;
    }

    isNearLeftEdge(fromIndex) {
        // Check if we're showing candles from the beginning (near left edge)
        return fromIndex <= 10; // 10 Kerzen Puffer zum Rand
    }

    async loadMoreCandles(visibleCandleCount) {
        if (this.isLoading) return;

        this.isLoading = true;
        console.log('📈 Lade mehr Kerzen für bessere Zoom-Erfahrung...');

        try {
            // Berechne wie viele Kerzen wir brauchen
            const targetCandles = Math.min(
                Math.max(visibleCandleCount * 2, this.currentCandles * 1.5),
                this.maxVisibleCandles
            );

            // API-Call für mehr Daten
            const response = await fetch('/api/chart/change_timeframe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    timeframe: this.currentTimeframe,
                    visible_candles: Math.ceil(targetCandles)
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                // Update Chart mit mehr Daten
                this.candlestickSeries.setData(result.data);
                this.currentCandles = result.data.length;

                console.log(`✅ Mehr Kerzen geladen: ${this.currentCandles} (war: ${this.currentCandles})`);

                // Toast-Benachrichtigung
                this.showZoomNotification(`Zoom erweitert: ${this.currentCandles} Kerzen verfügbar`);
            }
        } catch (error) {
            console.error('❌ Fehler beim Laden zusätzlicher Kerzen:', error);
        } finally {
            this.isLoading = false;
        }
    }

    async loadHistoricalCandles() {
        if (this.isLoading) return;

        this.isLoading = true;
        console.log('📚 Lade historische Daten (links erweitern)...');

        try {
            // Für historische Daten könnten wir einen separaten Endpunkt nutzen
            // Hier erstmal mehr Daten vom aktuellen Endpunkt
            const response = await fetch('/api/chart/change_timeframe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    timeframe: this.currentTimeframe,
                    visible_candles: this.currentCandles + 500 // Erweitere um 500 Kerzen
                })
            });

            const result = await response.json();

            if (result.status === 'success') {
                this.candlestickSeries.setData(result.data);
                this.currentCandles = result.data.length;

                console.log(`✅ Historische Daten geladen: ${this.currentCandles} Kerzen`);
                this.showZoomNotification(`Verlauf erweitert: ${this.currentCandles} Kerzen`);
            }
        } catch (error) {
            console.error('❌ Fehler beim Laden historischer Daten:', error);
        } finally {
            this.isLoading = false;
        }
    }

    updateTimeframe(newTimeframe) {
        this.currentTimeframe = newTimeframe;
        console.log(`🔄 Timeframe geändert zu: ${newTimeframe}`);
    }

    showZoomNotification(message) {
        // Erstelle eine schöne Toast-Benachrichtigung
        const toast = document.createElement('div');
        toast.className = 'zoom-toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: rgba(8, 153, 129, 0.9);
            color: white;
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 10000;
            animation: slideIn 0.3s ease-out;
        `;

        // CSS Animation hinzufügen
        if (!document.getElementById('zoom-toast-styles')) {
            const style = document.createElement('style');
            style.id = 'zoom-toast-styles';
            style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(toast);

        // Auto-remove nach 3 Sekunden
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Debugging-Methoden
    getStats() {
        return {
            currentTimeframe: this.currentTimeframe,
            currentCandles: this.currentCandles,
            isLoading: this.isLoading,
            lastVisibleRange: this.lastVisibleRange
        };
    }
}

// Global verfügbar machen
window.IntelligentZoomSystem = IntelligentZoomSystem;