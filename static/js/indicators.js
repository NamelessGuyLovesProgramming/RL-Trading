// ============================================================
// INDICATOR SYSTEM - Strategy Pattern + Singleton Manager
// ============================================================
// Architektur:
// - BaseIndicator: Abstract base class für alle Indikatoren
// - IndicatorManager: Singleton orchestriert Lifecycle
// - EMAIndicator: Konkrete Implementation
// ============================================================

console.log('📊 Indicators Module geladen');

// ============================================================
// BASE INDICATOR - Abstract Class
// ============================================================

class BaseIndicator {
    constructor(id, type, config = {}) {
        if (this.constructor === BaseIndicator) {
            throw new Error('BaseIndicator ist abstract und kann nicht direkt instanziiert werden');
        }

        this.id = id;
        this.type = type;
        this.config = config;
        this.visible = true;
        this.series = null; // LightweightCharts Series
        this.data = null;   // Cached calculated data

        console.log(`📊 Indikator erstellt: ${type} (ID: ${id})`);
    }

    // Abstract Methods - MÜSSEN von Subclasses implementiert werden
    calculate(data) {
        throw new Error('calculate() muss von Subclass implementiert werden');
    }

    render(chart) {
        throw new Error('render() muss von Subclass implementiert werden');
    }

    update(candle, allData) {
        throw new Error('update() muss von Subclass implementiert werden');
    }

    // Concrete Methods - Verfügbar für alle Indikatoren
    toggleVisibility() {
        this.visible = !this.visible;
        if (this.series) {
            this.series.applyOptions({ visible: this.visible });
            console.log(`👁️ ${this.type}(${this.id}) Visibility: ${this.visible}`);
        }
    }

    setConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        console.log(`⚙️ ${this.type}(${this.id}) Config updated:`, this.config);
    }

    destroy() {
        if (this.series && window.chart) {
            try {
                window.chart.removeSeries(this.series);
                console.log(`🗑️ ${this.type}(${this.id}) Series entfernt`);
            } catch (e) {
                console.warn(`⚠️ Fehler beim Entfernen von ${this.type}(${this.id}):`, e);
            }
        }
        this.series = null;
        this.data = null;
    }

    // Getter für UI-Label
    getDisplayName() {
        return `${this.type}(${this.config.period || ''})`;
    }

    // Serialize für localStorage
    serialize() {
        return {
            type: this.type,
            config: this.config
        };
    }
}

// ============================================================
// EMA INDICATOR - Exponential Moving Average
// ============================================================

class EMAIndicator extends BaseIndicator {
    constructor(id, config = { period: 9, color: '#000000' }) {
        super(id, 'EMA', config);

        // Validierung
        if (!this.config.period || this.config.period < 2) {
            this.config.period = 9;
        }
        if (!this.config.color) {
            this.config.color = '#000000';
        }
    }

    calculate(data) {
        const period = this.config.period;

        // Validierung: Genug Daten?
        if (!data || data.length < period) {
            console.warn(`⚠️ EMA(${period}): Nicht genug Daten (${data?.length || 0} < ${period})`);
            return [];
        }

        // No phantom candles - use all data directly
        const realData = data;

        if (realData.length < period) {
            console.warn(`⚠️ EMA(${period}): Nicht genug echte Kerzen (${realData.length} < ${period})`);
            return [];
        }

        const ema = [];
        const multiplier = 2 / (period + 1);

        // Schritt 1: SMA für ersten EMA-Wert (Seed)
        let sum = 0;
        for (let i = 0; i < period; i++) {
            sum += realData[i].close;
        }
        const initialEMA = sum / period;
        ema.push({ time: realData[period - 1].time, value: initialEMA });

        // Schritt 2: EMA für alle weiteren Kerzen
        for (let i = period; i < realData.length; i++) {
            const currentClose = realData[i].close;
            const prevEMA = ema[ema.length - 1].value;
            const currentEMA = (currentClose - prevEMA) * multiplier + prevEMA;

            ema.push({
                time: realData[i].time,
                value: currentEMA
            });
        }

        console.log(`✅ EMA(${period}) berechnet: ${ema.length} Werte`);
        this.data = ema; // Cache für Updates
        return ema;
    }

    render(chart) {
        if (!chart) {
            console.error('❌ EMA render: Chart nicht verfügbar');
            return;
        }

        // Hole aktuelle Candlestick-Daten
        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            console.warn('⚠️ EMA render: Keine Candlestick-Daten verfügbar');
            return;
        }

        // Berechne EMA
        const emaData = this.calculate(candleData);
        if (emaData.length === 0) {
            console.warn('⚠️ EMA render: Berechnung ergab keine Daten');
            return;
        }

        // Erstelle LineSeries
        try {
            this.series = chart.addLineSeries({
                color: this.config.color,
                lineWidth: 2,
                priceLineVisible: false,
                lastValueVisible: true,
                crosshairMarkerVisible: true,
                title: this.getDisplayName()
            });

            this.series.setData(emaData);
            this.series.applyOptions({ visible: this.visible });

            console.log(`✅ EMA(${this.config.period}) gerendert: ${emaData.length} Punkte`);
        } catch (e) {
            console.error(`❌ Fehler beim Rendern von EMA(${this.config.period}):`, e);
        }
    }

    update(candle, allData) {
        // Komplette Neuberechnung bei jedem Update (wie gewünscht)
        if (!allData || allData.length === 0) {
            console.warn('⚠️ EMA update: Keine Daten verfügbar');
            return;
        }

        const newEmaData = this.calculate(allData);

        if (this.series && newEmaData.length > 0) {
            try {
                this.series.setData(newEmaData);
                console.log(`🔄 EMA(${this.config.period}) updated: ${newEmaData.length} Punkte`);
            } catch (e) {
                console.error(`❌ Fehler beim Update von EMA(${this.config.period}):`, e);
            }
        }
    }

    // Override setConfig für Live-Update bei Änderungen
    setConfig(newConfig) {
        const oldPeriod = this.config.period;
        const oldColor = this.config.color;

        super.setConfig(newConfig);

        // Bei Period-Änderung: Neuberechnung nötig
        if (newConfig.period && newConfig.period !== oldPeriod) {
            const candleData = window.candlestickSeries?.data();
            if (candleData) {
                this.update(null, candleData);
            }
        }

        // Bei Color-Änderung: Nur Series-Option updaten
        if (newConfig.color && newConfig.color !== oldColor && this.series) {
            this.series.applyOptions({
                color: newConfig.color,
                title: this.getDisplayName()
            });
        }
    }
}

// ============================================================
// INDICATOR MANAGER - Singleton Pattern
// ============================================================

class IndicatorManager {
    static instance = null;

    constructor() {
        if (IndicatorManager.instance) {
            return IndicatorManager.instance;
        }

        this.registry = new Map(); // Type → Class
        this.activeIndicators = new Map(); // ID → Instance
        this.nextId = 1;
        this.isInitialized = false;

        IndicatorManager.instance = this;
        console.log('📊 IndicatorManager initialisiert (Singleton)');
    }

    static getInstance() {
        if (!IndicatorManager.instance) {
            IndicatorManager.instance = new IndicatorManager();
        }
        return IndicatorManager.instance;
    }

    // Registry: Indikator-Typen registrieren
    registerIndicator(type, indicatorClass) {
        this.registry.set(type, indicatorClass);
        console.log(`📋 Indikator registriert: ${type}`);
    }

    // Indikator hinzufügen
    addIndicator(type, config = {}, skipSave = false) {
        const IndicatorClass = this.registry.get(type);

        if (!IndicatorClass) {
            console.error(`❌ Unbekannter Indikator-Typ: ${type}`);
            return null;
        }

        // Guard: Chart muss existieren
        if (!window.chart) {
            console.error('❌ Chart nicht verfügbar - kann Indikator nicht hinzufügen');
            return null;
        }

        // Erstelle Instanz mit einzigartiger ID
        const id = `${type}_${this.nextId++}`;
        const indicator = new IndicatorClass(id, config);

        // Render auf Chart
        indicator.render(window.chart);

        // Speichern
        this.activeIndicators.set(id, indicator);

        // CRITICAL: Nur speichern wenn nicht vom Load aufgerufen (verhindert Duplikation)
        if (!skipSave) {
            this.saveState();
        }

        console.log(`✅ Indikator hinzugefügt: ${type} (ID: ${id})`);

        // UI-Label rendern
        this.renderLabels();

        return id;
    }

    // Indikator entfernen
    removeIndicator(id) {
        const indicator = this.activeIndicators.get(id);

        if (!indicator) {
            console.warn(`⚠️ Indikator nicht gefunden: ${id}`);
            return;
        }

        // Cleanup
        indicator.destroy();
        this.activeIndicators.delete(id);
        this.saveState();

        console.log(`🗑️ Indikator entfernt: ${id}`);

        // UI-Label aktualisieren
        this.renderLabels();
    }

    // Visibility Toggle
    toggleVisibility(id) {
        const indicator = this.activeIndicators.get(id);

        if (!indicator) {
            console.warn(`⚠️ Indikator nicht gefunden: ${id}`);
            return;
        }

        indicator.toggleVisibility();
        this.saveState();

        // UI-Label aktualisieren (Eye-Icon)
        this.renderLabels();
    }

    // Settings Update
    updateIndicatorConfig(id, newConfig) {
        const indicator = this.activeIndicators.get(id);

        if (!indicator) {
            console.warn(`⚠️ Indikator nicht gefunden: ${id}`);
            return;
        }

        indicator.setConfig(newConfig);
        this.saveState();

        // UI-Label aktualisieren (Name könnte sich ändern)
        this.renderLabels();
    }

    // Update bei Live-Candle-Updates
    updateAllIndicators(candle) {
        const candleData = window.candlestickSeries?.data();

        if (!candleData || candleData.length === 0) {
            return;
        }

        this.activeIndicators.forEach(indicator => {
            indicator.update(candle, candleData);
        });
    }

    // Sync bei Timeframe-Wechsel (komplette Neuberechnung)
    syncWithTimeframe(newData) {
        console.log('🔄 Indikatoren-Sync mit Timeframe-Wechsel...');

        this.activeIndicators.forEach(indicator => {
            indicator.update(null, newData);
        });

        console.log(`✅ ${this.activeIndicators.size} Indikatoren synchronisiert`);
    }

    // Re-Render nach Chart-Neuaufbau
    reRenderAll(chart) {
        console.log('🔄 Re-Render aller Indikatoren...');

        const candleData = window.candlestickSeries?.data();
        if (!candleData) {
            console.warn('⚠️ Keine Candlestick-Daten für Re-Render');
            return;
        }

        this.activeIndicators.forEach(indicator => {
            // Zerstöre alte Series (falls vorhanden)
            if (indicator.series) {
                indicator.series = null;
            }

            // Neu rendern
            indicator.render(chart);
        });

        console.log(`✅ ${this.activeIndicators.size} Indikatoren re-rendered`);
        this.renderLabels();
    }

    // localStorage Persistierung
    saveState() {
        try {
            const state = Array.from(this.activeIndicators.values()).map(indicator =>
                indicator.serialize()
            );

            localStorage.setItem('rl-trading-indicators', JSON.stringify(state));
            console.log(`💾 ${state.length} Indikatoren gespeichert`);
        } catch (e) {
            console.error('❌ Fehler beim Speichern der Indikatoren:', e);
        }
    }

    loadState() {
        try {
            const saved = localStorage.getItem('rl-trading-indicators');

            if (!saved) {
                console.log('📊 Keine gespeicherten Indikatoren gefunden');
                return;
            }

            const state = JSON.parse(saved);

            // CLEANUP: Remove duplicates from saved state (from old duplication bug)
            const uniqueState = [];
            const seen = new Set();

            state.forEach(({ type, config }) => {
                // Create unique key based on type and config
                const key = `${type}-${config.period}-${config.color}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    uniqueState.push({ type, config });
                }
            });

            const removedCount = state.length - uniqueState.length;
            if (removedCount > 0) {
                console.log(`🧹 ${removedCount} Duplikat(e) entfernt`);
            }
            console.log(`📂 Lade ${uniqueState.length} eindeutige Indikatoren...`);

            // CRITICAL GUARDS: Chart UND CandlestickSeries müssen existieren UND Daten haben
            if (!window.chart) {
                console.warn('⚠️ Chart noch nicht bereit - verschiebe Load (500ms)');
                setTimeout(() => this.loadState(), 500);
                return;
            }

            if (!window.candlestickSeries) {
                console.warn('⚠️ CandlestickSeries noch nicht bereit - verschiebe Load (500ms)');
                setTimeout(() => this.loadState(), 500);
                return;
            }

            const candleData = window.candlestickSeries.data();
            if (!candleData || candleData.length === 0) {
                console.warn('⚠️ Keine Candlestick-Daten verfügbar - verschiebe Load (500ms)');
                setTimeout(() => this.loadState(), 500);
                return;
            }

            // CRITICAL: Clear existing indicators before loading (prevent duplicates)
            this.activeIndicators.clear();

            // Alles bereit - lade Indikatoren OHNE zu speichern (verhindert Duplikation)
            uniqueState.forEach(({ type, config }) => {
                this.addIndicator(type, config, true); // skipSave = true
            });

            // Jetzt EINMALIG speichern mit den geladenen Indikatoren
            this.saveState();

            console.log(`✅ ${uniqueState.length} Indikatoren wiederhergestellt`);
        } catch (e) {
            console.error('❌ Fehler beim Laden der Indikatoren:', e);
        }
    }

    // UI: Labels rendern
    renderLabels() {
        const container = document.getElementById('indicatorLabels');

        if (!container) {
            console.warn('⚠️ Indicator Labels Container nicht gefunden');
            return;
        }

        // Clear
        container.innerHTML = '';

        // Render für jeden aktiven Indikator
        this.activeIndicators.forEach((indicator, id) => {
            const label = document.createElement('div');
            label.className = 'indicator-label';
            label.dataset.id = id;

            const eyeIcon = indicator.visible ? '👁️' : '👁️‍🗨️';
            const visibleClass = indicator.visible ? 'visible' : 'hidden';

            label.innerHTML = `
                <span class="indicator-name ${visibleClass}">${indicator.getDisplayName()}</span>
                <div class="indicator-controls">
                    <button class="indicator-control-btn" onclick="window.IndicatorManager.toggleVisibility('${id}')" title="Toggle Visibility">${eyeIcon}</button>
                    <button class="indicator-control-btn" onclick="window.IndicatorManager.openSettings('${id}')" title="Settings">⚙️</button>
                    <button class="indicator-control-btn" onclick="window.IndicatorManager.removeIndicator('${id}')" title="Remove">🗑️</button>
                </div>
            `;

            container.appendChild(label);
        });

        console.log(`🏷️ ${this.activeIndicators.size} Labels gerendert`);
    }

    // UI: Settings Modal öffnen
    openSettings(id) {
        const indicator = this.activeIndicators.get(id);

        if (!indicator) {
            console.warn(`⚠️ Indikator nicht gefunden: ${id}`);
            return;
        }

        // Setze aktuellen Indikator für Modal
        window.currentIndicatorForSettings = indicator;

        // Fülle Modal mit aktuellen Werten
        const modal = document.getElementById('indicatorSettingsModal');
        const periodInput = document.getElementById('indicatorPeriodInput');
        const colorInput = document.getElementById('indicatorColorInput');

        if (periodInput) periodInput.value = indicator.config.period || 9;
        if (colorInput) colorInput.value = indicator.config.color || '#000000';

        // Öffne Modal
        if (modal) {
            modal.style.display = 'flex';
            console.log(`⚙️ Settings Modal geöffnet für ${indicator.getDisplayName()}`);
        }
    }

    // UI: Settings anwenden
    applySettings() {
        const indicator = window.currentIndicatorForSettings;

        if (!indicator) {
            console.warn('⚠️ Kein Indikator für Settings ausgewählt');
            return;
        }

        const periodInput = document.getElementById('indicatorPeriodInput');
        const colorInput = document.getElementById('indicatorColorInput');

        const newConfig = {
            period: parseInt(periodInput.value) || indicator.config.period,
            color: colorInput.value || indicator.config.color
        };

        this.updateIndicatorConfig(indicator.id, newConfig);

        // Modal schließen
        this.closeSettingsModal();

        console.log(`✅ Settings angewendet für ${indicator.getDisplayName()}`);
    }

    closeSettingsModal() {
        const modal = document.getElementById('indicatorSettingsModal');
        if (modal) {
            modal.style.display = 'none';
        }
        window.currentIndicatorForSettings = null;
    }

    // Cleanup: Alle Indikatoren entfernen
    removeAll() {
        this.activeIndicators.forEach((indicator, id) => {
            indicator.destroy();
        });
        this.activeIndicators.clear();
        this.saveState();
        this.renderLabels();
        console.log('🗑️ Alle Indikatoren entfernt');
    }
}

// ============================================================
// INITIALIZATION
// ============================================================

// Erstelle Singleton-Instanz
const manager = IndicatorManager.getInstance();

// Registriere EMA Indicator
manager.registerIndicator('EMA', EMAIndicator);

// Make globally available
window.IndicatorManager = manager;

console.log('✅ Indicator System bereit');
