# Indicator Blueprint System - Dokumentation

**Datum:** 2025-11-01
**Branch:** main
**Base:** Phantom Candles Removal

## Zusammenfassung

Blueprint-System für Indikatoren implementiert. Gemeinsame Basis-Properties für alle Indikatoren (lineWidth, lineStyle, etc.) + Settings Modal Integration + automatisches Re-Rendering bei Config-Änderungen.

## Problem

**Vorher:**
- Jeder Indikator definierte eigene Properties (Code-Duplikation)
- Keine einheitliche Linienstärke-Konfiguration
- Settings Modal konnte nur Period/Color ändern
- Indikatoren wurden bei "Go To Date" neu gerendert statt aktualisiert
- Config-Änderungen wurden gespeichert, aber Chart nicht aktualisiert

## Lösung

### 1. Blueprint Defaults in BaseIndicator

**Datei:** `static/js/indicators.js` (Zeile 16-30)

```javascript
constructor(id, type, config = {}) {
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
}
```

**Vorteil:** Jeder Indikator erbt automatisch alle Blueprint-Properties.

### 2. EMAIndicator verwendet Blueprint

**Datei:** `static/js/indicators.js` (Zeile 169)

```javascript
this.series = chart.addLineSeries({
    color: this.config.color,
    lineWidth: this.config.lineWidth,           // From Blueprint
    lineStyle: this.config.lineStyle,           // From Blueprint
    priceLineVisible: this.config.priceLineVisible,
    lastValueVisible: this.config.lastValueVisible,
    crosshairMarkerVisible: this.config.crosshairMarkerVisible,
    title: this.getDisplayName()
});
```

**Vorher:** `lineWidth: 2` (hardcoded)
**Jetzt:** `lineWidth: this.config.lineWidth` (dynamisch)

### 3. Settings Modal - Line Width Slider

**Datei:** `templates/chart.html` (Zeile 210-218)

```html
<!-- Blueprint Property: Line Width Slider -->
<div class="balance-section" style="margin-top: 15px;">
    <label class="balance-label">Linienstärke: <span id="lineWidthValue">2</span></label>
    <input type="range" id="indicatorLineWidthInput" class="balance-input"
           value="2" min="1" max="10" step="1"
           oninput="document.getElementById('lineWidthValue').textContent = this.value"
           style="width: 100%;">
</div>
```

**Features:**
- Range Slider 1-10
- Live Value Display (`lineWidthValue` Span)
- Standard: 2

### 4. Settings Modal - lineWidth Input lesen

**Datei:** `static/js/indicators.js` (Zeile 584-592)

```javascript
const periodInput = document.getElementById('indicatorPeriodInput');
const colorInput = document.getElementById('indicatorColorInput');
const lineWidthInput = document.getElementById('indicatorLineWidthInput');  // Blueprint Property

const newConfig = {
    period: parseInt(periodInput.value) || indicator.config.period,
    color: colorInput.value || indicator.config.color,
    lineWidth: parseInt(lineWidthInput.value) || indicator.config.lineWidth  // Blueprint Property
};
```

**Bug Fix:** Input wurde nicht gelesen → Config blieb unverändert.

### 5. Settings Modal - Slider initialisieren

**Datei:** `static/js/indicators.js` (Zeile 571)

```javascript
openSettingsModal(id) {
    // ... existing code ...

    document.getElementById('indicatorLineWidthInput').value = indicator.config.lineWidth || 2;
    document.getElementById('lineWidthValue').textContent = indicator.config.lineWidth || 2;
}
```

**Wichtig:** Slider zeigt aktuellen lineWidth-Wert beim Öffnen.

### 6. Config Update mit Re-Rendering

**Datei:** `static/js/indicators.js` (Zeile 376-395)

```javascript
updateIndicatorConfig(id, newConfig) {
    const indicator = this.activeIndicators.get(id);

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
    this.renderLabels();
}
```

**Kritisch:** Config-Update ohne Re-Render → Chart zeigt alte Line Width bis Page Reload.

### 7. Go To Date Bug Fix - Indicator Sync

**Datei:** `static/js/chart.js` (Zeile ~1574)

```javascript
candlestickSeries.setData(extendedHistoricalData);

// 📊 BUGFIX: Update Indikatoren nach Go To Date
if (window.IndicatorManager) {
    window.IndicatorManager.syncWithChart(extendedHistoricalData);
    console.log('📊 Indikatoren nach Go To Date aktualisiert');
}
```

**Datei:** `static/js/indicators.js` (neue Methode)

```javascript
syncWithChart(chartData) {
    console.log(`📊 Syncing ${this.activeIndicators.size} indicators with chart data (${chartData.length} candles)`);
    for (const indicator of this.activeIndicators.values()) {
        if (indicator.visible && indicator.series) {
            indicator.update(null, chartData);
        }
    }
}
```

**Vorher:** Go To Date → Indikatoren verschwanden
**Jetzt:** Go To Date → Indikatoren werden synced

## Auswirkungen

### Positiv
✅ **Blueprint Pattern** - Einheitliche Properties für alle Indikatoren
✅ **Line Width Konfigurierbar** - User kann Linienstärke 1-10 wählen
✅ **Settings Modal erweitert** - Slider für Line Width
✅ **Live Re-Rendering** - Config-Änderungen sofort sichtbar
✅ **Go To Date Fix** - Indikatoren bleiben erhalten + werden aktualisiert
✅ **Persistence** - Line Width wird in localStorage gespeichert

### Negativ
❌ **Breaking Change** - Alte Indikatoren ohne Blueprint müssen angepasst werden
❌ **Re-Render Cost** - Series wird removed + neu erstellt (könnte optimiert werden)

## Testing

- [x] Line Width Slider funktioniert (1-10)
- [x] Config-Update schreibt lineWidth korrekt
- [x] Chart re-rendert Indicator sofort nach Apply
- [x] Line Width visuell sichtbar im Chart
- [x] Go To Date aktualisiert Indikatoren korrekt
- [x] localStorage speichert lineWidth
- [x] Page Reload lädt lineWidth korrekt

## Commit Details

**Files Changed:**
- `static/js/indicators.js` - Blueprint System, Re-Render Logic, syncWithChart()
- `static/js/chart.js` - Go To Date Indicator Sync
- `templates/chart.html` - Line Width Slider im Settings Modal
- `docs/INDICATOR_BLUEPRINT_SYSTEM.md` - Diese Dokumentation

**Lines Changed:** ~60 Lines
- `indicators.js`: 40 Lines (Blueprint, Re-Render, Sync)
- `chart.js`: 5 Lines (Go To Date Fix)
- `chart.html`: 10 Lines (Slider UI)

---

**Erstellt von:** Claude Code
**Session:** 2025-11-01
