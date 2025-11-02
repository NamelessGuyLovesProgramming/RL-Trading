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

        this.visible = true;
        this.series = null; // LightweightCharts Series
        this.data = null;   // Cached calculated data

        console.log(`📊 Indikator erstellt: ${type} (ID: ${id})`, this.config);
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

        console.log('🌍 Session Indikator erstellt:', this.config);
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
            console.warn('⚠️ Session: Keine Daten verfügbar');
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
        const uniqueDays = new Set(ranges.map(r => new Date(r.start * 1000).toISOString().split('T')[0])).size;
        if (this.config.tradingDaysLookback === null) {
            console.log(`✅ ${ranges.length} Sessions in ${uniqueDays} Handelstagen (Unbegrenzter Modus)`);
        } else {
            console.log(`✅ ${ranges.length} Sessions in ${uniqueDays} Handelstagen (Limit: ${this.config.tradingDaysLookback} Tage)`);
        }

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
            console.warn('⚠️ Session render: Keine Candlestick-Daten');
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

        // Rendere Session-Boxen (immer!)
        this.renderHighLowLines(chart, highLows);

        console.log('✅ Session Indikator gerendert');
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
        console.log('🧹 Alte Session-Boxen entfernt');

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

        if (skippedCount > 0) {
            console.log(`⏭️ ${skippedCount} Sessions übersprungen (Handelstage-Limit: ${this.config.tradingDaysLookback})`);
        }
        console.log(`✅ ${attachedCount}/${highLows.length} Session Rectangle-Boxen attached (${paintedTradingDays.size} Handelstage)`);
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

        // Neu berechnen und rendern
        const { sessions, highLows } = this.calculate(allData);
        if (window.chart) {
            this.renderHighLowLines(window.chart, highLows);
        }

        console.log('🔄 Session Indikator updated');
    }

    destroy() {
        // Entferne alle Primitives & Lines
        const candlestickSeries = window.candlestickSeries;
        this.highLowLines.forEach(item => {
            try {
                // Detach Rectangle Primitives von Candlestick Series
                if (item.primitive && candlestickSeries) {
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

        // 🔄 Re-render: Alte Series entfernen, dann neu zeichnen
        const chartData = window.candlestickSeries?.data();
        if (chartData && chartData.length > 0 && window.chart) {
            // 1. Alte Series entfernen
            if (indicator.series) {
                try {
                    window.chart.removeSeries(indicator.series);
                    indicator.series = null;
                } catch (e) {
                    console.warn('⚠️ Fehler beim Entfernen der alten Series:', e);
                }
            }

            // 2. Neu rendern mit neuer Config
            indicator.render(window.chart);
            indicator.update(null, chartData);
            console.log(`🔄 Indikator neu gerendert mit neuer Config`);
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

        // SESSION Indikator → Spezielles Modal
        if (indicator.type === 'SESSION') {
            this.openSessionSettings(indicator);
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
        console.log('⚙️ Session Settings Modal geöffnet');
    }

    // UI: Session Settings anwenden
    applySessionSettings() {
        const indicator = window.currentIndicatorForSettings;

        if (!indicator || indicator.type !== 'SESSION') {
            console.warn('⚠️ Kein Session Indikator für Settings ausgewählt');
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

        console.log('✅ Session Settings angewendet');
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

// Make globally available
window.IndicatorManager = manager;

console.log('✅ Indicator System bereit (EMA + SESSION + VOLUME)');
