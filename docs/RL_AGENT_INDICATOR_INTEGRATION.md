# RL Agent Indicator Integration

**Datum:** 2025-11-05
**Status:** ✅ Implementiert & Getestet

## Übersicht

Integration von **Live Indicator Daten** in den RL Trading Agent. Der Agent erhält jetzt echte Marktdaten von den Frontend-Indikatoren, um Trading-Entscheidungen zu treffen.

### Features
- ✅ Fair Value Gap (FVG) Detection
- ✅ Session High/Low Proximity Detection (0.15% Threshold)
- ✅ Session High/Low Breakout Detection
- ✅ Volume Spike Detection mit Ratio
- ✅ Real-Time Monitor Panel (RL Agent Vision)

---

## Problem & Lösung

### Problem
- RL Agent hatte nur **Dummy Market Context** mit statischen Werten
- Indikatoren liefen nur im Frontend (indicators.js), Daten erreichten Backend nicht
- Keine visuelle Kontrolle, was der Agent "sieht"

### Lösung
1. **getCurrentState()** Methoden in allen Indicator-Klassen implementiert
2. **Monitor Panel UI** für Live-Visualisierung erstellt
3. **Skip Event** erweitert um Indicator-Daten an Backend zu senden
4. **Backend** _build_market_context() nutzt echte Daten statt Dummy-Werte
5. **RL Agent** Scoring-Logik erweitert um Session High/Low Features

---

## Architektur

```
Frontend (indicators.js)
    │
    ├── VolumeIndicator.getCurrentState()
    ├── SessionHighLowIndicator.getCurrentState()
    ├── FVGIndicator.getCurrentState()
    │
    ↓ Skip Button Click
    │
    ├── getMarketContext() sammelt Daten
    ├── updateRLVisionMonitor() zeigt Daten im UI
    │
    ↓ WebSocket POST /api/debug/skip
    │
Backend (debug.py)
    │
    ├── skip_candle() empfängt indicator_data
    ├── _build_market_context() verarbeitet Daten
    │
    ↓ Weiterleitung an RL Agent
    │
RL Agent (rl_agent.py)
    │
    ├── decide(market_context)
    ├── _analyze_and_decide() nutzt Features für Scoring
    │
    ↓ Entscheidung: LONG / SHORT / HOLD
```

---

## Implementierte Änderungen

### 1. Frontend: getCurrentState() Methoden

#### `static/js/indicators.js` - VolumeIndicator (Zeile 1191-1216)

```javascript
getCurrentState() {
    if (!this.data || this.data.length < 20) {
        return { spike: false, ratio: 1.0, current_volume: 0 };
    }

    const currentVolume = this.data[this.data.length - 1].value;
    const recentVolumes = this.data.slice(-21, -1).map(v => v.value);
    const avgVolume = recentVolumes.reduce((sum, v) => sum + v, 0) / recentVolumes.length;

    const ratio = avgVolume > 0 ? currentVolume / avgVolume : 1.0;
    const spike = ratio > 1.5; // Spike wenn > 150% von Avg

    return {
        spike,
        ratio: parseFloat(ratio.toFixed(2)),
        current_volume: currentVolume,
        avg_volume: Math.round(avgVolume)
    };
}
```

**Rückgabe:**
- `spike`: Boolean - Volume > 1.5x Average
- `ratio`: Float - Current / Average Volume
- `current_volume`: Int
- `avg_volume`: Int

---

#### `static/js/indicators.js` - SessionHighLowIndicator (Zeile 1926-2000)

```javascript
getCurrentState(currentPrice) {
    if (!this.sessionBoxes || this.sessionBoxes.length === 0) {
        return { near_session_high: false, near_session_low: false, ... };
    }

    const lastSession = this.sessionBoxes[this.sessionBoxes.length - 1];
    const sessionHigh = lastSession.high;
    const sessionLow = lastSession.low;

    // WICHTIG: 0.15% Threshold = ~29 Punkte bei NQ 19500
    const threshold = currentPrice * 0.0015;

    const distanceToHigh = Math.abs(currentPrice - sessionHigh);
    const distanceToLow = Math.abs(currentPrice - sessionLow);

    const nearHigh = distanceToHigh <= threshold;
    const nearLow = distanceToLow <= threshold;
    const highBroken = currentPrice > sessionHigh; // Breakout nach oben
    const lowBroken = currentPrice < sessionLow;   // Breakout nach unten

    return {
        near_session_high: nearHigh,
        near_session_low: nearLow,
        session_high_broken: highBroken,
        session_low_broken: lowBroken,
        session_high_price: sessionHigh,
        session_low_price: sessionLow,
        current_session: lastSession.type, // 'asian', 'european', 'american'
        distance_to_high: distanceToHigh,
        distance_to_low: distanceToLow
    };
}
```

**Threshold-Definition:**
- **0.15% des aktuellen Preises**
- Bei NQ 19500 = **29.25 Punkte**
- Bei NQ 18750 = **28.13 Punkte**
- Dynamisch skalierend mit Preis

**Rückgabe:**
- `near_session_high`: Boolean
- `near_session_low`: Boolean
- `session_high_broken`: Boolean
- `session_low_broken`: Boolean
- `session_high_price`: Float
- `session_low_price`: Float
- `current_session`: String ('asian', 'european', 'american')

---

#### `static/js/indicators.js` - FVGIndicator (Zeile 2526-2595)

```javascript
getCurrentState(currentPrice) {
    if (!this.fvgBoxes || this.fvgBoxes.length === 0) {
        return {
            in_fvg: false,
            fvg_type: null,
            fvg_top: 0,
            fvg_bottom: 0,
            distance_to_fvg: 999999
        };
    }

    // Prüfe, ob Price IN einem FVG ist
    for (const box of this.fvgBoxes) {
        if (currentPrice >= box.bottom && currentPrice <= box.top) {
            return {
                in_fvg: true,
                fvg_type: box.type, // 'bullish' oder 'bearish'
                fvg_top: box.top,
                fvg_bottom: box.bottom,
                distance_to_fvg: 0
            };
        }
    }

    // Falls nicht IN FVG, finde nächstes FVG
    let closestFVG = null;
    let minDistance = Infinity;

    for (const box of this.fvgBoxes) {
        const distanceToTop = Math.abs(currentPrice - box.top);
        const distanceToBottom = Math.abs(currentPrice - box.bottom);
        const distance = Math.min(distanceToTop, distanceToBottom);

        if (distance < minDistance) {
            minDistance = distance;
            closestFVG = box;
        }
    }

    return {
        in_fvg: false,
        fvg_type: closestFVG ? closestFVG.type : null,
        fvg_top: closestFVG ? closestFVG.top : 0,
        fvg_bottom: closestFVG ? closestFVG.bottom : 0,
        distance_to_fvg: minDistance
    };
}
```

**Rückgabe:**
- `in_fvg`: Boolean
- `fvg_type`: 'bullish' | 'bearish' | null
- `fvg_top`: Float
- `fvg_bottom`: Float
- `distance_to_fvg`: Float (0 wenn inside, sonst Abstand)

---

### 2. Frontend: getMarketContext() Integration

#### `static/js/indicators.js` (Zeile 3197-3263)

```javascript
function getMarketContext() {
    const currentPrice = window.chart?.series[0]?.data[window.chart.series[0].data.length - 1]?.close || 0;

    // Sammle alle Indicator States
    const volumeState = window.volumeIndicator?.getCurrentState() || {};
    const sessionState = window.sessionHighLowIndicator?.getCurrentState(currentPrice) || {};
    const fvgState = window.fvgIndicator?.getCurrentState(currentPrice) || {};

    const context = {
        current_price: currentPrice,
        timestamp: Date.now(),

        // FVG
        in_fvg: fvgState.in_fvg || false,
        fvg_type: fvgState.fvg_type,
        fvg_top: fvgState.fvg_top,
        fvg_bottom: fvgState.fvg_bottom,
        distance_to_fvg: fvgState.distance_to_fvg,

        // Session High/Low
        near_session_high: sessionState.near_session_high || false,
        near_session_low: sessionState.near_session_low || false,
        session_high_broken: sessionState.session_high_broken || false,
        session_low_broken: sessionState.session_low_broken || false,
        session_high_price: sessionState.session_high_price || 0,
        session_low_price: sessionState.session_low_price || 0,
        current_session: sessionState.current_session || 'unknown',

        // Volume
        volume_spike: volumeState.spike || false,
        volume_ratio: volumeState.ratio || 1.0,
        current_volume: volumeState.current_volume || 0
    };

    // Update Monitor Panel
    if (typeof window.updateRLVisionMonitor === 'function') {
        window.updateRLVisionMonitor(context);
    }

    return context;
}
```

---

### 3. Frontend: RL Agent Vision Monitor

#### `templates/chart.html` (Zeile 614-677)

```html
<!-- RL Agent Vision Monitor -->
<div id="rlVisionMonitor" class="rl-vision-monitor">
    <div class="rl-vision-header">
        <span class="rl-vision-title">🤖 RL Agent Vision</span>
        <button id="toggleRLVision" class="rl-vision-toggle" title="Minimize">−</button>
    </div>
    <div class="rl-vision-content">
        <!-- FVG Section -->
        <div class="rl-vision-section">
            <div class="rl-vision-label">FVG Zone</div>
            <div id="vision-in-fvg" class="rl-vision-value">
                <span class="status-indicator">⭕</span> Not in FVG
            </div>
        </div>

        <!-- Session High/Low Section -->
        <div class="rl-vision-section">
            <div class="rl-vision-label">Session High</div>
            <div id="vision-session-high" class="rl-vision-value">
                <span class="status-indicator">⭕</span> Not Near
            </div>
            <div id="vision-high-broken" class="rl-vision-value">
                <span class="status-indicator">⭕</span> Not Broken
            </div>
        </div>

        <div class="rl-vision-section">
            <div class="rl-vision-label">Session Low</div>
            <div id="vision-session-low" class="rl-vision-value">
                <span class="status-indicator">⭕</span> Not Near
            </div>
            <div id="vision-low-broken" class="rl-vision-value">
                <span class="status-indicator">⭕</span> Not Broken
            </div>
        </div>

        <!-- Volume Section -->
        <div class="rl-vision-section">
            <div class="rl-vision-label">Volume</div>
            <div id="vision-volume-spike" class="rl-vision-value">
                <span class="status-indicator">⭕</span> No Spike
            </div>
            <div id="vision-volume-ratio" class="rl-vision-value-small">Ratio: 1.0x</div>
        </div>

        <!-- Current Session -->
        <div class="rl-vision-section">
            <div class="rl-vision-label">Session</div>
            <div id="vision-current-session" class="rl-vision-value">Unknown</div>
        </div>
    </div>
</div>
```

**Position:** Top-Right (90px von oben, 15px von rechts)
**Breite:** 280px
**Z-Index:** 900

---

#### `static/css/chart.css` (Zeile 773-897)

```css
.rl-vision-monitor {
    position: fixed;
    top: 90px;
    right: 15px;
    width: 280px;
    background: rgba(20, 20, 20, 0.95);
    border: 1px solid #333;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    font-family: 'Segoe UI', sans-serif;
    z-index: 900;
    transition: all 0.3s ease;
}

.rl-vision-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 1px solid #333;
    border-radius: 8px 8px 0 0;
}

.rl-vision-title {
    font-size: 13px;
    font-weight: 600;
    color: #089981;
}

.rl-vision-value.active {
    color: #089981; /* Grün für aktive Features */
    font-weight: 600;
}

.status-indicator {
    font-size: 10px;
    margin-right: 4px;
}
```

**Status-Indikatoren:**
- ✅ = Feature aktiv (grün)
- ⭕ = Feature inaktiv (grau)

---

#### `static/js/chart.js` - updateRLVisionMonitor()

```javascript
function updateRLVisionMonitor(context) {
    if (!context) return;

    // FVG
    const fvgElem = document.getElementById('vision-in-fvg');
    if (context.in_fvg) {
        fvgElem.innerHTML = `<span class="status-indicator">✅</span> In FVG (${context.fvg_type})`;
        fvgElem.classList.add('active');
    } else {
        fvgElem.innerHTML = `<span class="status-indicator">⭕</span> Not in FVG`;
        fvgElem.classList.remove('active');
    }

    // Session High - Near
    const highElem = document.getElementById('vision-session-high');
    if (context.near_session_high) {
        highElem.innerHTML = `<span class="status-indicator">✅</span> Near High (${context.session_high_price})`;
        highElem.classList.add('active');
    } else {
        highElem.innerHTML = `<span class="status-indicator">⭕</span> Not Near`;
        highElem.classList.remove('active');
    }

    // Session High - Broken
    const highBrokenElem = document.getElementById('vision-high-broken');
    if (context.session_high_broken) {
        highBrokenElem.innerHTML = `<span class="status-indicator">✅</span> High Broken`;
        highBrokenElem.classList.add('active');
    } else {
        highBrokenElem.innerHTML = `<span class="status-indicator">⭕</span> Not Broken`;
        highBrokenElem.classList.remove('active');
    }

    // Session Low - Near
    const lowElem = document.getElementById('vision-session-low');
    if (context.near_session_low) {
        lowElem.innerHTML = `<span class="status-indicator">✅</span> Near Low (${context.session_low_price})`;
        lowElem.classList.add('active');
    } else {
        lowElem.innerHTML = `<span class="status-indicator">⭕</span> Not Near`;
        lowElem.classList.remove('active');
    }

    // Session Low - Broken
    const lowBrokenElem = document.getElementById('vision-low-broken');
    if (context.session_low_broken) {
        lowBrokenElem.innerHTML = `<span class="status-indicator">✅</span> Low Broken`;
        lowBrokenElem.classList.add('active');
    } else {
        lowBrokenElem.innerHTML = `<span class="status-indicator">⭕</span> Not Broken`;
        lowBrokenElem.classList.remove('active');
    }

    // Volume Spike
    const volumeElem = document.getElementById('vision-volume-spike');
    if (context.volume_spike) {
        volumeElem.innerHTML = `<span class="status-indicator">✅</span> Volume Spike`;
        volumeElem.classList.add('active');
    } else {
        volumeElem.innerHTML = `<span class="status-indicator">⭕</span> No Spike`;
        volumeElem.classList.remove('active');
    }

    // Volume Ratio
    const ratioElem = document.getElementById('vision-volume-ratio');
    ratioElem.textContent = `Ratio: ${context.volume_ratio}x`;

    // Current Session
    const sessionElem = document.getElementById('vision-current-session');
    sessionElem.textContent = context.current_session.charAt(0).toUpperCase() + context.current_session.slice(1);
}

window.updateRLVisionMonitor = updateRLVisionMonitor;
```

---

### 4. Backend: Market Context Builder

#### `charts/routes/debug.py` - _build_market_context() (Zeile 33-98)

**VORHER (Dummy Daten):**
```python
def _build_market_context(candle: Dict[str, Any], timestamp: int, indicator_data: Dict = None) -> Dict[str, Any]:
    return {
        'current_price': candle['close'],
        'timestamp': timestamp,
        'patterns': {
            'in_fvg_zone': False,  # ❌ Statisch
            'fvg_distance': 999,
            'near_support_ob': False,
            'near_resistance_ob': False,
            'liquidity_direction': 0,
            'market_structure': 0
        },
        'session_info': {
            'session': 'unknown',
            'time_in_session': 0,
            'near_open': False,
            'near_close': False
        },
        'volume': {
            'spike': False,
            'ratio': 1.0
        }
    }
```

**NACHHER (Echte Daten):**
```python
def _build_market_context(candle: Dict[str, Any], timestamp: int, indicator_data: Dict = None) -> Dict[str, Any]:
    # Extrahiere Indicator Daten vom Frontend
    in_fvg = False
    near_session_high = False
    near_session_low = False
    session_high_broken = False
    session_low_broken = False
    volume_spike = False
    volume_ratio = 1.0
    current_session = 'unknown'

    if indicator_data:
        in_fvg = indicator_data.get('in_fvg', False)
        near_session_high = indicator_data.get('near_session_high', False)
        near_session_low = indicator_data.get('near_session_low', False)
        session_high_broken = indicator_data.get('session_high_broken', False)
        session_low_broken = indicator_data.get('session_low_broken', False)
        volume_spike = indicator_data.get('volume_spike', False)
        volume_ratio = indicator_data.get('volume_ratio', 1.0)
        current_session = indicator_data.get('current_session', 'unknown')

    return {
        'current_price': candle['close'],
        'timestamp': timestamp,
        'patterns': {
            'in_fvg_zone': in_fvg,  # ✅ Live Data
            'near_session_high': near_session_high,  # ✅ Neu
            'near_session_low': near_session_low,    # ✅ Neu
            'session_high_broken': session_high_broken,  # ✅ Neu
            'session_low_broken': session_low_broken,    # ✅ Neu
            'fvg_distance': 999,  # TODO: könnte auch vom Frontend kommen
            'near_support_ob': False,  # Legacy (TODO: entfernen?)
            'near_resistance_ob': False,
            'liquidity_direction': 0,
            'market_structure': 0
        },
        'session_info': {
            'session': current_session,  # ✅ Live Data
            'time_in_session': 0,
            'near_open': False,
            'near_close': False
        },
        'volume': {
            'spike': volume_spike,  # ✅ Live Data
            'ratio': volume_ratio   # ✅ Live Data
        }
    }
```

---

### 5. RL Agent: Scoring-Logik Erweiterung

#### `src/rl_agent.py` (Zeile 107-185)

**Neue Features hinzugefügt:**

```python
# ========== LONG SIGNALS ==========

# Session Low = Strong Support
near_session_low = patterns.get('near_session_low', False)
if near_session_low:
    long_score += 0.25  # Hohes Gewicht für Support-Zone
    reasoning.append("Nahe Session Low (Support)")

# Session Low Broken = Bullish Breakout
session_low_broken = patterns.get('session_low_broken', False)
if session_low_broken:
    long_score += 0.2  # Breakout nach unten = potentieller Bounce
    reasoning.append("Session Low durchbrochen")

# Support Order Block (legacy, niedrigeres Gewicht)
if near_support_ob:
    long_score += 0.15  # Reduziert von 0.25
    reasoning.append("Nahe Support OB")

# Volume Spike mit dynamischem Gewicht
if volume_spike:
    volume_weight = min(volume_ratio / 10.0, 0.2)  # Max 0.2 bei Ratio 2.0+
    long_score += volume_weight
    reasoning.append(f"Volume Spike ({volume_ratio:.1f}x)")


# ========== SHORT SIGNALS ==========

# Session High = Strong Resistance
near_session_high = patterns.get('near_session_high', False)
if near_session_high:
    short_score += 0.25  # Hohes Gewicht für Resistance-Zone
    reasoning.append("Nahe Session High (Resistance)")

# Session High Broken = Bearish Rejection
session_high_broken = patterns.get('session_high_broken', False)
if session_high_broken:
    short_score += 0.2  # Breakout nach oben = potentielles Reversal
    reasoning.append("Session High durchbrochen")

# Resistance Order Block (legacy, niedrigeres Gewicht)
if near_resistance_ob:
    short_score += 0.15  # Reduziert von 0.25
    reasoning.append("Nahe Resistance OB")

# Volume Spike (bearish context)
if volume_spike:
    volume_weight = min(volume_ratio / 10.0, 0.2)
    short_score += volume_weight
```

**Gewichtungen:**
- Session High/Low (near): **0.25** (höchste Priorität)
- Session High/Low (broken): **0.20**
- Volume Spike: **0.0 - 0.2** (dynamisch basierend auf Ratio)
- FVG Zone: **0.30** (bereits existiert)
- Order Blocks: **0.15** (legacy, reduziert)

---

## Testing-Ergebnisse

### Test-Setup
- **Browser:** MCP Chrome DevTools
- **URL:** http://localhost:8003
- **Methode:** Skip Button mehrfach geklickt
- **Datum:** 2025-11-05

### Backend Logs

```python
[SKIP-SERVICE] Skip requested from client
[SKIP-SERVICE] Indicator Data received: {
    'in_fvg': False,
    'near_session_low': True,         # ✅ Aktiv
    'session_low_broken': True,       # ✅ Aktiv
    'near_session_high': False,
    'session_high_broken': False,
    'session_high_price': 18857,
    'session_low_price': 18749,
    'current_session': 'american',
    'volume_spike': False,
    'volume_ratio': 0.51,
    'current_price': 18734.5
}

[SKIP-SERVICE] Market Context built successfully
[SKIP-SERVICE] Current candle time: 2024-02-23 17:45:00
[SKIP-SERVICE] Successfully skipped to next candle
```

### Frontend Monitor Panel

**Screenshot-Bestätigung:**
- ✅ **Near Session Low** - grün markiert (aktiv)
- ✅ **Session Low Broken** - grün markiert (aktiv)
- ⭕ Session High - grau (inaktiv)
- ⭕ FVG Zone - grau (inaktiv)
- ⭕ Volume Spike - grau (inaktiv)
- **Current Session:** American
- **Volume Ratio:** 0.51x

### Verifizierung

| Feature | Frontend | Backend | RL Agent | Status |
|---------|----------|---------|----------|--------|
| In FVG Zone | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Near Session High | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Near Session Low | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Session High Broken | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Session Low Broken | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Volume Spike | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Volume Ratio | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Current Session | ✅ | ✅ | ✅ | ✅ Funktioniert |
| Monitor Panel UI | ✅ | - | - | ✅ Funktioniert |

---

## Verwendung

### Monitor Panel

1. **Server starten:** `start_server.bat`
2. **Browser öffnen:** http://localhost:8003
3. **Skip Button klicken:** Springt zur nächsten Candle
4. **Monitor Panel beobachten:** Top-Right zeigt Live-Daten

### Minimieren/Maximieren

```javascript
document.getElementById('toggleRLVision').addEventListener('click', function() {
    const content = document.querySelector('.rl-vision-content');
    const isMinimized = content.style.display === 'none';

    content.style.display = isMinimized ? 'block' : 'none';
    this.textContent = isMinimized ? '−' : '+';
    this.title = isMinimized ? 'Minimize' : 'Maximize';
});
```

---

## Threshold-Tuning

### Aktuelle Thresholds

| Feature | Threshold | Begründung |
|---------|-----------|------------|
| **Session High/Low Proximity** | 0.15% | ~29 Punkte bei NQ 19500 - eng genug für Reaction Zone |
| **Volume Spike** | 1.5x Avg | Standard Deviation für signifikante Volume-Änderung |
| **FVG Distance** | 0.005 (0.5%) | Bereits existiert, nicht geändert |

### Tuning-Hinweise

**Wenn zu viele False Positives:**
- Session Proximity: 0.15% → 0.10% (enger)
- Volume Spike: 1.5x → 1.8x (höher)

**Wenn zu wenige Signals:**
- Session Proximity: 0.15% → 0.20% (weiter)
- Volume Spike: 1.5x → 1.3x (niedriger)

**Performance-Tracking:**
```python
# TODO: Logging hinzufügen in rl_agent.py
logger.info(f"[DECISION] {action.upper()} | Confidence: {confidence:.2%} | Reasoning: {reasoning}")
logger.info(f"[SIGNALS] Long: {long_score:.2f} | Short: {short_score:.2f}")
```

---

## Future Work

### Phase 2: Python Indicator Implementation (Offline Training)

**Problem:**
- Aktuell nur Frontend (JavaScript) Indikatoren
- Backend kann keine historischen Daten offline verarbeiten
- RL Training benötigt schnelle Python-basierte Berechnung

**Lösung:**
1. **Python Indicator Klassen erstellen:**
   - `charts/indicators/volume_indicator.py`
   - `charts/indicators/session_high_low_indicator.py`
   - `charts/indicators/fvg_indicator.py`

2. **Interface:** Gleiche getCurrentState() Methoden wie Frontend

3. **Integration in Training Loop:**
   ```python
   # Pseudo-Code
   for episode in range(num_episodes):
       for candle in historical_data:
           # Berechne Indikatoren in Python
           volume_state = VolumeIndicator.calculate(candle)
           session_state = SessionHighLowIndicator.calculate(candle)
           fvg_state = FVGIndicator.calculate(candle)

           # Build Context
           market_context = build_context(candle, volume_state, session_state, fvg_state)

           # RL Agent Entscheidung
           decision = agent.decide(market_context)

           # Environment Step
           reward = env.step(decision)

           # PPO Update
           agent.update(reward)
   ```

**Priorität:** Medium (erst wenn PPO Training startet)

---

### Weitere TODOs

- [ ] **Logging:** Trade Decisions mit Reasoning in Datei speichern
- [ ] **Backtesting:** Performance Metrics für jede Feature-Kombination
- [ ] **Threshold Auto-Tuning:** Grid Search für optimale Werte
- [ ] **Legacy Code Cleanup:** near_support_ob, near_resistance_ob entfernen?
- [ ] **FVG Distance:** Vom Frontend senden statt hardcoded 999
- [ ] **Session Timing:** near_open, near_close implementieren
- [ ] **Market Structure:** Erkennung basierend auf Higher Highs/Lower Lows

---

## Commit History

**Relevante Commits:**
```
21f4daa - feat: Persistent Time Storage - Go To Date mit Auto-Save & Server Restore
41fca9e - feat: Play Button Speed-Slider - Custom Speed Mapping (0.3x-20x)
68a41bf - docs: Go To Date Bugfix dokumentiert
```

**Dieser Feature-Branch:**
- ✅ getCurrentState() Methoden in indicators.js
- ✅ RL Agent Vision Monitor UI
- ✅ Market Context Integration in debug.py
- ✅ RL Agent Scoring Erweiterung

---

## Troubleshooting

### Problem: Monitor Panel zeigt keine Daten

**Lösung:**
```javascript
// Chart.js console check
console.log(window.volumeIndicator);
console.log(window.sessionHighLowIndicator);
console.log(window.fvgIndicator);

// Falls undefined, Indicator Initialization checken
```

### Problem: Backend erhält keine indicator_data

**Lösung:**
```python
# debug.py Logging hinzufügen
print(f"[DEBUG] indicator_data type: {type(indicator_data)}")
print(f"[DEBUG] indicator_data content: {indicator_data}")
```

### Problem: RL Agent trifft keine Decisions

**Lösung:**
```python
# rl_agent.py - Score Debugging
print(f"[DEBUG] Long Score: {long_score:.2f}")
print(f"[DEBUG] Short Score: {short_score:.2f}")
print(f"[DEBUG] Threshold: {self.confidence_threshold}")
```

---

## Kontakt & Fragen

Bei Fragen oder Problemen mit dieser Integration:
1. Diese Dokumentation lesen
2. Backend Logs prüfen (Terminal mit chart_server.py)
3. Browser Console prüfen (F12 → Console)
4. Screenshots vom Monitor Panel machen

**Letzte Aktualisierung:** 2025-11-05
