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

        // BLUEPRINT: Standard-Properties für ALLE Indikatoren
        const blueprintDefaults = {
            lineWidth: 2,               // Liniendicke (1-10)
            lineStyle: 0,               // 0=solid, 1=dashed, 2=dotted (future)
            priceLineVisible: false,
            lastValueVisible: true,
            crosshairMarkerVisible: true
        };

        // Merge: Blueprint Defaults + User Config
        this.config = { ...blueprintDefaults, ...config };

        // CRITICAL: Lese visible aus config (für localStorage-Restore), Fallback zu true
        this.visible = config.visible !== undefined ? config.visible : true;
        this.series = null; // LightweightCharts Series
        this.data = null;   // Cached calculated data

        // Indikator erstellt
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

        // Handle single series (EMA, VOLUME)
        if (this.series) {
            this.series.applyOptions({ visible: this.visible });
        }

        // Handle multiple series in a Map (SESSION)
        if (this.seriesMap && this.seriesMap instanceof Map) {
            this.seriesMap.forEach(series => {
                series.applyOptions({ visible: this.visible });
            });
        }

        // Handle multiple series in an Array (SESSION_HL)
        if (this.lineSeries && Array.isArray(this.lineSeries)) {
            this.lineSeries.forEach(series => {
                series.applyOptions({ visible: this.visible });
            });
        }

        console.log(`👁️ ${this.type}(${this.id}) Visibility: ${this.visible}`);
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

    /**
     * Request Chart Update - Für Primitive-basierte Indikatoren
     * Triggert Chart-Neuzeichnung nach Primitive-Änderungen (attach/detach)
     * Sucht in allen gängigen Primitive-Container-Strukturen
     */
    requestChartUpdate() {
        console.log(`🔄 requestChartUpdate() called for ${this.type}`);

        // Try multiple container structures (Array, Map, single object)
        const containers = [
            this.highLowLines,      // Session Indikator
            this.fvgBoxes,          // FVG Indikator
            this.sessionBoxes,      // Potenzielle zukünftige Indikatoren
            this.primitives         // Generic container
        ];

        for (const container of containers) {
            if (!container) continue;

            // Array-basierte Container (z.B. highLowLines, fvgBoxes)
            if (Array.isArray(container) && container.length > 0) {
                console.log(`  📦 Found Array container with ${container.length} items`);
                const firstItem = container[0];
                if (firstItem.primitive && firstItem.primitive._requestUpdate) {
                    console.log(`  ✅ Calling _requestUpdate()`);
                    firstItem.primitive._requestUpdate();
                    return; // Update ausgeführt
                }
            }

            // Map-basierte Container (z.B. seriesMap)
            if (container instanceof Map && container.size > 0) {
                console.log(`  📦 Found Map container with ${container.size} items`);
                const firstEntry = container.values().next().value;
                if (firstEntry && firstEntry._requestUpdate) {
                    console.log(`  ✅ Calling _requestUpdate() on Map entry`);
                    firstEntry._requestUpdate();
                    return;
                }
            }
        }

        console.log(`  ⚠️ No valid container found with _requestUpdate`);
    }

    // Getter für UI-Label
    getDisplayName() {
        return `${this.type}(${this.config.period || ''})`;
    }
    // Blueprint: Gemeinsame Config-Controls für Settings Modal
    getCommonConfigControls() {
        return {
            lineWidth: {
                label: 'Linienstärke',
                type: 'range',
                min: 1,
                max: 10,
                step: 1,
                value: this.config.lineWidth
            }
        };
    }


    // Serialize für localStorage
    serialize() {
        return {
            type: this.type,
            config: {...this.config, visible: this.visible}
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

        // Erstelle LineSeries mit Blueprint-Properties
        try {
            this.series = chart.addLineSeries({
                color: this.config.color,
                lineWidth: this.config.lineWidth,           // From Blueprint
                lineStyle: this.config.lineStyle,           // From Blueprint
                priceLineVisible: this.config.priceLineVisible,
                lastValueVisible: this.config.lastValueVisible,
                crosshairMarkerVisible: this.config.crosshairMarkerVisible,
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
// CUSTOM RECTANGLE PRIMITIVE - Für durchgehende Session-Boxen
// ============================================================

class RectanglePrimitive {
    constructor(p1, p2, fillColor) {
        this._p1 = p1; // { time, price }
        this._p2 = p2; // { time, price }
        this._fillColor = fillColor;
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const crosshairPos = this._crosshairPosition(scope);
            if (!crosshairPos) return;

            // Konvertiere Zeit/Preis zu Pixel-Koordinaten
            const x1 = crosshairPos.x1;
            const y1 = crosshairPos.y1;
            const x2 = crosshairPos.x2;
            const y2 = crosshairPos.y2;

            // Zeichne gefülltes Rechteck
            ctx.fillStyle = this._fillColor;
            ctx.fillRect(
                Math.min(x1, x2),
                Math.min(y1, y2),
                Math.abs(x2 - x1),
                Math.abs(y2 - y1)
            );
        });
    }

    _crosshairPosition(scope) {
        const series = scope.series;
        const timeScale = scope.timeScale;

        // Konvertiere Zeit zu Pixel
        const x1 = timeScale.timeToCoordinate(this._p1.time);
        const x2 = timeScale.timeToCoordinate(this._p2.time);

        // Konvertiere Preis zu Pixel
        const y1 = series.priceToCoordinate(this._p1.price);
        const y2 = series.priceToCoordinate(this._p2.price);

        if (x1 === null || x2 === null || y1 === null || y2 === null) {
            return null;
        }

        return {
            x1: x1 * scope.horizontalPixelRatio,
            y1: y1 * scope.verticalPixelRatio,
            x2: x2 * scope.horizontalPixelRatio,
            y2: y2 * scope.verticalPixelRatio
        };
    }
}

// ============================================================
// SESSION RECTANGLE PRIMITIVE - Custom Drawing
// ============================================================

/**
 * Helper: Berechnet Position und Länge für Rectangle Drawing
 */
function positionsBox(p1, p2, pixelRatio) {
    const minCoordinate = Math.min(p1, p2) * pixelRatio;
    const maxCoordinate = Math.max(p1, p2) * pixelRatio;
    return {
        position: minCoordinate,
        length: maxCoordinate - minCoordinate
    };
}

/**
 * Rectangle Pane Renderer - Zeichnet Rectangle auf Canvas
 */
class RectanglePaneRenderer {
    constructor(p1, p2, fillColor, label, labelColor) {
        this._p1 = p1; // {x, y}
        this._p2 = p2; // {x, y}
        this._fillColor = fillColor;
        this._label = label; // Label-Text (z.B. "ASIAN", "EUROPEAN")
        this._labelColor = labelColor; // Label-Farbe
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            if (!this._p1 || !this._p2 || this._p1.x === null || this._p2.x === null) {
                return;
            }

            const ctx = scope.context;
            const horizontalPositions = positionsBox(
                this._p1.x,
                this._p2.x,
                scope.horizontalPixelRatio
            );
            const verticalPositions = positionsBox(
                this._p1.y,
                this._p2.y,
                scope.verticalPixelRatio
            );

            // Zeichne Rectangle
            ctx.fillStyle = this._fillColor;
            ctx.fillRect(
                horizontalPositions.position,
                verticalPositions.position,
                horizontalPositions.length,
                verticalPositions.length
            );

            // Zeichne Label (ÜBER der Box, mittig)
            if (this._label) {
                const labelX = horizontalPositions.position + (horizontalPositions.length / 2); // Mitte der Box
                const labelY = verticalPositions.position - 5 * scope.verticalPixelRatio; // Oberhalb

                ctx.font = `${12 * scope.verticalPixelRatio}px Arial`;
                ctx.fillStyle = this._labelColor;
                ctx.textAlign = 'center'; // Zentriert
                ctx.textBaseline = 'bottom';
                ctx.fillText(this._label, labelX, labelY);
            }
        });
    }
}

/**
 * Rectangle Pane View - Konvertiert Preis/Zeit zu Koordinaten
 */
class RectanglePaneView {
    constructor(source) {
        this._source = source;
        this._p1 = null;
        this._p2 = null;
    }

    update() {
        const series = this._source.series;
        const chart = this._source.chart;

        if (!series || !chart) {
            console.warn('⚠️ RectanglePaneView update: series oder chart nicht verfügbar');
            return;
        }

        // Konvertiere Preis zu Y-Koordinate
        const y1 = series.priceToCoordinate(this._source._p1.price);
        const y2 = series.priceToCoordinate(this._source._p2.price);

        // Konvertiere Zeit zu X-Koordinate
        const timeScale = chart.timeScale();
        const x1 = timeScale.timeToCoordinate(this._source._p1.time);
        const x2 = timeScale.timeToCoordinate(this._source._p2.time);

        this._p1 = { x: x1, y: y1 };
        this._p2 = { x: x2, y: y2 };
    }

    renderer() {
        // Wenn nicht sichtbar, nichts rendern
        if (!this._source._visible) {
            return null;
        }

        return new RectanglePaneRenderer(
            this._p1,
            this._p2,
            this._source._fillColor,
            this._source._label,
            this._source._labelColor
        );
    }

    zOrder() {
        return 'bottom'; // Hinter Candles rendern
    }
}

/**
 * Session Rectangle Primitive - ISeriesPrimitive Implementation
 */
class SessionRectangle {
    constructor(p1, p2, fillColor, chart, series, label, labelColor) {
        this._p1 = p1; // {time, price}
        this._p2 = p2; // {time, price}
        this._fillColor = fillColor;
        this._label = label; // Label-Text (z.B. "ASIAN")
        this._labelColor = labelColor; // Label-Farbe
        this.chart = chart;
        this.series = series;
        this._paneViews = [new RectanglePaneView(this)];
        this._requestUpdate = null;
        this._visible = true; // Sichtbarkeits-Flag (Standard: sichtbar)
    }

    updateAllViews() {
        this._paneViews.forEach(view => view.update());
    }

    paneViews() {
        return this._paneViews;
    }

    attached(param) {
        this.chart = param.chart;
        this.series = param.series;
        this._requestUpdate = param.requestUpdate;
        this.updateAllViews();
    }

    detached() {
        this.chart = null;
        this.series = null;
        this._requestUpdate = null;
    }
}

// SESSION INDICATOR - Trading Sessions mit High/Low
// ============================================================

class SessionIndicator extends BaseIndicator {
    constructor(id, config = {}) {
        // Default Config mit allen anpassbaren Werten
        const defaults = {
            // Timezone Settings
            utcOffset: 2,               // UTC+2 für Europa/Berlin (NQ Futures)

            // Session Zeiten (in lokaler Zeit mit UTC-Offset)
            asianStart: '00:00',
            asianEnd: '08:00',
            europeanStart: '08:00',
            europeanEnd: '14:30',
            americanStart: '14:30',
            americanEnd: '22:00',

            // Farben & Transparenz (0-50%)
            asianColor: '#FFD700',      // Gold
            europeanColor: '#00FF00',   // Green
            americanColor: '#1E90FF',   // DodgerBlue
            transparency: 10,           // 10% Transparenz (0-50%)

            // High/Low Lines
            showHighLow: true,
            highLowColor: '#FFFFFF',
            highLowStyle: 2,            // 2 = dashed
            highLowWidth: 1,

            // Labels
            showLabels: true,

            // Handelstage-Rückblick (echte Handelstage Mo-Fr)
            tradingDaysLookback: null   // null = unbegrenzt (alle Daten), Zahl = letzte N Handelstage
        };

        super(id, 'SESSION', { ...defaults, ...config });

        // Session-Boxen Storage
        this.sessionBoxes = [];
        this.highLowLines = [];
        this.chart = null; // Chart-Referenz für sichtbaren Bereich (wird in render() gesetzt)
    }

    // Hilfsfunktion: Zeit-String zu Minuten seit Mitternacht
    timeToMinutes(timeStr) {
        const [hours, minutes] = timeStr.split(':').map(Number);
        return hours * 60 + minutes;
    }

    // Hilfsfunktion: RGB zu RGBA mit Transparenz
    colorWithTransparency(hexColor, transparency) {
        // Konvertiere HEX zu RGB
        const r = parseInt(hexColor.slice(1, 3), 16);
        const g = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);

        // Transparenz: 0-50% → Alpha: 0.00-0.50
        const alpha = transparency / 100;

        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    // Hilfsfunktion: Prüfe ob Datum ein Handelstag ist (Mo-Fr)
    isTradingDay(date) {
        const dayOfWeek = date.getUTCDay(); // 0=Sonntag, 6=Samstag
        return dayOfWeek >= 1 && dayOfWeek <= 5; // Mo-Fr
    }

    // Hilfsfunktion: Hole letzte N Handelstage ab Enddatum
    getLastNTradingDays(endDate, n) {
        const tradingDays = [];

        // CRITICAL FIX: Nutze lokale Zeit mit UTC-Offset statt UTC
        // Konvertiere endDate zu lokaler Zeit
        const offsetMinutes = this.config.utcOffset * 60;
        const localEndDate = new Date(endDate.getTime() + offsetMinutes * 60 * 1000);

        const currentDate = new Date(localEndDate);

        // Rückwärts zählen bis N Handelstage gefunden
        while (tradingDays.length < n) {
            if (this.isTradingDay(currentDate)) {
                // Speichere Datum als YYYY-MM-DD String (lokale Zeit)
                const year = currentDate.getUTCFullYear();
                const month = String(currentDate.getUTCMonth() + 1).padStart(2, '0');
                const day = String(currentDate.getUTCDate()).padStart(2, '0');
                const dateStr = `${year}-${month}-${day}`;
                tradingDays.push(dateStr);
            }
            // Gehe 1 Tag zurück
            currentDate.setUTCDate(currentDate.getUTCDate() - 1);
        }

        return tradingDays;
    }

    // Hilfsfunktion: Hole ALLE Handelstage aus verfügbaren Daten (unbegrenzter Modus)
    getAllTradingDaysInData(data) {
        const tradingDaysSet = new Set();

        data.forEach(candle => {
            const date = new Date(candle.time * 1000);

            // Wende UTC-Offset an (konsistent mit isInTradingDaysList)
            const offsetMinutes = this.config.utcOffset * 60;
            const localDate = new Date(date.getTime() + offsetMinutes * 60 * 1000);

            // Prüfe ob Handelstag (Mo-Fr)
            if (this.isTradingDay(localDate)) {
                // Extrahiere Datum als YYYY-MM-DD String
                const year = localDate.getUTCFullYear();
                const month = String(localDate.getUTCMonth() + 1).padStart(2, '0');
                const day = String(localDate.getUTCDate()).padStart(2, '0');
                const dateStr = `${year}-${month}-${day}`;
                tradingDaysSet.add(dateStr);
            }
        });

        // Konvertiere Set zu Array und sortiere (älteste zuerst)
        return Array.from(tradingDaysSet).sort();
    }

    // Hilfsfunktion: Prüfe ob Kerze in Handelstagen-Liste liegt
    isInTradingDaysList(candleTime, tradingDaysList) {
        const date = new Date(candleTime * 1000);

        // CRITICAL FIX: Wende UTC-Offset an für konsistente Datumsberechnung
        // UTC-Offset wird auch für Session-Erkennung genutzt - muss konsistent sein!
        // Konvertiere zu lokaler Zeit mit Offset (in Minuten)
        const offsetMinutes = this.config.utcOffset * 60;
        const localDate = new Date(date.getTime() + offsetMinutes * 60 * 1000);

        // Nutze lokales Datum für Vergleich
        const year = localDate.getUTCFullYear();
        const month = String(localDate.getUTCMonth() + 1).padStart(2, '0');
        const day = String(localDate.getUTCDate()).padStart(2, '0');
        const dateStr = `${year}-${month}-${day}`;

        return tradingDaysList.includes(dateStr);
    }

    // Berechne Session-Daten und High/Low
    calculate(data) {
        if (!data || data.length === 0) {
            return { sessions: [], highLows: [] };
        }

        const sessions = [];
        const highLows = [];

        // Gruppiere Kerzen nach Session
        const sessionRanges = this.findSessionRanges(data);

        // Berechne High/Low für jede Session
        sessionRanges.forEach(({ type, start, end, candles }) => {
            if (candles.length === 0) return;

            // Finde High/Low in dieser Session
            let high = candles[0].high;
            let low = candles[0].low;

            candles.forEach(candle => {
                if (candle.high > high) high = candle.high;
                if (candle.low < low) low = candle.low;
            });

            sessions.push({ type, start, end });
            highLows.push({ type, start, end, high, low, candles });
        });

        return { sessions, highLows };
    }

    // Finde Session-Ranges in Daten
    findSessionRanges(data) {
        if (!data || data.length === 0) return [];

        // MODUS-SWITCH: null = unbegrenzt (alle Daten), Zahl = letzte N Handelstage
        let tradingDaysList;

        if (this.config.tradingDaysLookback === null) {
            // MODUS 2: Unbegrenzter Modus - alle verfügbaren Handelstage nutzen
            tradingDaysList = this.getAllTradingDaysInData(data);
        } else {
            // MODUS 1: Begrenzter Modus - nur letzte N Handelstage
            // CRITICAL: IMMER die neueste Kerze im Dataset nutzen (nicht sichtbare!)
            // → Sessions bleiben bei den neuesten Daten, egal wo User scrollt
            const newestCandle = data[data.length - 1];
            const newestCandleDate = new Date(newestCandle.time * 1000);
            tradingDaysList = this.getLastNTradingDays(newestCandleDate, this.config.tradingDaysLookback);
        }

        // CRITICAL FIX: Filtere Daten VORHER auf Handelstage, nicht WÄHREND der Iteration
        // Verhindert abgebrochene Sessions durch Kerzen außerhalb der Handelstage
        const filteredData = data.filter(candle => this.isInTradingDaysList(candle.time, tradingDaysList));

        const ranges = [];
        let currentSession = null;
        let currentCandles = [];

        filteredData.forEach(candle => {
            // Alle Kerzen hier sind garantiert in den Handelstagen

            // Wende UTC-Offset an (Candle-Zeit ist UTC, wir brauchen lokale Zeit)
            const date = new Date(candle.time * 1000);
            const utcHour = date.getUTCHours();
            const localHour = (utcHour + this.config.utcOffset + 24) % 24; // +24 und %24 für negative Offsets
            const localMinute = date.getUTCMinutes();
            const hourMinute = `${String(localHour).padStart(2, '0')}:${String(localMinute).padStart(2, '0')}`;
            const minutes = this.timeToMinutes(hourMinute);

            // Bestimme Session-Typ
            let sessionType = null;
            const asianMinutes = { start: this.timeToMinutes(this.config.asianStart), end: this.timeToMinutes(this.config.asianEnd) };
            const europeanMinutes = { start: this.timeToMinutes(this.config.europeanStart), end: this.timeToMinutes(this.config.europeanEnd) };
            const americanMinutes = { start: this.timeToMinutes(this.config.americanStart), end: this.timeToMinutes(this.config.americanEnd) };

            if (minutes >= asianMinutes.start && minutes < asianMinutes.end) {
                sessionType = 'asian';
            } else if (minutes >= europeanMinutes.start && minutes < europeanMinutes.end) {
                sessionType = 'european';
            } else if (minutes >= americanMinutes.start && minutes < americanMinutes.end) {
                sessionType = 'american';
            }

            // Session-Wechsel erkennen
            if (sessionType !== currentSession) {
                // Speichere vorherige Session
                if (currentSession && currentCandles.length > 0) {
                    const sessionRange = {
                        type: currentSession,
                        start: currentCandles[0].time,
                        end: currentCandles[currentCandles.length - 1].time,
                        candles: [...currentCandles]
                    };
                    ranges.push(sessionRange);
                }

                // Starte neue Session
                currentSession = sessionType;
                currentCandles = sessionType ? [candle] : [];
            } else if (sessionType) {
                currentCandles.push(candle);
            }
        });

        // Letzte Session speichern
        if (currentSession && currentCandles.length > 0) {
            const sessionRange = {
                type: currentSession,
                start: currentCandles[0].time,
                end: currentCandles[currentCandles.length - 1].time,
                candles: currentCandles
            };
            ranges.push(sessionRange);
        }

        // Summary Log (kompakt)
        return ranges;
    }

    render(chart) {
        if (!chart) {
            console.error('❌ Session render: Chart nicht verfügbar');
            return;
        }

        // CRITICAL: Speichere Chart-Referenz für sichtbaren Bereich in findSessionRanges()
        this.chart = chart;

        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            return;
        }

        // Berechne Sessions
        const { sessions, highLows } = this.calculate(candleData);

        // WICHTIG: Lightweight Charts hat KEINE native Session-Box Unterstützung
        // Workaround: Wir nutzen eine unsichtbare Line-Series als Placeholder
        // Die echte Session-Visualisierung müsste über Canvas-Overlay erfolgen

        // Erstelle Dummy-Series für Indikator-Label
        this.series = chart.addLineSeries({
            color: 'transparent',
            lastValueVisible: false,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
            title: 'Sessions'
        });

        // Rendere Session-Boxen (nur wenn visible!)
        if (this.visible) {
            this.renderHighLowLines(chart, highLows);
        }
    }

    renderHighLowLines(chart, highLows) {
        // Hole Candlestick Series ZUERST für Cleanup UND Rendering
        const candlestickSeries = window.candlestickSeries;
        if (!candlestickSeries) {
            console.error('❌ Candlestick Series nicht verfügbar für Session Rectangles');
            return;
        }

        // Clear alte Primitives & Lines
        this.highLowLines.forEach(item => {
            try {
                // KRITISCH: Detach von candlestickSeries, nicht this.series!
                if (item.primitive && candlestickSeries) {
                    // KRITISCH: _visible Flag setzen + Update triggern VOR Detach!
                    item.primitive._visible = false;
                    if (item.primitive._requestUpdate) {
                        item.primitive._requestUpdate();
                    }
                    candlestickSeries.detachPrimitive(item.primitive);
                }
                if (item.series) {
                    chart.removeSeries(item.series);
                }
            } catch (e) {
                console.warn('⚠️ Fehler beim Entfernen:', e);
            }
        });
        this.highLowLines = [];

        // GUARD: Handelstage-Tracking für Begrenzung
        const paintedTradingDays = new Set();
        let skippedCount = 0;

        // CRITICAL: Reverse Array → Neueste Sessions zuerst malen (für Limit)
        // Ohne Reverse: Alte Sessions werden gemalt, neue übersprungen
        // Mit Reverse: Neue Sessions werden gemalt, alte übersprungen (korrekt!)
        const reversedHighLows = [...highLows].reverse();

        // Rendere Session-Boxen mit Rectangle Primitives
        let attachedCount = 0;
        reversedHighLows.forEach(({ type, start, end, high, low, candles }, index) => {
            // Extrahiere Handelstag aus Session-Start (mit UTC-Offset)
            const sessionDate = new Date(start * 1000);
            const offsetMinutes = this.config.utcOffset * 60;
            const localDate = new Date(sessionDate.getTime() + offsetMinutes * 60 * 1000);
            const dateKey = `${localDate.getUTCFullYear()}-${String(localDate.getUTCMonth() + 1).padStart(2, '0')}-${String(localDate.getUTCDate()).padStart(2, '0')}`;

            // GUARD: Prüfe Handelstage-Limit (nur im begrenzten Modus)
            if (this.config.tradingDaysLookback !== null) {
                // Ist dieser Handelstag neu und würde Limit überschreiten?
                if (!paintedTradingDays.has(dateKey) && paintedTradingDays.size >= this.config.tradingDaysLookback) {
                    skippedCount++;
                    return; // SKIP - Limit erreicht
                }
            }

            // Handelstag merken
            paintedTradingDays.add(dateKey);

            const sessionColor = this.getSessionColor(type);
            const colorWithAlpha = this.colorWithTransparency(sessionColor, this.config.transparency);
            const label = this.getSessionLabel(type);

            // ========================================
            // SESSION BOX: Rectangle Primitive = Echte Box
            // ========================================
            const rectangle = new SessionRectangle(
                { time: start, price: low },    // P1: Start Zeit, Low Preis
                { time: end, price: high },     // P2: End Zeit, High Preis
                colorWithAlpha,                 // Fill Color mit Transparenz
                chart,
                candlestickSeries,
                label,                          // Label-Text
                sessionColor                    // Label-Farbe (volle Farbe, kein Alpha)
            );

            // Attach Primitive zu Candlestick Series
            try {
                candlestickSeries.attachPrimitive(rectangle);
                this.highLowLines.push({ primitive: rectangle, type: 'rectangle-box', sessionType: type });
                attachedCount++;
            } catch (e) {
                console.error(`❌ Fehler beim Attach von Box #${index + 1}:`, e);
            }
        });
    }

    getSessionColor(type) {
        switch (type) {
            case 'asian': return this.config.asianColor;
            case 'european': return this.config.europeanColor;
            case 'american': return this.config.americanColor;
            default: return '#FFFFFF';
        }
    }

    getSessionLabel(type) {
        switch (type) {
            case 'asian': return 'ASIAN';
            case 'european': return 'EUROPE';
            case 'american': return 'US';
            default: return '';
        }
    }

    update(candle, allData) {
        // Bei Session-Indikator: Komplette Neuberechnung bei Update
        if (!allData || allData.length === 0) return;

        // Entferne alte Primitives & Lines
        const candlestickSeries = window.candlestickSeries;
        this.highLowLines.forEach(item => {
            try {
                // Detach Rectangle Primitives von Candlestick Series
                if (item.primitive && candlestickSeries) {
                    // KRITISCH: _visible Flag setzen + Update triggern VOR Detach!
                    item.primitive._visible = false;
                    if (item.primitive._requestUpdate) {
                        item.primitive._requestUpdate();
                    }
                    candlestickSeries.detachPrimitive(item.primitive);
                }
                // Remove Border Line Series
                if (item.series && window.chart) {
                    window.chart.removeSeries(item.series);
                }
            } catch (e) {
                console.warn('⚠️ Update: Fehler beim Entfernen:', e);
            }
        });
        this.highLowLines = [];

        // Neu berechnen und rendern (nur wenn visible!)
        const { sessions, highLows } = this.calculate(allData);
        if (window.chart && this.visible) {
            this.renderHighLowLines(window.chart, highLows);
        }
    }

    toggleVisibility() {
        this.visible = !this.visible;

        const candlestickSeries = window.candlestickSeries;
        if (!candlestickSeries) {
            console.error('❌ Sessions Toggle: Candlestick Series nicht verfügbar');
            return;
        }

        if (this.visible) {
            // EINSCHALTEN: Neu rendern (erstellt Primitives neu)
            const candleData = candlestickSeries.data();
            if (candleData && candleData.length > 0) {
                const { sessions, highLows } = this.calculate(candleData);
                this.renderHighLowLines(window.chart, highLows);
                // Force chart update nach Primitive-Attach
                this.requestChartUpdate();
            }
        } else {
            // AUSSCHALTEN: Alle Primitives detachen
            this.highLowLines.forEach(item => {
                try {
                    if (item.primitive) {
                        // CRITICAL FIX: Leere die PaneViews BEVOR detach!
                        item.primitive._paneViews = [];
                        item.primitive._visible = false;
                        if (item.primitive._requestUpdate) {
                            item.primitive._requestUpdate();
                        }
                        candlestickSeries.detachPrimitive(item.primitive);
                    }
                } catch (e) {
                    console.warn('⚠️ Fehler beim Detach:', e);
                }
            });
            this.highLowLines = [];
        }

        console.log(`✅ Sessions Toggle: ${this.visible ? 'ON' : 'OFF'}`);
    }

    destroy() {
        // Entferne alle Primitives & Lines
        const candlestickSeries = window.candlestickSeries;
        this.highLowLines.forEach(item => {
            try {
                // Detach Rectangle Primitives von Candlestick Series
                if (item.primitive && candlestickSeries) {
                    // KRITISCH: _visible Flag setzen + Update triggern VOR Detach!
                    item.primitive._visible = false;
                    if (item.primitive._requestUpdate) {
                        item.primitive._requestUpdate();
                    }
                    candlestickSeries.detachPrimitive(item.primitive);
                }
                // Remove Border Line Series
                if (item.series && window.chart) {
                    window.chart.removeSeries(item.series);
                }
            } catch (e) {
                console.warn('⚠️ Destroy: Fehler beim Entfernen:', e);
            }
        });
        this.highLowLines = [];

        super.destroy();
    }

    getDisplayName() {
        return 'Sessions (A/E/US)';
    }
}

// ============================================================
// VOLUME INDICATOR - Volume Histogram with Price Direction
// ============================================================

class VolumeIndicator extends BaseIndicator {
    constructor(id, config = {}) {
        // Default Config
        const defaults = {
            bullishColor: '#26a69a',    // Grün für bullish (Close >= Open)
            bearishColor: '#ef5350',    // Rot für bearish (Close < Open)
            scaleMargins: {
                top: 0.92,              // 92% Abstand vom oberen Rand (startet bei 92%)
                bottom: 0               // Null Abstand zur X-Achse (belegt untere 8%)
            }
        };

        super(id, 'VOLUME', { ...defaults, ...config });
        console.log('📊 Volume Indikator erstellt:', this.config);
    }

    calculate(data) {
        if (!data || data.length === 0) {
            console.warn('⚠️ Volume: Keine Daten verfügbar');
            return [];
        }

        // Extrahiere Volume + berechne Farbe basierend auf Candle-Direction
        const volumeData = data.map(candle => {
            // Validierung: Volume vorhanden?
            if (candle.volume === undefined || candle.volume === null) {
                console.warn('⚠️ Candle ohne Volume gefunden:', candle);
                return null;
            }

            // Farb-Logik: Grün wenn Close >= Open, Rot sonst
            const color = candle.close >= candle.open
                ? this.config.bullishColor
                : this.config.bearishColor;

            return {
                time: candle.time,
                value: candle.volume,
                color: color
            };
        }).filter(item => item !== null); // Filtere invalide Daten

        console.log(`✅ Volume berechnet: ${volumeData.length} Bars`);
        this.data = volumeData;
        return volumeData;
    }

    render(chart) {
        if (!chart) {
            console.error('❌ Volume render: Chart nicht verfügbar');
            return;
        }

        // Hole Candlestick-Daten + Volume aus Cache
        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            console.warn('⚠️ Volume render: Keine Candlestick-Daten verfügbar');
            return;
        }

        // CRITICAL: Merge Candle-Daten mit Volume aus Cache
        const candleDataWithVolume = candleData.map((candle, index) => {
            const volumeEntry = window.volumeDataCache?.find(v => v.time === candle.time);
            return {
                ...candle,
                volume: volumeEntry?.volume || 0
            };
        });

        // Berechne Volume-Daten
        const volumeData = this.calculate(candleDataWithVolume);
        if (volumeData.length === 0) {
            console.warn('⚠️ Volume render: Berechnung ergab keine Daten');
            return;
        }

        // Erstelle Histogram-Series (Overlay-Modus)
        try {
            this.series = chart.addHistogramSeries({
                priceFormat: {
                    type: 'volume'  // Volume-Format für korrekte Darstellung
                },
                priceScaleId: '',   // Overlay-Modus (eigene Scale)
                lastValueVisible: false,
                priceLineVisible: false,
                title: 'Volume'
            });

            // CRITICAL: Apply scaleMargins to Volume's price scale (separate from main chart)
            this.series.priceScale().applyOptions({
                scaleMargins: this.config.scaleMargins
            });

            this.series.setData(volumeData);
            this.series.applyOptions({ visible: this.visible });

            console.log(`✅ Volume-Indikator gerendert: ${volumeData.length} Bars`);
        } catch (e) {
            console.error('❌ Fehler beim Rendern von Volume:', e);
        }
    }

    update(candle, allData) {
        if (!allData || allData.length === 0) {
            console.warn('⚠️ Volume update: Keine Daten verfügbar');
            return;
        }

        // CRITICAL: Merge mit Volume-Cache
        const allDataWithVolume = allData.map(c => {
            const volumeEntry = window.volumeDataCache?.find(v => v.time === c.time);
            return {
                ...c,
                volume: volumeEntry?.volume || 0
            };
        });

        // Komplette Neuberechnung bei jedem Update
        const newVolumeData = this.calculate(allDataWithVolume);

        if (this.series && newVolumeData.length > 0) {
            try {
                this.series.setData(newVolumeData);
                console.log(`🔄 Volume updated: ${newVolumeData.length} Bars`);
            } catch (e) {
                console.error('❌ Fehler beim Update von Volume:', e);
            }
        }
    }

    getDisplayName() {
        return 'Volume';
    }

    getCurrentState() {
        // Volume Spike Detection für RL Agent
        if (!this.data || this.data.length < 20) {
            return { spike: false, ratio: 1.0, current_volume: 0 };
        }

        // Letztes Volume
        const currentVolume = this.data[this.data.length - 1].value;

        // Durchschnitt der letzten 20 Kerzen (ohne aktuelle)
        const recentVolumes = this.data.slice(-21, -1).map(v => v.value);
        const avgVolume = recentVolumes.reduce((sum, v) => sum + v, 0) / recentVolumes.length;

        // Ratio berechnen
        const ratio = avgVolume > 0 ? currentVolume / avgVolume : 1.0;

        // Spike = Ratio > 1.5x
        const spike = ratio > 1.5;

        return {
            spike,
            ratio: parseFloat(ratio.toFixed(2)),
            current_volume: currentVolume,
            avg_volume: Math.round(avgVolume)
        };
    }
}

// ============================================================
// SESSION HIGH/LOW INDICATOR - Swing Highs/Lows from Sessions
// ============================================================

class SessionHighLowIndicator extends BaseIndicator {
    constructor(id, config = {}) {
        // Default Config
        const defaults = {
            // Timezone Settings (wie SessionIndicator)
            utcOffset: 2,               // UTC+2 für Europa/Berlin

            // Session Zeiten (in lokaler Zeit mit UTC-Offset)
            asianStart: '00:00',
            asianEnd: '08:00',
            europeanStart: '08:00',
            europeanEnd: '14:30',
            americanStart: '14:30',
            americanEnd: '22:00',

            // Sliding Window (KEIN Tages-Limit!)
            maxLinesAbove: 5,           // Max. High-Linien über Preis
            maxLinesBelow: 5,           // Max. Low-Linien unter Preis

            // Line Styling
            highColor: '#FF5252',       // Rot für Highs (Widerstand)
            lowColor: '#4CAF50',        // Grün für Lows (Support)
            lineWidth: 2,
            lineStyle: 0                // 0=solid, 2=dashed
        };

        super(id, 'SESSION_HL', { ...defaults, ...config });

        // Storage
        this.completedSessions = [];    // [{sessionId, type, high, low, endTime}]
        this.lineSeries = [];           // Aktive LineSeries (extend right only)
        this.priceLines = [];           // Price Lines für Breakout Detection

        // Break Tracking (für First Break Detection)
        this.lastSessionId = null;      // Track aktuelle Session
        this.sessionHighBroken = false; // Wurde Session High bereits gebrochen?
        this.sessionLowBroken = false;  // Wurde Session Low bereits gebrochen?
        this.lastPrice = null;          // Letzter Preis für Breakout-Detection
        this.chart = null;              // Chart-Referenz für LineSeries

        // Trigger-History: Welche Levels wurden bereits geloggt?
        // [{price, type: 'high'|'low', brokenLogged: bool}]
        this.triggeredLevels = [];

        // Broken State Tracking (Bugfix: Mehrfach-Aktivierung)
        // current = gerade aktiv | had = war aktiv, dann deaktiviert (permanent blockiert)
        this.currentBrokenHighs = new Set();
        this.currentBrokenLows = new Set();
        this.hadBrokenHighs = new Set();
        this.hadBrokenLows = new Set();
    }

    // ========================================
    // SESSION DETECTION (wiederverwenden)
    // ========================================

    timeToMinutes(timeStr) {
        const [hours, minutes] = timeStr.split(':').map(Number);
        return hours * 60 + minutes;
    }

    // ========================================
    // HELPER: Trading Day Check (optional für Mo-Fr Filter)
    // ========================================

    isTradingDay(date) {
        const dayOfWeek = date.getUTCDay();
        return dayOfWeek >= 1 && dayOfWeek <= 5; // Mo-Fr
    }

    // ========================================
    // HELPER: Aktuelle Session bestimmen + Ende berechnen
    // ========================================

    getCurrentSessionInfo(timestamp) {
        const date = new Date(timestamp * 1000);
        const utcHour = date.getUTCHours();
        const localHour = (utcHour + this.config.utcOffset + 24) % 24;
        const localMinute = date.getUTCMinutes();
        const hourMinute = `${String(localHour).padStart(2, '0')}:${String(localMinute).padStart(2, '0')}`;
        const minutes = this.timeToMinutes(hourMinute);

        // Session-Typ bestimmen
        const asianMinutes = { start: this.timeToMinutes(this.config.asianStart), end: this.timeToMinutes(this.config.asianEnd) };
        const europeanMinutes = { start: this.timeToMinutes(this.config.europeanStart), end: this.timeToMinutes(this.config.europeanEnd) };
        const americanMinutes = { start: this.timeToMinutes(this.config.americanStart), end: this.timeToMinutes(this.config.americanEnd) };

        let sessionType = null;
        let endMinutes = null;

        if (minutes >= asianMinutes.start && minutes < asianMinutes.end) {
            sessionType = 'asian';
            endMinutes = asianMinutes.end;
        } else if (minutes >= europeanMinutes.start && minutes < europeanMinutes.end) {
            sessionType = 'european';
            endMinutes = europeanMinutes.end;
        } else if (minutes >= americanMinutes.start && minutes < americanMinutes.end) {
            sessionType = 'american';
            endMinutes = americanMinutes.end;
        }

        if (!sessionType) {
            return null; // Außerhalb aller Sessions
        }

        // Berechne Session-Ende Timestamp
        const localDate = new Date(date.getTime() + this.config.utcOffset * 60 * 60 * 1000);
        const endHour = Math.floor(endMinutes / 60);
        const endMinute = endMinutes % 60;

        const sessionEndDate = new Date(Date.UTC(
            localDate.getUTCFullYear(),
            localDate.getUTCMonth(),
            localDate.getUTCDate(),
            endHour,
            endMinute,
            0
        ));

        // Konvertiere zurück zu UTC
        const sessionEndTimestamp = Math.floor((sessionEndDate.getTime() - this.config.utcOffset * 60 * 60 * 1000) / 1000);

        return {
            type: sessionType,
            endTimestamp: sessionEndTimestamp
        };
    }

    // ========================================
    // GET NEXT SESSION END TIME (für Breakouts außerhalb Sessions)
    // ========================================

    getNextSessionEndTime(timestamp) {
        // Wenn Breakout außerhalb Session → finde NÄCHSTE Session und nutze deren Ende
        const date = new Date(timestamp * 1000);
        const utcHour = date.getUTCHours();
        const localHour = (utcHour + this.config.utcOffset + 24) % 24;
        const localMinute = date.getUTCMinutes();
        const hourMinute = `${String(localHour).padStart(2, '0')}:${String(localMinute).padStart(2, '0')}`;
        const minutes = this.timeToMinutes(hourMinute);

        const asianMinutes = { start: this.timeToMinutes(this.config.asianStart), end: this.timeToMinutes(this.config.asianEnd) };
        const europeanMinutes = { start: this.timeToMinutes(this.config.europeanStart), end: this.timeToMinutes(this.config.europeanEnd) };
        const americanMinutes = { start: this.timeToMinutes(this.config.americanStart), end: this.timeToMinutes(this.config.americanEnd) };

        let nextSessionType = null;
        let nextEndMinutes = null;
        let daysToAdd = 0;

        // Finde nächste Session
        if (minutes < asianMinutes.start) {
            // Vor Asian Start (22:00-00:00) → Asian Session ist nächste (gleicher Tag)
            nextSessionType = 'asian';
            nextEndMinutes = asianMinutes.end;
        } else if (minutes >= asianMinutes.end && minutes < europeanMinutes.start) {
            // Zwischen Asian/European → European ist nächste
            nextSessionType = 'european';
            nextEndMinutes = europeanMinutes.end;
        } else if (minutes >= europeanMinutes.end && minutes < americanMinutes.start) {
            // Zwischen European/American → American ist nächste
            nextSessionType = 'american';
            nextEndMinutes = americanMinutes.end;
        } else if (minutes >= americanMinutes.end) {
            // Nach American Ende (22:00-24:00) → Asian Session nächster Tag
            nextSessionType = 'asian';
            nextEndMinutes = asianMinutes.end;
            daysToAdd = 1;
        }

        if (!nextSessionType) {
            return null;
        }

        // Berechne Session-Ende Timestamp
        const localDate = new Date(date.getTime() + this.config.utcOffset * 60 * 60 * 1000);
        const endHour = Math.floor(nextEndMinutes / 60);
        const endMinute = nextEndMinutes % 60;

        const sessionEndDate = new Date(Date.UTC(
            localDate.getUTCFullYear(),
            localDate.getUTCMonth(),
            localDate.getUTCDate() + daysToAdd,
            endHour,
            endMinute,
            0
        ));

        // Konvertiere zurück zu UTC
        const sessionEndTimestamp = Math.floor((sessionEndDate.getTime() - this.config.utcOffset * 60 * 60 * 1000) / 1000);

        return {
            type: nextSessionType,
            endTimestamp: sessionEndTimestamp
        };
    }

    // ========================================
    // SESSION RANGE DETECTION
    // ========================================

    findSessionRanges(data) {
        if (!data || data.length === 0) return [];

        const ranges = [];
        let currentSession = null;
        let currentCandles = [];
        let previousDay = null; // 🔥 NEU: Tracke Tag-Wechsel

        // ALLE Daten verwenden (kein Tages-Limit!)
        data.forEach(candle => {
            const date = new Date(candle.time * 1000);
            const utcHour = date.getUTCHours();
            const localHour = (utcHour + this.config.utcOffset + 24) % 24;
            const localMinute = date.getUTCMinutes();
            const hourMinute = `${String(localHour).padStart(2, '0')}:${String(localMinute).padStart(2, '0')}`;
            const minutes = this.timeToMinutes(hourMinute);

            // 🔥 NEU: Tag extrahieren (YYYY-MM-DD)
            const currentDay = date.toISOString().split('T')[0]; // "2024-12-27"
            const dayChanged = previousDay !== null && currentDay !== previousDay;

            // Session-Typ bestimmen
            let sessionType = null;
            const asianMinutes = { start: this.timeToMinutes(this.config.asianStart), end: this.timeToMinutes(this.config.asianEnd) };
            const europeanMinutes = { start: this.timeToMinutes(this.config.europeanStart), end: this.timeToMinutes(this.config.europeanEnd) };
            const americanMinutes = { start: this.timeToMinutes(this.config.americanStart), end: this.timeToMinutes(this.config.americanEnd) };

            if (minutes >= asianMinutes.start && minutes < asianMinutes.end) {
                sessionType = 'asian';
            } else if (minutes >= europeanMinutes.start && minutes < europeanMinutes.end) {
                sessionType = 'european';
            } else if (minutes >= americanMinutes.start && minutes < americanMinutes.end) {
                sessionType = 'american';
            }

            // 🔥 ERWEITERT: Session-Wechsel ODER Tag-Wechsel
            // → Neue Session bei: Session-Typ ändert sich ODER Tag ändert sich
            const shouldStartNewSession = (sessionType !== currentSession) || dayChanged;

            if (shouldStartNewSession) {
                // Speichere vorherige Session
                if (currentSession && currentCandles.length > 0) {
                    ranges.push({
                        type: currentSession,
                        start: currentCandles[0].time,
                        end: currentCandles[currentCandles.length - 1].time,
                        candles: [...currentCandles]
                    });
                }

                // Neue Session
                currentSession = sessionType;
                currentCandles = sessionType ? [candle] : [];
            } else if (sessionType) {
                currentCandles.push(candle);
            }

            // 🔥 NEU: Tag merken
            previousDay = currentDay;
        });

        // Letzte Session
        if (currentSession && currentCandles.length > 0) {
            ranges.push({
                type: currentSession,
                start: currentCandles[0].time,
                end: currentCandles[currentCandles.length - 1].time,
                candles: currentCandles
            });
        }

        return ranges;
    }

    // ========================================
    // CALCULATE - Finde abgeschlossene Sessions
    // ========================================

    calculate(data) {
        if (!data || data.length === 0) {
            return { completedSessions: [] };
        }

        // 🔥 FIX: Lösche alle bestehenden LineSeries VOR Neuberechnung (Go To Date Fix)
        this.lineSeries.forEach(series => {
            try {
                this.chart.removeSeries(series);
            } catch (e) {
                console.warn('⚠️ Fehler beim Entfernen der LineSeries:', e);
            }
        });
        this.lineSeries = [];

        const sessionRanges = this.findSessionRanges(data);

        const completed = [];

        // WICHTIG: Letzte Session könnte noch laufen → ausschließen
        // Prüfe: Ist end-Zeit der Session < neueste Kerze?
        const newestCandleTime = data[data.length - 1].time;

        sessionRanges.forEach((range, index) => {
            const { type, start, end, candles } = range;

            // Guard: Mindestens 1 Kerze
            if (candles.length === 0) return;

            // CRITICAL: Ist das die letzte Session im Array?
            // → Könnte noch laufen, nur abgeschlossene Sessions nutzen
            const isLastSession = index === sessionRanges.length - 1;

            // Prüfe: Ist Session wirklich abgeschlossen?
            // Heuristik: end-Zeit + 5min < neueste Kerze (gibt Puffer für Sessionende)
            const sessionEndBuffer = end + (5 * 60); // 5 Minuten Puffer
            const isCompleted = sessionEndBuffer < newestCandleTime;

            if (!isCompleted && isLastSession) {
                return; // Skip aktive Session
            }

            // Berechne High/Low UND speichere die Zeit wann sie gemacht wurden
            let high = candles[0].high;
            let highTime = candles[0].time;
            let low = candles[0].low;
            let lowTime = candles[0].time;

            candles.forEach(candle => {
                if (candle.high > high) {
                    high = candle.high;
                    highTime = candle.time;  // Merke WANN das High gemacht wurde
                }
                if (candle.low < low) {
                    low = candle.low;
                    lowTime = candle.time;  // Merke WANN das Low gemacht wurde
                }
            });

            // CRITICAL: Berechne THEORETISCHES Session-Ende (nicht letzte Kerzen-Zeit!)
            // `end` ist die Start-Zeit der letzten Kerze, NICHT das Session-Ende!
            // Wir brauchen das tatsächliche Session-Ende basierend auf Session-Typ
            const sessionDate = new Date(start * 1000);
            const offsetMinutes = this.config.utcOffset * 60;
            const localDate = new Date(sessionDate.getTime() + offsetMinutes * 60 * 1000);

            // Session-Ende-Zeit aus Config holen
            let sessionEndTimeStr;
            if (type === 'asian') sessionEndTimeStr = this.config.asianEnd;
            else if (type === 'european') sessionEndTimeStr = this.config.europeanEnd;
            else if (type === 'american') sessionEndTimeStr = this.config.americanEnd;

            // Parse End-Zeit (z.B. "14:30")
            const [endHour, endMinute] = sessionEndTimeStr.split(':').map(Number);

            // Konstruiere theoretisches Session-Ende
            const theoreticalEndDate = new Date(Date.UTC(
                localDate.getUTCFullYear(),
                localDate.getUTCMonth(),
                localDate.getUTCDate(),
                endHour,
                endMinute,
                0
            ));

            // Konvertiere zurück zu UTC (minus offset)
            const theoreticalEndTimestamp = Math.floor((theoreticalEndDate.getTime() - offsetMinutes * 60 * 1000) / 1000);

            completed.push({
                sessionId: `${type}_${start}`,
                type,
                high,
                highTime,  // WANN wurde das High gemacht
                low,
                lowTime,   // WANN wurde das Low gemacht
                startTime: start,
                endTime: theoreticalEndTimestamp  // Nutze theoretisches Ende statt letzter Kerzen-Zeit!
            });
        });

        this.completedSessions = completed;

        return { completedSessions: completed };
    }

    // ========================================
    // SLIDING WINDOW - Filtere sichtbare Levels (inkl. Grace Period für Vision Monitor)
    // ========================================

    getAllLevelsWithGracePeriod(currentPrice) {
        // Gleiche Logik wie getVisibleLevels, aber gibt AUCH durchbrochene Levels zurück
        // die noch in Grace Period sind (für Vision Monitor "broken" Detection)
        if (!this.completedSessions || this.completedSessions.length === 0) {
            return { highs: [], lows: [], brokenHighs: [], brokenLows: [] };
        }

        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            return { highs: [], lows: [], brokenHighs: [], brokenLows: [] };
        }

        const newestCandleTime = candleData[candleData.length - 1].time;
        const relevantSessions = this.completedSessions.filter(s => s.endTime <= newestCandleTime);

        const allHighs = relevantSessions.map(s => ({ price: s.high, sessionId: s.sessionId, session: s, type: 'high' }));
        const allLows = relevantSessions.map(s => ({ price: s.low, sessionId: s.sessionId, session: s, type: 'low' }));

        const unbrokenHighs = [];
        const brokenHighsInGracePeriod = [];

        allHighs.forEach(({ price, session, sessionId }) => {
            const brokenCandle = candleData.find(candle => {
                if (candle.time <= session.endTime) return false;
                return candle.high > price || candle.close > price;
            });

            if (!brokenCandle) {
                unbrokenHighs.push({ price, sessionId, session, type: 'high' });
            } else {
                // Durchbrochen - prüfe Grace Period
                let breakoutSessionInfo = this.getCurrentSessionInfo(brokenCandle.time);

                // 🔥 NEU: Falls außerhalb Session → nutze NÄCHSTE Session Ende
                if (!breakoutSessionInfo) {
                    breakoutSessionInfo = this.getNextSessionEndTime(brokenCandle.time);
                }

                if (breakoutSessionInfo) {
                    const isBreakoutSessionStillActive = newestCandleTime < breakoutSessionInfo.endTimestamp;

                    const breakDate = new Date(brokenCandle.time * 1000).toISOString();
                    const sessionEndDate = new Date(breakoutSessionInfo.endTimestamp * 1000).toISOString();
                    const nowDate = new Date(newestCandleTime * 1000).toISOString();

                    if (isBreakoutSessionStillActive) {
                        brokenHighsInGracePeriod.push({ price, sessionId, session, type: 'high', brokenAt: brokenCandle.time });
                        console.log(`✅ [ALL LEVELS HIGH] ${price.toFixed(2)}: Broken in ${breakoutSessionInfo.type} @ ${breakDate}, Session ends ${sessionEndDate}, now ${nowDate} → GRACE PERIOD`);
                    } else {
                        console.log(`❌ [ALL LEVELS HIGH] ${price.toFixed(2)}: Session ended @ ${sessionEndDate}, now ${nowDate} → REMOVED`);
                    }
                }
            }
        });

        const unbrokenLows = [];
        const brokenLowsInGracePeriod = [];

        allLows.forEach(({ price, session, sessionId }) => {
            const brokenCandle = candleData.find(candle => {
                if (candle.time <= session.endTime) return false;
                return candle.low < price || candle.close < price;
            });

            if (!brokenCandle) {
                unbrokenLows.push({ price, sessionId, session, type: 'low' });
            } else {
                // Durchbrochen - prüfe Grace Period
                let breakoutSessionInfo = this.getCurrentSessionInfo(brokenCandle.time);

                // 🔥 NEU: Falls außerhalb Session → nutze NÄCHSTE Session Ende
                if (!breakoutSessionInfo) {
                    breakoutSessionInfo = this.getNextSessionEndTime(brokenCandle.time);
                }

                if (breakoutSessionInfo) {
                    const isBreakoutSessionStillActive = newestCandleTime < breakoutSessionInfo.endTimestamp;

                    const breakDate = new Date(brokenCandle.time * 1000).toISOString();
                    const sessionEndDate = new Date(breakoutSessionInfo.endTimestamp * 1000).toISOString();
                    const nowDate = new Date(newestCandleTime * 1000).toISOString();

                    if (isBreakoutSessionStillActive) {
                        brokenLowsInGracePeriod.push({ price, sessionId, session, type: 'low', brokenAt: brokenCandle.time });
                        console.log(`✅ [ALL LEVELS LOW] ${price.toFixed(2)}: Broken in ${breakoutSessionInfo.type} @ ${breakDate}, Session ends ${sessionEndDate}, now ${nowDate} → GRACE PERIOD`);
                    } else {
                        console.log(`❌ [ALL LEVELS LOW] ${price.toFixed(2)}: Session ended @ ${sessionEndDate}, now ${nowDate} → REMOVED`);
                    }
                }
            }
        });

        // Deduplizierung für UNBROKEN Levels
        const uniqueHighs = [];
        const seenHighPrices = new Set();
        unbrokenHighs.forEach(h => {
            const roundedPrice = Math.round(h.price * 100) / 100;
            if (!seenHighPrices.has(roundedPrice)) {
                seenHighPrices.add(roundedPrice);
                uniqueHighs.push(h);
            }
        });

        const uniqueLows = [];
        const seenLowPrices = new Set();
        unbrokenLows.forEach(l => {
            const roundedPrice = Math.round(l.price * 100) / 100;
            if (!seenLowPrices.has(roundedPrice)) {
                seenLowPrices.add(roundedPrice);
                uniqueLows.push(l);
            }
        });

        // Deduplizierung für BROKEN Levels in Grace Period
        const uniqueBrokenHighs = [];
        const seenBrokenHighPrices = new Set();
        brokenHighsInGracePeriod.forEach(h => {
            const roundedPrice = Math.round(h.price * 100) / 100;
            if (!seenBrokenHighPrices.has(roundedPrice)) {
                seenBrokenHighPrices.add(roundedPrice);
                uniqueBrokenHighs.push(h);
            }
        });

        const uniqueBrokenLows = [];
        const seenBrokenLowPrices = new Set();
        brokenLowsInGracePeriod.forEach(l => {
            const roundedPrice = Math.round(l.price * 100) / 100;
            if (!seenBrokenLowPrices.has(roundedPrice)) {
                seenBrokenLowPrices.add(roundedPrice);
                uniqueBrokenLows.push(l);
            }
        });

        // ========================================
        // CLEANUP: Entferne Levels aus Broken-Listen die nicht mehr sichtbar sind
        // ========================================
        const currentValidHighPrices = new Set(
            [...uniqueHighs, ...uniqueBrokenHighs].map(h => h.price.toFixed(2))
        );
        const currentValidLowPrices = new Set(
            [...uniqueLows, ...uniqueBrokenLows].map(l => l.price.toFixed(2))
        );

        // Filter Broken Listen - behalte nur noch sichtbare Levels
        this.currentBrokenHighs = new Set(
            [...this.currentBrokenHighs].filter(p => currentValidHighPrices.has(p))
        );
        this.hadBrokenHighs = new Set(
            [...this.hadBrokenHighs].filter(p => currentValidHighPrices.has(p))
        );
        this.currentBrokenLows = new Set(
            [...this.currentBrokenLows].filter(p => currentValidLowPrices.has(p))
        );
        this.hadBrokenLows = new Set(
            [...this.hadBrokenLows].filter(p => currentValidLowPrices.has(p))
        );

        // Logging nur wenn Listen nicht leer
        const totalTracked = this.currentBrokenHighs.size + this.currentBrokenLows.size +
                            this.hadBrokenHighs.size + this.hadBrokenLows.size;
        if (totalTracked > 0) {
            console.log(`🧹 [Session HL Cleanup] Current: H=${this.currentBrokenHighs.size} L=${this.currentBrokenLows.size} | Had: H=${this.hadBrokenHighs.size} L=${this.hadBrokenLows.size}`);
        }

        return {
            highs: uniqueHighs,  // Unbroken Levels
            lows: uniqueLows,
            brokenHighs: uniqueBrokenHighs,  // Broken aber in Grace Period (dedupliziert)
            brokenLows: uniqueBrokenLows
        };
    }

    // ========================================
    // SLIDING WINDOW - Filtere sichtbare Levels
    // ========================================

    getVisibleLevels(currentPrice) {
        if (!this.completedSessions || this.completedSessions.length === 0) {
            return { highs: [], lows: [] };
        }

        // Hole alle Candle-Daten für Breakout-Check
        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            console.warn('⚠️ Keine Candlestick-Daten für Breakout-Check');
            return { highs: [], lows: [] };
        }

        // Neueste Kerzen-Zeit
        const newestCandleTime = candleData[candleData.length - 1].time;

        // 🔥 ZEIT-FILTER: Nur Sessions die VOR oder BIS zur neuesten Kerze liegen
        const relevantSessions = this.completedSessions.filter(s => s.endTime <= newestCandleTime);

        // Sammle alle Highs und Lows NUR von relevanten Sessions
        const allHighs = relevantSessions.map(s => ({ price: s.high, sessionId: s.sessionId, session: s, type: 'high' }));
        const allLows = relevantSessions.map(s => ({ price: s.low, sessionId: s.sessionId, session: s, type: 'low' }));

        // BREAKOUT-FILTER: Entferne durchbrochene Levels (mit Grace Period bis Session-Ende)
        const unbrokenHighs = allHighs.filter(({ price, session }) => {
            // Prüfe: Gab es NACH session.endTime eine Kerze, die das High durchbrochen hat?
            const brokenCandle = candleData.find(candle => {
                // Nur Kerzen NACH Session-Ende prüfen
                if (candle.time <= session.endTime) return false;

                // High durchbrochen wenn: Kerze ging ÜBER das Level (Wick oder Close)
                return candle.high > price || candle.close > price;
            });

            if (!brokenCandle) {
                return true; // Level nicht durchbrochen → anzeigen
            }

            // Level wurde durchbrochen - ABER: Grace Period prüfen!
            // Finde Session, in der der Breakout passiert ist
            let breakoutSessionInfo = this.getCurrentSessionInfo(brokenCandle.time);

            // 🔥 NEU: Falls außerhalb Session → nutze NÄCHSTE Session Ende
            if (!breakoutSessionInfo) {
                breakoutSessionInfo = this.getNextSessionEndTime(brokenCandle.time);
            }

            if (!breakoutSessionInfo) {
                // Kein Session-Info gefunden → entfernen
                return false;
            }

            // Prüfe: Ist die Breakout-Session noch aktiv?
            // → Level bleibt sichtbar BIS zum Ende der Breakout-Session
            const isBreakoutSessionStillActive = newestCandleTime < breakoutSessionInfo.endTimestamp;

            if (isBreakoutSessionStillActive) {
                // Session läuft noch → Level BLEIBT sichtbar (Grace Period)
                return true;
            } else {
                // Session ist vorbei → Level wird entfernt
                return false;
            }
        });

        const unbrokenLows = allLows.filter(({ price, session }) => {
            // Prüfe: Gab es NACH session.endTime eine Kerze, die das Low durchbrochen hat?
            const brokenCandle = candleData.find(candle => {
                // Nur Kerzen NACH Session-Ende prüfen
                if (candle.time <= session.endTime) return false;

                // Low durchbrochen wenn: Kerze ging UNTER das Level (Wick oder Close)
                return candle.low < price || candle.close < price;
            });

            if (!brokenCandle) {
                return true; // Level nicht durchbrochen → anzeigen
            }

            // Level wurde durchbrochen - ABER: Grace Period prüfen!
            // Finde Session, in der der Breakout passiert ist
            let breakoutSessionInfo = this.getCurrentSessionInfo(brokenCandle.time);

            // 🔥 NEU: Falls außerhalb Session → nutze NÄCHSTE Session Ende
            if (!breakoutSessionInfo) {
                breakoutSessionInfo = this.getNextSessionEndTime(brokenCandle.time);
            }

            if (!breakoutSessionInfo) {
                // Kein Session-Info gefunden → entfernen
                return false;
            }

            // Prüfe: Ist die Breakout-Session noch aktiv?
            // → Level bleibt sichtbar BIS zum Ende der Breakout-Session
            const isBreakoutSessionStillActive = newestCandleTime < breakoutSessionInfo.endTimestamp;

            if (isBreakoutSessionStillActive) {
                // Session läuft noch → Level BLEIBT sichtbar (Grace Period)
                return true;
            } else {
                // Session ist vorbei → Level wird entfernt
                return false;
            }
        });

        // DEDUPLIZIERUNG: Entferne doppelte Preis-Levels (behalte neueste Session)
        const uniqueHighs = [];
        const seenHighPrices = new Set();
        unbrokenHighs.forEach(h => {
            // Runde auf 2 Dezimalstellen für Vergleich (vermeidet Floating-Point-Probleme)
            const roundedPrice = Math.round(h.price * 100) / 100;
            if (!seenHighPrices.has(roundedPrice)) {
                seenHighPrices.add(roundedPrice);
                uniqueHighs.push(h);
            }
        });

        const uniqueLows = [];
        const seenLowPrices = new Set();
        unbrokenLows.forEach(l => {
            const roundedPrice = Math.round(l.price * 100) / 100;
            if (!seenLowPrices.has(roundedPrice)) {
                seenLowPrices.add(roundedPrice);
                uniqueLows.push(l);
            }
        });

        // Filter: Highs ÜBER aktuellem Preis (Widerstand)
        const highsAbove = uniqueHighs
            .filter(h => h.price > currentPrice)
            .sort((a, b) => a.price - b.price) // Sortiere aufsteigend (nächste zuerst)
            .slice(0, this.config.maxLinesAbove);

        // Filter: Lows UNTER aktuellem Preis (Support)
        const lowsBelow = uniqueLows
            .filter(l => l.price < currentPrice)
            .sort((a, b) => b.price - a.price) // Sortiere absteigend (nächste zuerst)
            .slice(0, this.config.maxLinesBelow);

        console.log(`📊 Final Visible Levels: ${highsAbove.length} Highs über ${currentPrice.toFixed(2)}, ${lowsBelow.length} Lows darunter`);
        console.log('🔍 ========== BREAKOUT CHECK END ==========\n');

        return { highs: highsAbove, lows: lowsBelow };
    }

    // ========================================
    // RENDER - Erstelle PriceLines
    // ========================================

    render(chart) {
        if (!chart) {
            console.error('❌ SessionHL render: Chart nicht verfügbar');
            return;
        }

        // Speichere Chart-Referenz für LineSeries
        this.chart = chart;

        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            return;
        }

        // 🔥 FIX: NUR berechnen wenn noch KEINE Sessions vorhanden (Initial Load / Go To Date)
        if (!this.completedSessions || this.completedSessions.length === 0) {
            this.calculate(candleData);
        }

        // Initial Render: Hole aktuellen Preis
        const currentPrice = candleData[candleData.length - 1].close;
        this.lastPrice = currentPrice;

        // Rendere LineSeries (extend right only)
        this.updateLineSeries(currentPrice, candleData);
    }

    // ========================================
    // UPDATE LINE SERIES (Extend Right Only)
    // ========================================

    updateLineSeries(currentPrice, candleData) {
        if (!this.chart) {
            return;
        }

        // 🔥 VALIDIERUNG: Prüfe ob candleData vorhanden
        if (!candleData || candleData.length === 0) {
            return;
        }

        // 🔥 FIX: Lösche alte Linien und erstelle neu (für Grace Period Updates)
        this.lineSeries.forEach(series => this.chart.removeSeries(series));
        this.lineSeries = [];

        // Hole sichtbare Levels + Grace Period Levels
        const { highs, lows, brokenHighs, brokenLows } = this.getAllLevelsWithGracePeriod(currentPrice);

        // Kombiniere ungebrochene + Grace Period Levels für Rendering
        const allHighsToRender = [...highs, ...brokenHighs];
        const allLowsToRender = [...lows, ...brokenLows];

        // Neueste Kerzen-Zeit (für Linien-Ende)
        const newestCandleTime = candleData[candleData.length - 1].time;

        // 🔥 VALIDIERUNG: Prüfe ob newestCandleTime gültig ist
        if (!newestCandleTime || isNaN(newestCandleTime)) {
            console.error('❌ SessionHL: Ungültige newestCandleTime:', newestCandleTime);
            return;
        }

        // Erstelle LineSeries für Highs (Widerstand + Grace Period)
        allHighsToRender.forEach(({ price, sessionId }) => {
            try {
                // Finde Session-Ende für diese Linie
                const session = this.completedSessions.find(s => s.sessionId === sessionId);
                if (!session) {
                    return;
                }

                // 🔥 VALIDIERUNG: Prüfe alle Werte vor setData()
                if (!session.endTime || isNaN(session.endTime)) {
                    console.error(`❌ SKIP HIGH: Ungültige session.endTime:`, session.endTime);
                    return;
                }
                if (!session.high || isNaN(session.high)) {
                    console.error(`❌ SKIP HIGH: Ungültige session.high:`, session.high);
                    return;
                }
                if (session.endTime > newestCandleTime) {
                    return;
                }

                // Wähle Farbe basierend auf Session-Typ
                const highColor = session.type === 'asian' ? this.config.asianHighColor :
                                 session.type === 'european' ? this.config.europeanHighColor :
                                 this.config.americanHighColor;

                // Erstelle LineSeries: Von Session-Ende bis neueste Kerze
                const lineSeries = this.chart.addLineSeries({
                    color: highColor,
                    lineWidth: this.config.lineWidth,
                    lineStyle: this.config.lineStyle,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                    title: '' // Y-Achsen Label deaktiviert
                });

                // Setze Daten: Start = Kerze die das High machte, Ende = neueste Kerze
                const lineStartTime = session.highTime;  // Beginne direkt an der Kerze die das High machte!
                const lineData = [
                    { time: lineStartTime, value: session.high },
                    { time: newestCandleTime, value: session.high }
                ];

                lineSeries.setData(lineData);

                this.lineSeries.push(lineSeries);
            } catch (e) {
                console.error(`❌ Fehler beim Erstellen der High LineSeries (${price}):`, e);
            }
        });

        // Erstelle LineSeries für Lows (Support + Grace Period)
        allLowsToRender.forEach(({ price, sessionId }) => {
            try {
                // Finde Session-Ende für diese Linie
                const session = this.completedSessions.find(s => s.sessionId === sessionId);
                if (!session) {
                    return;
                }

                // 🔥 VALIDIERUNG: Prüfe alle Werte vor setData()
                if (!session.endTime || isNaN(session.endTime)) {
                    console.error(`❌ SKIP LOW: Ungültige session.endTime:`, session.endTime);
                    return;
                }
                if (!session.low || isNaN(session.low)) {
                    console.error(`❌ SKIP LOW: Ungültige session.low:`, session.low);
                    return;
                }
                if (session.endTime > newestCandleTime) {
                    return;
                }

                // Wähle Farbe basierend auf Session-Typ
                const lowColor = session.type === 'asian' ? this.config.asianLowColor :
                                session.type === 'european' ? this.config.europeanLowColor :
                                this.config.americanLowColor;

                // Erstelle LineSeries: Von Session-Ende bis neueste Kerze
                const lineSeries = this.chart.addLineSeries({
                    color: lowColor,
                    lineWidth: this.config.lineWidth,
                    lineStyle: this.config.lineStyle,
                    priceLineVisible: false,
                    lastValueVisible: false,
                    crosshairMarkerVisible: false,
                    title: '' // Y-Achsen Label deaktiviert
                });

                // Setze Daten: Start = Kerze die das Low machte, Ende = neueste Kerze
                const lineStartTime = session.lowTime;  // Beginne direkt an der Kerze die das Low machte!
                const lineData = [
                    { time: lineStartTime, value: session.low },
                    { time: newestCandleTime, value: session.low }
                ];

                lineSeries.setData(lineData);

                this.lineSeries.push(lineSeries);
            } catch (e) {
                console.error(`❌ Fehler beim Erstellen der Low LineSeries (${price}):`, e);
            }
        });
    }

    // ========================================
    // UPDATE - Breakout Detection
    // ========================================

    update(candle, allData) {
        if (!allData || allData.length === 0) return;

        // Hole aktuellen Preis
        const currentPrice = allData[allData.length - 1].close;

        // CRITICAL: Breakout Detection
        // Prüfe: Hat sich der Preis "signifikant" bewegt?
        // Heuristik: Wenn Preis wick/touch durch eine der sichtbaren Linien ging
        const currentHigh = allData[allData.length - 1].high;
        const currentLow = allData[allData.length - 1].low;

        let needsUpdate = false;

        // Prüfe ob eine unserer PriceLines durchbrochen wurde
        this.priceLines.forEach(line => {
            // Leider können wir den Preis nicht direkt von der PriceLine lesen
            // Workaround: Wir vergleichen mit lastPrice und schauen ob Sliding Window sich ändern würde
        });

        // Einfachere Heuristik: Hat sich Preis um > 0.1% bewegt seit letztem Update?
        if (this.lastPrice !== null) {
            const priceChange = Math.abs(currentPrice - this.lastPrice) / this.lastPrice;
            if (priceChange > 0.001) { // 0.1% Änderung
                needsUpdate = true;
            }
        }

        // ODER: Neue Kerze deutet auf Session-Wechsel hin (alle 5min neu checken)
        // Für Echtzeit: Bei jedem Update neu berechnen (Performance OK für <100 Sessions)
        needsUpdate = true; // Simpel: Immer updaten

        if (needsUpdate) {
            // Neuberechnung der Sessions (könnten neue abgeschlossene Sessions haben)
            this.calculate(allData);

            // Update LineSeries (extend right to newest candle)
            this.updateLineSeries(currentPrice, allData);

            this.lastPrice = currentPrice;
        }
    }

    destroy() {
        // Entferne alle LineSeries
        if (this.chart) {
            this.lineSeries.forEach(series => {
                try {
                    this.chart.removeSeries(series);
                } catch (e) {
                    console.warn('⚠️ Destroy: Fehler beim Entfernen der LineSeries:', e);
                }
            });
        }
        this.lineSeries = [];
        this.completedSessions = [];
        this.chart = null;
    }

    getDisplayName() {
        return `Session H/L (${this.config.maxLinesAbove}/${this.config.maxLinesBelow} Lines)`;
    }

    // ========================================
    // SETTINGS HTML (für Edit-Dialog)
    // ========================================

    getSettingsHTML() {
        return `
            <div class="setting-group">
                <label>🌍 UTC Offset:</label>
                <input type="number" id="edit_shl_utcOffset" value="${this.config.utcOffset}" min="-12" max="14" step="1">
                <small>Deine lokale Zeitzone (z.B. UTC+2 für Berlin)</small>
            </div>

            <div class="setting-group">
                <label>🌏 Asian Session:</label>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="time" id="edit_shl_asianStart" value="${this.config.asianStart}">
                    <span>bis</span>
                    <input type="time" id="edit_shl_asianEnd" value="${this.config.asianEnd}">
                </div>
            </div>

            <div class="setting-group">
                <label>🌍 European Session:</label>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="time" id="edit_shl_europeanStart" value="${this.config.europeanStart}">
                    <span>bis</span>
                    <input type="time" id="edit_shl_europeanEnd" value="${this.config.europeanEnd}">
                </div>
            </div>

            <div class="setting-group">
                <label>🌎 American Session:</label>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="time" id="edit_shl_americanStart" value="${this.config.americanStart}">
                    <span>bis</span>
                    <input type="time" id="edit_shl_americanEnd" value="${this.config.americanEnd}">
                </div>
            </div>

            <div class="setting-group">
                <label>📊 Max. Linien (oben/unten):</label>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="number" id="edit_shl_maxLinesAbove" value="${this.config.maxLinesAbove}" min="1" max="20" step="1" style="flex: 1;">
                    <span>/</span>
                    <input type="number" id="edit_shl_maxLinesBelow" value="${this.config.maxLinesBelow}" min="1" max="20" step="1" style="flex: 1;">
                </div>
                <small>Wie viele Resistance/Support-Linien gleichzeitig zeigen</small>
            </div>

            <div class="setting-group">
                <label>🎨 Session Farben:</label>
                <div style="display: grid; grid-template-columns: auto 40px 40px; gap: 8px; align-items: center; margin-top: 10px;">
                    <!-- Header -->
                    <div style="color: #888; font-size: 12px;"></div>
                    <div style="color: #888; font-size: 11px; text-align: center;">High</div>
                    <div style="color: #888; font-size: 11px; text-align: center;">Low</div>

                    <!-- Asian Session -->
                    <div style="color: #ff00bb; font-weight: bold;">🌏 Asian</div>
                    <input type="color" id="edit_shl_asianHighColor" value="${this.config.asianHighColor || '#FF00BB'}" style="width: 40px; height: 40px; border: 2px solid #333; border-radius: 4px; cursor: pointer;">
                    <input type="color" id="edit_shl_asianLowColor" value="${this.config.asianLowColor || '#FF00BB'}" style="width: 40px; height: 40px; border: 2px solid #333; border-radius: 4px; cursor: pointer;">

                    <!-- European Session -->
                    <div style="color: #00fbff; font-weight: bold;">🌍 European</div>
                    <input type="color" id="edit_shl_europeanHighColor" value="${this.config.europeanHighColor || '#00CCFF'}" style="width: 40px; height: 40px; border: 2px solid #333; border-radius: 4px; cursor: pointer;">
                    <input type="color" id="edit_shl_europeanLowColor" value="${this.config.europeanLowColor || '#00CCFF'}" style="width: 40px; height: 40px; border: 2px solid #333; border-radius: 4px; cursor: pointer;">

                    <!-- American Session -->
                    <div style="color: #ffae00; font-weight: bold;">🌎 American</div>
                    <input type="color" id="edit_shl_americanHighColor" value="${this.config.americanHighColor || '#FF9900'}" style="width: 40px; height: 40px; border: 2px solid #333; border-radius: 4px; cursor: pointer;">
                    <input type="color" id="edit_shl_americanLowColor" value="${this.config.americanLowColor || '#FF9900'}" style="width: 40px; height: 40px; border: 2px solid #333; border-radius: 4px; cursor: pointer;">
                </div>
            </div>

            <div class="setting-group">
                <label>📏 Linien-Stil:</label>
                <select id="edit_shl_lineStyle">
                    <option value="0" ${this.config.lineStyle === 0 ? 'selected' : ''}>Solid (durchgezogen)</option>
                    <option value="1" ${this.config.lineStyle === 1 ? 'selected' : ''}>Dotted (gepunktet)</option>
                    <option value="2" ${this.config.lineStyle === 2 ? 'selected' : ''}>Dashed (gestrichelt)</option>
                    <option value="3" ${this.config.lineStyle === 3 ? 'selected' : ''}>Large Dashed (große Striche)</option>
                    <option value="4" ${this.config.lineStyle === 4 ? 'selected' : ''}>Sparse Dotted (wenige Punkte)</option>
                </select>
            </div>

            <div class="setting-group">
                <label>📏 Linien-Breite:</label>
                <input type="number" id="edit_shl_lineWidth" value="${this.config.lineWidth}" min="1" max="5" step="1">
            </div>
        `;
    }

    applySettings() {
        // Lese Werte aus Edit-Dialog
        this.config.utcOffset = parseInt(document.getElementById('edit_shl_utcOffset')?.value) || 0;
        this.config.asianStart = document.getElementById('edit_shl_asianStart')?.value || '00:00';
        this.config.asianEnd = document.getElementById('edit_shl_asianEnd')?.value || '09:00';
        this.config.europeanStart = document.getElementById('edit_shl_europeanStart')?.value || '09:00';
        this.config.europeanEnd = document.getElementById('edit_shl_europeanEnd')?.value || '15:30';
        this.config.americanStart = document.getElementById('edit_shl_americanStart')?.value || '15:30';
        this.config.americanEnd = document.getElementById('edit_shl_americanEnd')?.value || '22:00';
        this.config.maxLinesAbove = parseInt(document.getElementById('edit_shl_maxLinesAbove')?.value) || 5;
        this.config.maxLinesBelow = parseInt(document.getElementById('edit_shl_maxLinesBelow')?.value) || 5;
        // Session-spezifische Farben
        this.config.asianHighColor = document.getElementById('edit_shl_asianHighColor')?.value || '#FF00BB';
        this.config.asianLowColor = document.getElementById('edit_shl_asianLowColor')?.value || '#FF00BB';
        this.config.europeanHighColor = document.getElementById('edit_shl_europeanHighColor')?.value || '#00CCFF';
        this.config.europeanLowColor = document.getElementById('edit_shl_europeanLowColor')?.value || '#00CCFF';
        this.config.americanHighColor = document.getElementById('edit_shl_americanHighColor')?.value || '#FF9900';
        this.config.americanLowColor = document.getElementById('edit_shl_americanLowColor')?.value || '#FF9900';
        this.config.lineStyle = parseInt(document.getElementById('edit_shl_lineStyle')?.value) || 0;
        this.config.lineWidth = parseInt(document.getElementById('edit_shl_lineWidth')?.value) || 1;

        // Trigger re-render mit aktualisierten Settings
        const candleData = window.candlestickSeries?.data();
        if (candleData && candleData.length > 0) {
            this.calculate(candleData);
            const currentPrice = candleData[candleData.length - 1].close;
            this.updateLineSeries(currentPrice, candleData);
        }
    }

    getCurrentState(currentPrice) {
        // Session High/Low Detection für RL Agent
        if (!this.completedSessions || this.completedSessions.length === 0) {
            return {
                session_high_broken: false,
                session_low_broken: false,
                session_high_price: null,
                session_low_price: null,
                current_session: null
            };
        }

        // Hole aktuelle Kerze (brauchen high/low/close)
        const candleData = window.candlestickSeries?.data();
        if (!candleData || candleData.length === 0) {
            return {
                session_high_broken: false,
                session_low_broken: false,
                session_high_price: null,
                session_low_price: null,
                current_session: null
            };
        }

        const currentCandle = candleData[candleData.length - 1];
        if (!currentPrice) {
            currentPrice = currentCandle.close;
        }

        // Finde AKTUELLE Session (kann laufend oder abgeschlossen sein)
        // Prüfe zuerst: In welcher Session sind wir gerade?
        const currentTime = currentCandle.time;
        const currentDate = new Date(currentTime * 1000);
        const offsetMinutes = this.config.utcOffset * 60;
        const localDate = new Date(currentDate.getTime() + offsetMinutes * 60 * 1000);

        const hours = localDate.getUTCHours();
        const minutes = localDate.getUTCMinutes();
        const totalMinutes = hours * 60 + minutes;

        // Helper: Zeit zu Minuten
        const timeToMinutes = (timeStr) => {
            const [h, m] = timeStr.split(':').map(Number);
            return h * 60 + m;
        };

        const asianMinutes = { start: timeToMinutes(this.config.asianStart), end: timeToMinutes(this.config.asianEnd) };
        const europeanMinutes = { start: timeToMinutes(this.config.europeanStart), end: timeToMinutes(this.config.europeanEnd) };
        const americanMinutes = { start: timeToMinutes(this.config.americanStart), end: timeToMinutes(this.config.americanEnd) };

        let currentSessionType = null;
        if (totalMinutes >= asianMinutes.start && totalMinutes < asianMinutes.end) {
            currentSessionType = 'asian';
        } else if (totalMinutes >= europeanMinutes.start && totalMinutes < europeanMinutes.end) {
            currentSessionType = 'european';
        } else if (totalMinutes >= americanMinutes.start && totalMinutes < americanMinutes.end) {
            currentSessionType = 'american';
        }

        // 🔥 NEU: Hole ALLE Levels inkl. durchbrochene mit Grace Period
        const { highs, lows, brokenHighs, brokenLows } = this.getAllLevelsWithGracePeriod(currentPrice);

        // ========================================
        // CLEANUP: Entferne Trigger für Levels die nicht mehr sichtbar sind
        // ========================================
        const allVisiblePrices = [
            ...highs.map(h => h.price),
            ...lows.map(l => l.price),
            ...brokenHighs.map(h => h.price),
            ...brokenLows.map(l => l.price)
        ];

        const beforeCleanup = this.triggeredLevels.length;
        this.triggeredLevels = this.triggeredLevels.filter(trigger => {
            const isStillVisible = allVisiblePrices.some(
                price => Math.abs(price - trigger.price) < 0.1
            );

            return isStillVisible;
        });

        // Kombiniere unbroken + broken Levels für Near/Broken Detection
        const allHighs = [...highs, ...brokenHighs];
        const allLows = [...lows, ...brokenLows];

        // Wenn keine Levels verfügbar → return false für alles
        if (allHighs.length === 0 && allLows.length === 0) {
            return {
                session_high_broken: false,
                session_low_broken: false,
                session_high_first_break: false,
                session_low_first_break: false,
                session_high_price: null,
                session_low_price: null,
                current_session: currentSessionType || 'unknown'
            };
        }

        // Fixed Threshold (absolute Punkte, nicht prozentual)
        const brokenThreshold = 50;  // 50 Punkte für "broken" Anzeige

        // Sortiere Highs/Lows nach Distanz zum Preis (nächstes zuerst)
        allHighs.sort((a, b) => a.price - b.price); // Aufsteigend (nächstes High über Preis)
        allLows.sort((a, b) => b.price - a.price);  // Absteigend (nächstes Low unter Preis)

        // 🔥 FIX: Nächstes High/Low AUCH finden wenn Preis das Level bereits gebrochen hat!
        // Wähle das NÄCHSTE gebrochene Level in Range (nicht das niedrigste/höchste)

        // Nächstes High: Priorisiere broken Levels in Range, dann ungebrochene über Preis
        let nextHigh = null;

        // 🔥 PRIORITÄT 1: Gebrochenes High in Range (Grace Period)
        if (brokenHighs.length > 0) {
            const brokenInRange = brokenHighs
                .filter(h => {
                    const distance = Math.abs(currentPrice - h.price);
                    return distance <= brokenThreshold;
                })
                .map(h => ({
                    ...h,
                    distance: Math.abs(currentPrice - h.price)
                }))
                .sort((a, b) => a.distance - b.distance); // Nächstes zuerst

            nextHigh = brokenInRange[0] || null;
        }

        // 🔥 PRIORITÄT 2: Falls kein broken Level in Range → nächstes ungebrochenes über Preis
        if (!nextHigh) {
            nextHigh = allHighs.find(h => h.price > currentPrice) || null;
        }

        // Nächstes Low: Priorisiere broken Levels in Range, dann ungebrochene unter Preis
        let nextLow = null;

        // 🔥 PRIORITÄT 1: Gebrochenes Low in Range (Grace Period)
        if (brokenLows.length > 0) {
            const brokenInRange = brokenLows
                .filter(l => {
                    const distance = Math.abs(currentPrice - l.price);
                    return distance <= brokenThreshold;
                })
                .map(l => ({
                    ...l,
                    distance: Math.abs(currentPrice - l.price)
                }))
                .sort((a, b) => a.distance - b.distance); // Nächstes zuerst

            nextLow = brokenInRange[0] || null;
        }

        // 🔥 PRIORITÄT 2: Falls kein broken Level in Range → nächstes ungebrochenes unter Preis
        if (!nextLow) {
            nextLow = allLows.find(l => l.price < currentPrice) || null;
        }

        // ========================================
        // DISTANCE CALCULATION (für Broken Detection)
        // ========================================
        let sessionHigh = null;
        let distanceToHigh = null;
        let sessionLow = null;
        let distanceToLow = null;

        if (nextHigh) {
            sessionHigh = nextHigh.price;
            distanceToHigh = Math.abs(currentPrice - sessionHigh);
        }

        if (nextLow) {
            sessionLow = nextLow.price;
            distanceToLow = Math.abs(currentPrice - sessionLow);
        }

        // ========================================
        // BROKEN DETECTION - State Tracking: Einmal aus = für immer blockiert
        // BUGFIX: Deaktivierungs-Check AUSSERHALB von Distance-Check!
        // ========================================
        let highBroken = false;
        let lowBroken = false;
        let highFirstBreak = false;
        let lowFirstBreak = false;

        // BROKEN HIGH CHECK (Liq Zone um Level nach Durchbruch)
        if (nextHigh) {
            const priceKey = nextHigh.price.toFixed(2);
            const isBroken = brokenHighs.some(h => Math.abs(h.price - nextHigh.price) < 0.1);
            const inZone = distanceToHigh <= brokenThreshold; // In 50-Punkte Zone

            // AKTIVIERUNGS-CHECK: Level durchbrochen UND in Zone
            if (isBroken && inZone) {
                if (this.hadBrokenHighs.has(priceKey)) {
                    // War schon mal aktiv + deaktiviert → PERMANENT BLOCKIERT
                    console.log(`🚫 [Broken High] PERMANENT BLOCKIERT für ${priceKey}`);
                } else {
                    // Darf aktivieren
                    highBroken = true;
                    this.currentBrokenHighs.add(priceKey);

                    // First Break Detection
                    if (!this.lastBrokenHighPrice || Math.abs(this.lastBrokenHighPrice - nextHigh.price) > 0.1) {
                        highFirstBreak = true;
                        this.lastBrokenHighPrice = nextHigh.price;
                        console.log(`🔔 [Broken High] AKTIVIERT für ${priceKey} (First Break)`);
                    }
                }
            }

            // DEAKTIVIERUNGS-CHECK: Preis verlässt die Zone (>50 Punkte weg)!
            if (this.currentBrokenHighs.has(priceKey) && !inZone) {
                // War gerade aktiv, jetzt außerhalb Zone → DEAKTIVIERUNG!
                this.currentBrokenHighs.delete(priceKey);
                this.hadBrokenHighs.add(priceKey);
                console.log(`⚠️ [Broken High] DEAKTIVIERT für ${priceKey} (Distance: ${distanceToHigh.toFixed(0)}pts) → PERMANENT BLOCKIERT!`);
            }
        }

        // BROKEN LOW CHECK (Liq Zone um Level nach Durchbruch)
        if (nextLow) {
            const priceKey = nextLow.price.toFixed(2);
            const isBroken = brokenLows.some(l => Math.abs(l.price - nextLow.price) < 0.1);
            const inZone = distanceToLow <= brokenThreshold; // In 50-Punkte Zone

            // AKTIVIERUNGS-CHECK: Level durchbrochen UND in Zone
            if (isBroken && inZone) {
                if (this.hadBrokenLows.has(priceKey)) {
                    // War schon mal aktiv + deaktiviert → PERMANENT BLOCKIERT
                    console.log(`🚫 [Broken Low] PERMANENT BLOCKIERT für ${priceKey}`);
                } else {
                    // Darf aktivieren
                    lowBroken = true;
                    this.currentBrokenLows.add(priceKey);

                    // First Break Detection
                    if (!this.lastBrokenLowPrice || Math.abs(this.lastBrokenLowPrice - nextLow.price) > 0.1) {
                        lowFirstBreak = true;
                        this.lastBrokenLowPrice = nextLow.price;
                        console.log(`🔔 [Broken Low] AKTIVIERT für ${priceKey} (First Break)`);
                    }
                }
            }

            // DEAKTIVIERUNGS-CHECK: Preis verlässt die Zone (>50 Punkte weg)!
            if (this.currentBrokenLows.has(priceKey) && !inZone) {
                // War gerade aktiv, jetzt außerhalb Zone → DEAKTIVIERUNG!
                this.currentBrokenLows.delete(priceKey);
                this.hadBrokenLows.add(priceKey);
                console.log(`⚠️ [Broken Low] DEAKTIVIERT für ${priceKey} (Distance: ${distanceToLow.toFixed(0)}pts) → PERMANENT BLOCKIERT!`);
            }
        }

        // ========================================
        // RETURN STATE
        // ========================================
        return {
            session_high_broken: highBroken,
            session_low_broken: lowBroken,
            session_high_first_break: highFirstBreak,
            session_low_first_break: lowFirstBreak,
            session_high_price: sessionHigh,
            session_low_price: sessionLow,
            current_session: currentSessionType || 'unknown',
            distance_to_high: distanceToHigh,
            distance_to_low: distanceToLow
        };
    }
}

// ============================================================
// FVG INDICATOR - Fair Value Gap
// ============================================================

class FVGIndicator extends BaseIndicator {
    constructor(id, config = {}) {
        // Default Config
        const defaultConfig = {
            bullishColor: 'rgba(0, 255, 0, 0.15)',
            bearishColor: 'rgba(255, 0, 0, 0.15)',
            minGapSize: 0, // Minimale Gap-Größe in Punkten (0 = alle)
            boxDisplayLength: 50 // Wie viele Kerzen die Box lang ist (0 = bis Chart-Ende)
        };

        super(id, 'FVG', { ...defaultConfig, ...config });

        this.fvgBoxes = []; // Array of {primitive, type, top, bottom, startTime, endTime}
        this.candlestickSeries = null;
    }

    calculate(data) {
        // FVG Erkennung: 3-Kerzen Muster
        if (!data || data.length < 3) {
            console.warn('⚠️ FVG: Nicht genug Daten für FVG-Analyse');
            return [];
        }

        const fvgs = [];

        // Iteriere durch Daten (Start bei Index 1, Ende bei length-1 für 3-Kerzen Fenster)
        for (let i = 1; i < data.length - 1; i++) {
            const prev = data[i - 1];
            const curr = data[i];
            const next = data[i + 1];

            // Bullish FVG: prev.high < next.low (Lücke nach oben)
            if (prev.high < next.low) {
                const gapSize = next.low - prev.high;

                if (gapSize >= this.config.minGapSize) {
                    fvgs.push({
                        type: 'bullish',
                        top: next.low,
                        bottom: prev.high,
                        startTime: curr.time,
                        endTime: null, // Wird später gesetzt (aktuellste Kerze)
                        filled: false
                    });
                }
            }

            // Bearish FVG: prev.low > next.high (Lücke nach unten)
            if (prev.low > next.high) {
                const gapSize = prev.low - next.high;

                if (gapSize >= this.config.minGapSize) {
                    fvgs.push({
                        type: 'bearish',
                        top: prev.low,
                        bottom: next.high,
                        startTime: curr.time,
                        endTime: null,
                        filled: false
                    });
                }
            }
        }

        this.data = fvgs;
        return fvgs;
    }

    render(chart) {
        if (!chart) {
            console.error('❌ FVG render: Chart nicht verfügbar');
            return;
        }

        // Hole Candlestick Series
        this.candlestickSeries = window.candlestickSeries;
        if (!this.candlestickSeries) {
            console.error('❌ FVG render: Candlestick Series nicht verfügbar');
            return;
        }

        // Hole Chart-Daten
        const candleData = this.candlestickSeries.data();
        if (!candleData || candleData.length === 0) {
            console.warn('⚠️ FVG render: Keine Chart-Daten verfügbar');
            return;
        }

        // Berechne FVGs
        const fvgs = this.calculate(candleData);

        // Rendere FVG Boxen
        this.renderFVGBoxes(chart, fvgs, candleData);
    }

    renderFVGBoxes(chart, fvgs, candleData) {
        // Cleanup alte Boxen
        this.clearFVGBoxes();

        if (!fvgs || fvgs.length === 0) {
            return;
        }

        // Letzte Kerzenzeit
        const lastCandleTime = candleData[candleData.length - 1].time;

        // Prüfe welche FVGs gefüllt wurden (Preis durch Gap gelaufen)
        fvgs.forEach(fvg => {
            if (!fvg.filled) {
                // Finde alle Kerzen NACH der FVG-Entstehung
                const candlesAfterFVG = candleData.filter(c => c.time > fvg.startTime);

                for (const candle of candlesAfterFVG) {
                    // Bullish FVG: Gefüllt nur wenn CLOSE unter bottom schließt (nicht nur Docht!)
                    if (fvg.type === 'bullish' && candle.close < fvg.bottom) {
                        fvg.filled = true;
                        break;
                    }
                    // Bearish FVG: Gefüllt nur wenn CLOSE über top schließt (nicht nur Docht!)
                    if (fvg.type === 'bearish' && candle.close > fvg.top) {
                        fvg.filled = true;
                        break;
                    }
                }
            }
        });

        // Nur OFFENE FVGs rendern
        const openFVGs = fvgs.filter(fvg => !fvg.filled);
        const filledFVGs = fvgs.filter(fvg => fvg.filled);

        let renderedCount = 0;
        openFVGs.forEach((fvg, index) => {
            // Berechne endTime basierend auf boxDisplayLength
            let endTime = lastCandleTime;

            if (this.config.boxDisplayLength > 0) {
                // Finde Index der FVG-Start-Kerze
                const startIndex = candleData.findIndex(c => c.time === fvg.startTime);
                if (startIndex !== -1) {
                    // Berechne End-Index: FVG-Start + boxDisplayLength Kerzen
                    const endIndex = Math.min(startIndex + this.config.boxDisplayLength, candleData.length - 1);
                    endTime = candleData[endIndex].time;
                }
            }
            // Wenn boxDisplayLength = 0, geht die Box bis zum Chart-Ende (lastCandleTime)

            const fillColor = fvg.type === 'bullish'
                ? this.config.bullishColor
                : this.config.bearishColor;

            const p1 = { time: fvg.startTime, price: fvg.bottom };
            const p2 = { time: endTime, price: fvg.top };

            // Erstelle Rectangle Primitive
            const rectangle = new SessionRectangle(
                p1,
                p2,
                fillColor,
                chart,
                this.candlestickSeries,
                null, // Kein Label für FVG
                null
            );

            try {
                this.candlestickSeries.attachPrimitive(rectangle);
                this.fvgBoxes.push({
                    primitive: rectangle,
                    type: fvg.type,
                    top: fvg.top,
                    bottom: fvg.bottom,
                    startTime: fvg.startTime
                });
                renderedCount++;
            } catch (e) {
                console.error(`❌ FVG: Fehler beim Attach von Box #${index + 1}:`, e);
            }
        });
    }

    clearFVGBoxes() {
        if (!this.candlestickSeries || !this.fvgBoxes || this.fvgBoxes.length === 0) {
            return;
        }

        this.fvgBoxes.forEach(box => {
            try {
                this.candlestickSeries.detachPrimitive(box.primitive);
            } catch (e) {
                console.warn('⚠️ FVG: Fehler beim Detach:', e);
            }
        });

        this.fvgBoxes = [];

        // Force Chart Update nach dem Detach (uses generelle BaseIndicator Methode)
        this.requestChartUpdate();
    }

    update(candle, allData) {
        if (!this.visible || !allData) {
            return;
        }

        // 🔥 KOMPLETTER RELOAD (Go To Date / Timeframe Switch)
        if (!candle && allData.length > 0) {
            // Update candlestickSeries reference (könnte sich geändert haben)
            this.candlestickSeries = window.candlestickSeries;

            if (!this.candlestickSeries) {
                console.warn('⚠️ FVG Update: Candlestick Series nicht verfügbar');
                return;
            }

            // Berechne FVGs neu
            const fvgs = this.calculate(allData);

            // Rendere alle FVGs neu
            this.renderFVGBoxes(window.chart, fvgs, allData);
            return;
        }

        // 🔄 INKREMENTELLES UPDATE (einzelne Kerze)
        if (!this.candlestickSeries || !candle) {
            return;
        }

        // Prüfe ob FVGs gefüllt wurden
        let needsRerender = false;
        const currentPrice = candle.close;

        this.data.forEach(fvg => {
            if (!fvg.filled) {
                // Check if price completely filled the gap
                // Bullish FVG: filled wenn Preis unter bottom fällt
                // Bearish FVG: filled wenn Preis über top steigt

                if (fvg.type === 'bullish' && currentPrice < fvg.bottom) {
                    fvg.filled = true;
                    needsRerender = true;
                } else if (fvg.type === 'bearish' && currentPrice > fvg.top) {
                    fvg.filled = true;
                    needsRerender = true;
                }
            }
        });

        // Bei neuer Kerze: Prüfe auf neue FVGs
        if (allData.length >= 3) {
            const newFVGs = this.calculate(allData);

            // Wenn neue FVGs gefunden: Re-render
            if (newFVGs.length !== this.data.length) {
                this.data = newFVGs;
                needsRerender = true;
            }
        }

        // Re-render wenn nötig
        if (needsRerender && window.chart) {
            this.renderFVGBoxes(window.chart, this.data, allData);
        }
    }

    destroy() {
        this.clearFVGBoxes();
        this.candlestickSeries = null;
        this.data = null;
    }

    getDisplayName() {
        return 'FVG';
    }

    // Settings für FVG
    getSettingsHTML() {
        return `
            <style>
                .fvg-settings-container {
                    display: flex;
                    flex-direction: column;
                    gap: 20px;
                }
                .fvg-section {
                    background: rgba(255, 255, 255, 0.03);
                    border-radius: 8px;
                    padding: 15px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
                .fvg-section-title {
                    font-weight: bold;
                    font-size: 14px;
                    margin-bottom: 12px;
                    color: #fff;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .fvg-slider-container {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-top: 8px;
                }
                .fvg-slider {
                    flex: 1;
                    height: 6px;
                    -webkit-appearance: none;
                    appearance: none;
                    background: rgba(255, 255, 255, 0.1);
                    outline: none;
                    border-radius: 3px;
                }
                .fvg-slider::-webkit-slider-thumb {
                    -webkit-appearance: none;
                    appearance: none;
                    width: 16px;
                    height: 16px;
                    background: #00fbff;
                    cursor: pointer;
                    border-radius: 50%;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }
                .fvg-slider::-moz-range-thumb {
                    width: 16px;
                    height: 16px;
                    background: #00fbff;
                    cursor: pointer;
                    border-radius: 50%;
                    border: none;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                }
                .fvg-value-display {
                    min-width: 60px;
                    text-align: center;
                    font-weight: bold;
                    color: #00fbff;
                    font-size: 14px;
                    background: rgba(0, 251, 255, 0.1);
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                .fvg-color-grid {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 15px;
                    margin-top: 10px;
                }
                .fvg-color-item {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .fvg-color-preview {
                    width: 100%;
                    height: 40px;
                    border-radius: 6px;
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    cursor: pointer;
                    transition: border-color 0.2s;
                }
                .fvg-color-preview:hover {
                    border-color: #00fbff;
                }
                .fvg-info-box {
                    background: rgba(0, 251, 255, 0.05);
                    border-left: 3px solid #00fbff;
                    padding: 10px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                    color: rgba(255, 255, 255, 0.8);
                    margin-top: 8px;
                }
            </style>

            <div class="fvg-settings-container">
                <!-- Detection Section -->
                <div class="fvg-section">
                    <div class="fvg-section-title">
                        <span>🔍</span>
                        <span>FVG Erkennung</span>
                    </div>

                    <label style="color: rgba(255,255,255,0.9); font-size: 13px;">Minimale Gap-Größe (Punkte):</label>
                    <div class="fvg-slider-container">
                        <input type="range" id="edit_fvg_minGapSize" class="fvg-slider"
                               value="${this.config.minGapSize}" min="0" max="50" step="1"
                               oninput="document.getElementById('fvg_minGapSize_display').textContent = this.value + ' Punkte'">
                        <div class="fvg-value-display" id="fvg_minGapSize_display">${this.config.minGapSize} Punkte</div>
                    </div>
                    <div class="fvg-info-box">
                        💡 <strong>Tipp:</strong> Bei 0 werden alle FVGs erkannt. Höhere Werte filtern kleine, unwichtige Gaps.
                    </div>
                </div>

                <!-- Display Section -->
                <div class="fvg-section">
                    <div class="fvg-section-title">
                        <span>📏</span>
                        <span>Anzeige-Optionen</span>
                    </div>

                    <label style="color: rgba(255,255,255,0.9); font-size: 13px;">FVG Box-Anzeigelänge (Kerzen):</label>
                    <div class="fvg-slider-container">
                        <input type="range" id="edit_fvg_boxDisplayLength" class="fvg-slider"
                               value="${this.config.boxDisplayLength}" min="0" max="200" step="10"
                               oninput="document.getElementById('fvg_boxDisplayLength_display').textContent = this.value === '0' ? 'Bis Chart-Ende' : this.value + ' Kerzen'">
                        <div class="fvg-value-display" id="fvg_boxDisplayLength_display">${this.config.boxDisplayLength === 0 ? 'Bis Chart-Ende' : this.config.boxDisplayLength + ' Kerzen'}</div>
                    </div>
                    <div class="fvg-info-box">
                        💡 <strong>Info:</strong> Wie viele Kerzen lang die FVG-Box nach rechts gezeichnet wird. Alle offenen FVGs werden immer angezeigt!
                    </div>
                </div>

                <!-- Colors Section -->
                <div class="fvg-section">
                    <div class="fvg-section-title">
                        <span>🎨</span>
                        <span>Farben</span>
                    </div>

                    <div class="fvg-color-grid">
                        <div class="fvg-color-item">
                            <label style="color: rgba(255,255,255,0.9); font-size: 13px; font-weight: 600;">
                                🟢 Bullish FVG
                            </label>
                            <input type="color" id="edit_fvg_bullishColor" class="fvg-color-preview"
                                   value="${this.rgbaToHex(this.config.bullishColor)}"
                                   style="background: ${this.config.bullishColor};">
                            <small style="color: rgba(255,255,255,0.6); font-size: 11px;">Support-Zonen</small>
                        </div>

                        <div class="fvg-color-item">
                            <label style="color: rgba(255,255,255,0.9); font-size: 13px; font-weight: 600;">
                                🔴 Bearish FVG
                            </label>
                            <input type="color" id="edit_fvg_bearishColor" class="fvg-color-preview"
                                   value="${this.rgbaToHex(this.config.bearishColor)}"
                                   style="background: ${this.config.bearishColor};">
                            <small style="color: rgba(255,255,255,0.6); font-size: 11px;">Resistance-Zonen</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    rgbaToHex(rgba) {
        // Extrahiere RGB aus rgba String (quick & dirty)
        if (rgba.startsWith('#')) return rgba;

        const match = rgba.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
        if (match) {
            const r = parseInt(match[1]).toString(16).padStart(2, '0');
            const g = parseInt(match[2]).toString(16).padStart(2, '0');
            const b = parseInt(match[3]).toString(16).padStart(2, '0');
            return `#${r}${g}${b}`;
        }
        return '#00ff00';
    }

    applySettings() {
        this.config.minGapSize = parseFloat(document.getElementById('edit_fvg_minGapSize')?.value) || 0;
        this.config.boxDisplayLength = parseInt(document.getElementById('edit_fvg_boxDisplayLength')?.value) || 50;

        // Konvertiere Hex zu RGBA
        const bullishHex = document.getElementById('edit_fvg_bullishColor')?.value || '#00ff00';
        const bearishHex = document.getElementById('edit_fvg_bearishColor')?.value || '#ff0000';

        this.config.bullishColor = this.hexToRgba(bullishHex, 0.15);
        this.config.bearishColor = this.hexToRgba(bearishHex, 0.15);

        // Re-render
        const candleData = window.candlestickSeries?.data();
        if (candleData && candleData.length > 0) {
            this.calculate(candleData);
            this.render(window.chart);
        }
    }

    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    toggleVisibility() {
        this.visible = !this.visible;

        // FVG verwendet Primitives (SessionRectangle) mit _visible Flag
        if (!this.candlestickSeries || !this.fvgBoxes || this.fvgBoxes.length === 0) {
            console.warn('⚠️ FVG: Keine FVG Boxen zum Togglen verfügbar');
            return;
        }

        // Setze _visible Flag für alle FVG Boxen
        this.fvgBoxes.forEach(box => {
            if (box.primitive) {
                box.primitive._visible = this.visible;
                box.primitive.updateAllViews(); // Update Views
            }
        });

        // Force Chart Update (uses generelle BaseIndicator Methode)
        this.requestChartUpdate();

        console.log(`👁️ ${this.type}(${this.id}) Visibility: ${this.visible} (${this.fvgBoxes.length} Boxen)`);
    }

    getCurrentState(currentPrice) {
        // FVG Zone Detection für RL Agent
        // WICHTIG: Nutze this.data (calculated FVGs), nicht fvgBoxes (rendered boxes)!
        if (!this.data || this.data.length === 0) {
            console.log('[FVG getCurrentState] Keine FVG Daten verfügbar');
            return {
                in_fvg: false,
                fvg_type: null,
                fvg_top: null,
                fvg_bottom: null,
                distance_to_fvg: null
            };
        }

        // Hole aktuellen Preis
        if (!currentPrice) {
            const candleData = window.candlestickSeries?.data();
            if (!candleData || candleData.length === 0) {
                return {
                    in_fvg: false,
                    fvg_type: null,
                    fvg_top: null,
                    fvg_bottom: null,
                    distance_to_fvg: null
                };
            }
            currentPrice = candleData[candleData.length - 1].close;
        }

        // Prüfe nur OFFENE FVGs (nicht gefüllte)
        const openFVGs = this.data.filter(fvg => !fvg.filled);

        // Prüfe ob Preis in einer FVG Zone ist
        for (const fvg of openFVGs) {
            const top = fvg.top;
            const bottom = fvg.bottom;

            // Ist Preis innerhalb der Zone?
            if (currentPrice >= bottom && currentPrice <= top) {
                return {
                    in_fvg: true,
                    fvg_type: fvg.type, // 'bullish' or 'bearish'
                    fvg_top: top,
                    fvg_bottom: bottom,
                    distance_to_fvg: 0
                };
            }
        }

        // Nicht in FVG → finde nächste FVG
        let closestDistance = Infinity;
        let closestFVG = null;

        for (const fvg of openFVGs) {
            const top = fvg.top;
            const bottom = fvg.bottom;

            // Distanz zur Zone (Mitte)
            const zoneMid = (top + bottom) / 2;
            const distance = Math.abs(currentPrice - zoneMid);

            if (distance < closestDistance) {
                closestDistance = distance;
                closestFVG = fvg;
            }
        }

        return {
            in_fvg: false,
            fvg_type: closestFVG?.type || null,
            fvg_top: closestFVG?.top || null,
            fvg_bottom: closestFVG?.bottom || null,
            distance_to_fvg: closestDistance !== Infinity ? closestDistance : null
        };
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
        // Indikator registriert
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

        // Render auf Chart mit Auto-Retry (Race Condition Protection)
        const tryRender = (retryCount = 0) => {
            try {
                indicator.render(window.chart);
                console.log(`✅ Indikator hinzugefügt: ${type} (ID: ${id})`);

                // Speichern
                this.activeIndicators.set(id, indicator);

                // CRITICAL: Nur speichern wenn nicht vom Load aufgerufen (verhindert Duplikation)
                if (!skipSave) {
                    this.saveState();
                }

                // UI-Label rendern
                this.renderLabels();
            } catch (e) {
                if (retryCount < 2) {
                    // Retry nach kurzer Wartezeit (Chart noch nicht ready)
                    console.warn(`⚠️ Indikator-Render fehlgeschlagen (Versuch ${retryCount + 1}/3), retry in ${100 * (retryCount + 1)}ms:`, e.message);
                    setTimeout(() => tryRender(retryCount + 1), 100 * (retryCount + 1));
                } else {
                    // Nach 3 Versuchen: Aufgeben aber Indikator behalten für manuellen Retry
                    console.error(`❌ Indikator-Render fehlgeschlagen nach 3 Versuchen: ${type} (ID: ${id})`, e);
                    // Speichere trotzdem (User kann später neu laden)
                    this.activeIndicators.set(id, indicator);
                    if (!skipSave) {
                        this.saveState();
                    }
                }
            }
        };

        tryRender();
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
        // CRITICAL FIX: Update nur das spezifische Label statt alle neu zu rendern
        // Verhindert Doppel-Toggle durch Event-Propagation zu neu erstellten Buttons
        this.updateIndicatorLabel(id);
    }

    // Settings Update
    updateIndicatorConfig(id, newConfig) {
        const indicator = this.activeIndicators.get(id);

        if (!indicator) {
            console.warn(`⚠️ Indikator nicht gefunden: ${id}`);
            return;
        }

        indicator.setConfig(newConfig);

        // 🔄 CRITICAL FIX: Re-render ALLE Indikatoren statt nur den einen
        // Grund: TradingView Legend cached alte Einträge bei removeSeries()
        // Lösung: Alle Indikatoren neu rendern → Legend wird komplett neu gebaut
        const chartData = window.candlestickSeries?.data();
        if (chartData && chartData.length > 0 && window.chart) {
            // Entferne ALLE Series von ALLEN Indikatoren
            this.activeIndicators.forEach(ind => {
                if (ind.series) {
                    try {
                        window.chart.removeSeries(ind.series);
                        ind.series = null;
                    } catch (e) {
                        console.warn('⚠️ Fehler beim Entfernen der Series:', e);
                    }
                }
            });

            // Rendere ALLE Indikatoren neu (inkl. dem geänderten)
            this.reRenderAll(window.chart);
            console.log(`🔄 Alle Indikatoren neu gerendert (Legend-Ghost-Bug-Fix)`);
        }

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
            // Indikatoren gespeichert
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

            // Indikatoren wiederhergestellt
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

        // Labels gerendert
    }

    // UI: Einzelnes Label updaten (ohne DOM-Neubildung → verhindert Event-Propagation)
    updateIndicatorLabel(id) {
        const indicator = this.activeIndicators.get(id);
        if (!indicator) {
            console.warn(`⚠️ Indikator nicht gefunden: ${id}`);
            return;
        }

        // Finde das existierende Label-Element
        const container = document.getElementById('indicatorLabels');
        if (!container) {
            console.warn('⚠️ Indicator Labels Container nicht gefunden');
            return;
        }

        const labelElement = container.querySelector(`[data-id="${id}"]`);
        if (!labelElement) {
            console.warn(`⚠️ Label-Element nicht gefunden für ${id} - verwende renderLabels() als Fallback`);
            this.renderLabels();
            return;
        }

        // Update nur Eye-Icon und Visibility-Klasse (OHNE Button neu zu erstellen)
        const eyeIcon = indicator.visible ? '👁️' : '👁️‍🗨️';
        const visibleClass = indicator.visible ? 'visible' : 'hidden';

        // Update Eye-Icon im Button
        const eyeButton = labelElement.querySelector('.indicator-control-btn[title="Toggle Visibility"]');
        if (eyeButton) {
            eyeButton.textContent = eyeIcon;
        }

        // Update Visibility-Klasse des Namens
        const nameSpan = labelElement.querySelector('.indicator-name');
        if (nameSpan) {
            nameSpan.className = `indicator-name ${visibleClass}`;
        }

        console.log(`🔄 Label updated für ${id} (visible: ${indicator.visible})`);
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

        // SESSION Indikator → Spezielles Modal
        if (indicator.type === 'SESSION') {
            this.openSessionSettings(indicator);
            return;
        }

        // Indikator mit getSettingsHTML() → Custom Settings
        if (typeof indicator.getSettingsHTML === 'function') {
            this.openCustomSettings(indicator);
            return;
        }

        // EMA & andere → Standard Modal
        // Fülle Modal mit aktuellen Werten
        const modal = document.getElementById('indicatorSettingsModal');
        const periodInput = document.getElementById('indicatorPeriodInput');
        const colorInput = document.getElementById('indicatorColorInput');
        const lineWidthInput = document.getElementById('indicatorLineWidthInput');

        if (periodInput) periodInput.value = indicator.config.period || 9;
        if (colorInput) colorInput.value = indicator.config.color || '#000000';
        if (lineWidthInput) lineWidthInput.value = indicator.config.lineWidth || 2;

        // Öffne Modal
        if (modal) {
            modal.style.display = 'flex';
            console.log(`⚙️ Settings Modal geöffnet für ${indicator.getDisplayName()}`);
        }
    }

    // UI: Session Settings Modal öffnen
    openSessionSettings(indicator) {
        const modal = document.getElementById('sessionSettingsModal');
        if (!modal) {
            console.error('❌ Session Settings Modal nicht gefunden');
            return;
        }

        // Fülle Modal mit aktuellen Werten
        const config = indicator.config;

        // UTC Offset (0 ist valide!)
        document.getElementById('sessionUtcOffsetInput').value = config.utcOffset !== undefined ? config.utcOffset : 2;

        // Transparenz
        document.getElementById('sessionTransparencyInput').value = config.transparency || 10;
        document.getElementById('sessionTransparencyValue').textContent = config.transparency || 10;

        // Asian Session
        document.getElementById('sessionAsianStart').value = config.asianStart || '00:00';
        document.getElementById('sessionAsianEnd').value = config.asianEnd || '08:00';
        document.getElementById('sessionAsianColor').value = config.asianColor || '#FFD700';

        // European Session
        document.getElementById('sessionEuropeanStart').value = config.europeanStart || '08:00';
        document.getElementById('sessionEuropeanEnd').value = config.europeanEnd || '14:30';
        document.getElementById('sessionEuropeanColor').value = config.europeanColor || '#00FF00';

        // American Session
        document.getElementById('sessionAmericanStart').value = config.americanStart || '14:30';
        document.getElementById('sessionAmericanEnd').value = config.americanEnd || '22:00';
        document.getElementById('sessionAmericanColor').value = config.americanColor || '#1E90FF';

        // High/Low Lines
        document.getElementById('sessionHighLowColor').value = config.highLowColor || '#FFFFFF';
        document.getElementById('sessionHighLowWidth').value = config.highLowWidth || 1;

        // Handelstage-Rückblick (null = leer, Zahl = Wert)
        document.getElementById('sessionTradingDaysInput').value = config.tradingDaysLookback !== null ? config.tradingDaysLookback : '';

        // Öffne Modal
        modal.style.display = 'flex';
    }

    // UI: Session Settings anwenden
    applySessionSettings() {
        const indicator = window.currentIndicatorForSettings;

        if (!indicator || indicator.type !== 'SESSION') {
            return;
        }

        // Lese neue Config
        const utcOffsetValue = document.getElementById('sessionUtcOffsetInput').value;
        const tradingDaysValue = document.getElementById('sessionTradingDaysInput').value.trim();

        const newConfig = {
            utcOffset: utcOffsetValue !== '' ? parseInt(utcOffsetValue) : 2,  // Fix: 0 ist valide!
            transparency: parseInt(document.getElementById('sessionTransparencyInput').value) || 10,

            asianStart: document.getElementById('sessionAsianStart').value || '00:00',
            asianEnd: document.getElementById('sessionAsianEnd').value || '08:00',
            asianColor: document.getElementById('sessionAsianColor').value || '#FFD700',

            europeanStart: document.getElementById('sessionEuropeanStart').value || '08:00',
            europeanEnd: document.getElementById('sessionEuropeanEnd').value || '14:30',
            europeanColor: document.getElementById('sessionEuropeanColor').value || '#00FF00',

            americanStart: document.getElementById('sessionAmericanStart').value || '14:30',
            americanEnd: document.getElementById('sessionAmericanEnd').value || '22:00',
            americanColor: document.getElementById('sessionAmericanColor').value || '#1E90FF',

            highLowColor: document.getElementById('sessionHighLowColor').value || '#FFFFFF',
            highLowWidth: parseInt(document.getElementById('sessionHighLowWidth').value) || 1,

            // MODUS SWITCH: Leer = null (unbegrenzt), Zahl = begrenzt
            tradingDaysLookback: tradingDaysValue === '' ? null : parseInt(tradingDaysValue)
        };

        // Update Indikator
        this.updateIndicatorConfig(indicator.id, newConfig);

        // Modal schließen
        this.closeSessionSettingsModal();
    }

    closeSessionSettingsModal() {
        const modal = document.getElementById('sessionSettingsModal');
        if (modal) {
            modal.style.display = 'none';
        }
        window.currentIndicatorForSettings = null;
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
        const lineWidthInput = document.getElementById('indicatorLineWidthInput');  // Blueprint Property

        const newConfig = {
            period: parseInt(periodInput.value) || indicator.config.period,
            color: colorInput.value || indicator.config.color,
            lineWidth: parseInt(lineWidthInput.value) || indicator.config.lineWidth  // Blueprint Property
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

    // UI: Custom Settings Modal öffnen (für Indikatoren mit getSettingsHTML())
    openCustomSettings(indicator) {
        const modal = document.getElementById('indicatorSettingsModal');
        if (!modal) {
            console.error('❌ Settings Modal nicht gefunden');
            return;
        }

        // Hole Custom HTML vom Indikator
        const customHTML = indicator.getSettingsHTML();

        // Finde Settings Content Container
        const settingsContent = modal.querySelector('.settings-content');
        const modalButtons = modal.querySelector('.date-modal-buttons');

        if (!settingsContent || !modalButtons) {
            console.error('❌ Settings Content oder Buttons Container nicht gefunden');
            return;
        }

        // Ersetze Content mit Custom HTML
        settingsContent.innerHTML = customHTML;

        // Ersetze Buttons
        modalButtons.innerHTML = `
            <button class="modal-btn" onclick="window.IndicatorManager.closeSettingsModal()">Abbrechen</button>
            <button class="modal-btn primary" onclick="window.IndicatorManager.applyCustomSettings()">💾 Speichern</button>
        `;

        // Öffne Modal
        modal.style.display = 'flex';
        console.log(`⚙️ Custom Settings Modal geöffnet für ${indicator.getDisplayName()}`);
    }

    // UI: Custom Settings anwenden
    applyCustomSettings() {
        const indicator = window.currentIndicatorForSettings;

        if (!indicator || typeof indicator.applySettings !== 'function') {
            console.warn('⚠️ Kein Custom Settings Indikator ausgewählt oder applySettings() fehlt');
            return;
        }

        // Rufe die applySettings() Methode des Indikators auf
        indicator.applySettings();

        // Modal schließen
        this.closeSettingsModal();

        console.log(`✅ Custom Settings angewendet für ${indicator.getDisplayName()}`);
    }

    // ========================================
    // API: Get Market Context for AI
    // ========================================
    getMarketContext(currentPrice, currentTime) {
        // Initialize context with defaults
        const context = {
            // FVG
            in_fvg: false,
            fvg_type: null,

            // Session High/Low
            session_high_broken: false,
            session_low_broken: false,
            session_high_first_break: false,
            session_low_first_break: false,
            session_high_price: null,
            session_low_price: null,
            current_session: null,

            // Volume
            volume_spike: false,
            volume_ratio: 1.0,

            // Metadata
            current_price: currentPrice,
            current_time: currentTime
        };

        // Iterate through active indicators and call getCurrentState()
        console.log(`🔍 [getMarketContext] activeIndicators.size: ${this.activeIndicators.size}`);
        for (const [id, indicator] of this.activeIndicators) {
            console.log(`🔍 [getMarketContext] Checking indicator: ${indicator.type}, visible: ${indicator.visible}`);
            if (!indicator.visible) {
                console.log(`⚠️ [getMarketContext] SKIPPED ${indicator.type} - not visible!`);
                continue; // Skip hidden indicators
            }

            try {
                // FVG Indicator
                if (indicator.type === 'FVG' && typeof indicator.getCurrentState === 'function') {
                    const fvgState = indicator.getCurrentState(currentPrice);
                    context.in_fvg = fvgState.in_fvg;
                    context.fvg_type = fvgState.fvg_type;
                }

                // Session High/Low Indicator
                if (indicator.type === 'SESSION_HL' && typeof indicator.getCurrentState === 'function') {
                    console.log(`✅ [getMarketContext] Calling SESSION_HL.getCurrentState(${currentPrice})`);
                    const sessionState = indicator.getCurrentState(currentPrice);
                    console.log(`✅ [getMarketContext] SESSION_HL result:`, sessionState);
                    context.session_high_broken = sessionState.session_high_broken;
                    context.session_low_broken = sessionState.session_low_broken;
                    context.session_high_first_break = sessionState.session_high_first_break;
                    context.session_low_first_break = sessionState.session_low_first_break;
                    context.session_high_price = sessionState.session_high_price;
                    context.session_low_price = sessionState.session_low_price;
                    context.current_session = sessionState.current_session;
                }

                // Volume Indicator
                if (indicator.type === 'VOLUME' && typeof indicator.getCurrentState === 'function') {
                    const volumeState = indicator.getCurrentState();
                    context.volume_spike = volumeState.spike;
                    context.volume_ratio = volumeState.ratio;
                }
            } catch (error) {
                console.warn(`[IndicatorManager] Error getting state from ${indicator.type}:`, error);
            }
        }

        // Update Monitor Panel
        if (typeof window.updateRLVisionMonitor === 'function') {
            window.updateRLVisionMonitor(context);
        }

        return context;
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

// Registriere Indikatoren
manager.registerIndicator('EMA', EMAIndicator);
manager.registerIndicator('SESSION', SessionIndicator);
manager.registerIndicator('VOLUME', VolumeIndicator);
manager.registerIndicator('SESSION_HL', SessionHighLowIndicator);
manager.registerIndicator('FVG', FVGIndicator);

// Make globally available
window.IndicatorManager = manager;

console.log('✅ Indicator System bereit (EMA + SESSION + VOLUME + SESSION_HL)');
