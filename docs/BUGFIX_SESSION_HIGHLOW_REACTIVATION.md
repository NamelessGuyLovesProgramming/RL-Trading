# 🐛 Bugfix: Session High/Low Mehrfach-Aktivierung

## Problem

Session High/Low Detection Signale (`broken_low`, `broken_high`) aktivieren sich mehrfach beim gleichen Level.

**Beispiel:**
- 11.09.2024 00:30: Kerze durchbricht US Session Low bei 19500 → broken_low = TRUE
- Kerzen bewegen sich weg → broken_low = FALSE
- 11.09.2024 03:40: Kerze durchbricht WIEDER 19500 → broken_low = TRUE ❌ (BUG!)

**Impact:**
Der RL Agent bekommt das gleiche Signal mehrfach für das identische Level, was das Training verwirrt. Das "erste Durchbrechen" sollte anders bewertet werden als "erneutes Durchbrechen".

---

## Root Cause

**Keine Persistierung welcher Levels bereits aktiviert wurden.**

Die Detection-Logik in `static/js/indicators.js` prüft nur den **aktuellen Zustand**:
- Level durchbrochen + `distance <= 50 Punkte` → `broken_low = TRUE`
- Nicht durchbrochen ODER `distance > 50 Punkte` → `broken_low = FALSE`

Es gibt kein "Gedächtnis" über vergangene Aktivierungen. Bei jeder Rückkehr zum Level wird die Bedingung erneut geprüft und aktiviert.

**Code Location:** `SessionHighLowIndicator.getCurrentState()` Lines 2474-2546

---

## Lösung

### Konzept: "Einmal aus = für immer blockiert"

**3 Zustände für jeden Level:**
1. **Noch nie aktiv** → darf aktivieren ✅
2. **Gerade aktiv** → bleibt aktiv ✅
3. **War aktiv, jetzt aus** → nie wieder ❌

### Implementierung: 4 Tracking-Listen

```javascript
// current = gerade aktiv | had = war aktiv, dann deaktiviert (permanent blockiert)
this.currentBrokenHighs = new Set();  // Levels wo broken_high gerade aktiv
this.currentBrokenLows = new Set();   // Levels wo broken_low gerade aktiv
this.hadBrokenHighs = new Set();      // Levels die broken_high hatten (blockiert)
this.hadBrokenLows = new Set();       // Levels die broken_low hatten (blockiert)
```

**Lifecycle:**
1. **Erste Aktivierung:** Level durchbrochen UND nicht in `had` → Aktiviere + In `current` eintragen
2. **Aktiv bleiben:** Level durchbrochen UND in `current` → Bleibt aktiv
3. **Deaktivierung:** Level nicht mehr durchbrochen UND in `current` → Move zu `had` (permanent!)
4. **Blockierung:** Level durchbrochen ABER in `had` → Blockieren
5. **Session Ende:** Line verschwindet → Aus allen Listen entfernen

### Warum Sets statt Arrays?

- `O(1)` Lookup-Performance mit `.has()`
- Automatische Deduplizierung
- Einfache Add/Remove Operationen

### Warum 2 Paare (current/had)?

**current vs had:**
- **current:** Level ist im Moment aktiv (kann sich ändern)
- **had:** Level war mal aktiv, ist jetzt aus (permanent blockiert)

**Highs vs Lows:**
- Verschiedene Price-Levels (19500 vs 20100)
- Unabhängige Session-Zyklen

---

## Geänderte Dateien

### `static/js/indicators.js`

#### 1. Class Properties (Line 1267-1272)

**Hinzugefügt:**
```javascript
// Broken State Tracking (Bugfix: Mehrfach-Aktivierung)
// current = gerade aktiv | had = war aktiv, dann deaktiviert (permanent blockiert)
this.currentBrokenHighs = new Set();
this.currentBrokenLows = new Set();
this.hadBrokenHighs = new Set();
this.hadBrokenLows = new Set();
```

---

#### 2. getCurrentState() - Distance Calculation (Line 2456-2472)

**Vereinfacht - nur noch Distanz-Berechnung, kein Near:**
```javascript
// DISTANCE CALCULATION (für Broken Detection)
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
```

---

#### 3. getCurrentState() - Broken High Check (Line 2474-2513)

**Neue State-Tracking Logik:**
```javascript
// BROKEN HIGH CHECK
if (nextHigh && distanceToHigh <= brokenThreshold) {
    const isBroken = brokenHighs.some(h => Math.abs(h.price - nextHigh.price) < 0.1);
    const priceKey = nextHigh.price.toFixed(2);

    if (isBroken) {
        // Level ist durchbrochen
        if (this.hadBrokenHighs.has(priceKey)) {
            // War schon mal aktiv + deaktiviert → PERMANENT BLOCKIERT
            console.log(`🚫 [Broken High] PERMANENT BLOCKIERT für ${priceKey}`);
        } else {
            // Darf aktivieren
            highBroken = true;
            this.currentBrokenHighs.add(priceKey);
            console.log(`🔔 [Broken High] AKTIVIERT für ${priceKey} (First Break)`);
        }
    } else {
        // Level ist NICHT durchbrochen → Check ob Deaktivierung
        if (this.currentBrokenHighs.has(priceKey)) {
            // War gerade aktiv, jetzt nicht mehr → DEAKTIVIERUNG!
            this.currentBrokenHighs.delete(priceKey);
            this.hadBrokenHighs.add(priceKey);
            console.log(`⚠️ [Broken High] DEAKTIVIERT für ${priceKey} → PERMANENT BLOCKIERT!`);
        }
    }
}
```

**Key Points:**
- Prüft `hadBrokenHighs` → permanent blockiert
- Prüft `currentBrokenHighs` → aktiv bleiben oder deaktivieren
- Deaktivierung: Move von `current` → `had`

---

#### 4. getCurrentState() - Broken Low Check (Line 2516-2546)

Analog zu Broken High Check (siehe oben), verwendet `currentBrokenLows` und `hadBrokenLows`.

---

#### 5. getCurrentState() - Return Statement (Line 2548-2560)

**Near Detection entfernt:**
```javascript
return {
    near_session_high: false,  // Entfernt - nur noch Broken
    near_session_low: false,   // Entfernt - nur noch Broken
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
```

---

#### 6. getAllLevelsWithGracePeriod() - Cleanup (Line 1744-1773)

**Cleanup für neue Listen:**
```javascript
// CLEANUP: Entferne Levels aus Broken-Listen die nicht mehr sichtbar sind
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

const totalTracked = this.currentBrokenHighs.size + this.currentBrokenLows.size +
                    this.hadBrokenHighs.size + this.hadBrokenLows.size;
if (totalTracked > 0) {
    console.log(`🧹 [Session HL Cleanup] Current: H=${this.currentBrokenHighs.size} L=${this.currentBrokenLows.size} | Had: H=${this.hadBrokenHighs.size} L=${this.hadBrokenLows.size}`);
}
```

**Warum hier?**
`getAllLevelsWithGracePeriod()` berechnet welche Lines noch sichtbar sind. Wenn ein Level die Grace Period überschreitet → Line verschwindet → idealer Zeitpunkt für Cleanup.

---

### `static/js/chart.js`

#### 1. Chart Reinitialize Cleanup (Line 1902-1905)

**Cleanup bei Chart-Reset:**
```javascript
sessionHLIndicator.indicator.currentBrokenHighs.clear();
sessionHLIndicator.indicator.currentBrokenLows.clear();
sessionHLIndicator.indicator.hadBrokenHighs.clear();
sessionHLIndicator.indicator.hadBrokenLows.clear();
```

#### 2. Go To Date Cleanup (Line 1996-1999)

**Cleanup bei Datums-Sprung:**
```javascript
sessionHLIndicator.indicator.currentBrokenHighs.clear();
sessionHLIndicator.indicator.currentBrokenLows.clear();
sessionHLIndicator.indicator.hadBrokenHighs.clear();
sessionHLIndicator.indicator.hadBrokenLows.clear();
```

**Warum beides leeren?**
Bei Chart-Reset oder Go To Date sind die alten Levels nicht mehr relevant → Fresh start!

---

## Test Case

### Szenario: 11.09.2024 - Doppeltes Durchbrechen US Session Low

**Asset:** NQ=F (NASDAQ-100 Futures)
**Session Low:** 19500 (US Session)

**Timeline:**

| Zeit  | Preis | Zustand | Erwartetes Verhalten |
|-------|-------|---------|----------------------|
| 00:15 | 19600 | - | Session Low wird gebildet |
| 00:30 | 19480 | Broken | **broken_low = TRUE** (First Break) ✅ |
| 01:00 | 19600 | Nicht broken | broken_low = FALSE → Move zu `had` ⚠️ |
| 03:40 | 19490 | Broken | **broken_low = FALSE** (blockiert!) ✅ |
| 07:00 | - | - | Session endet → Cleanup |

### Test-Durchführung

1. **Server starten:**
   ```bash
   py charts/chart_server.py
   ```

2. **Chart öffnen:**
   ```
   http://localhost:8003
   ```

3. **Navigation:**
   - Date Picker: 11.09.2024
   - Time: 00:15
   - Asset: NQ=F

4. **Test Steps:**
   - **Step 1:** Skip bis 00:30
     - **Browser Console:** `🔔 [Broken Low] AKTIVIERT für 19500.00 (First Break)`
     - **Vision Monitor:** broken_low = TRUE (grün)
     - **Intern:** `currentBrokenLows` = Set(["19500.00"])

   - **Step 2:** Skip bis 01:00
     - **Browser Console:** `⚠️ [Broken Low] DEAKTIVIERT für 19500.00 → PERMANENT BLOCKIERT!`
     - **Vision Monitor:** broken_low = FALSE (rot/aus)
     - **Intern:** `currentBrokenLows` = Set([]), `hadBrokenLows` = Set(["19500.00"])

   - **Step 3:** Skip bis 03:40
     - **Browser Console:** `🚫 [Broken Low] PERMANENT BLOCKIERT für 19500.00`
     - **Vision Monitor:** broken_low = FALSE ✅ (KEY TEST!)
     - **Intern:** Lists unchanged

   - **Step 4:** Skip bis 07:00 (US Session Ende)
     - **Browser Console:** `🧹 [Session HL Cleanup] Current: H=0 L=0 | Had: H=0 L=0`
     - **Intern:** Alle Listen leer (Line ist weg)

### Validierung

**Browser Console öffnen:** `F12` → `Console` Tab

**Erwartete Logs:**
```
🔔 [Broken Low] AKTIVIERT für 19500.00 (First Break)
... (Zeit vergeht)
⚠️ [Broken Low] DEAKTIVIERT für 19500.00 → PERMANENT BLOCKIERT!
... (Preis kommt zurück)
🚫 [Broken Low] PERMANENT BLOCKIERT für 19500.00
... (Session endet)
🧹 [Session HL Cleanup] Current: H=0 L=0 | Had: H=0 L=0
```

**WICHTIG:** Die "PERMANENT BLOCKIERT" Message bei 03:40 ist der **Beweis** dass der Fix funktioniert!

---

## Weitere Tests

### Test 2: Mehrere Sessions

**Ziel:** Verify dass verschiedene Session Levels separat getrackt werden.

1. Navigate zu Tag mit mehreren Sessions (z.B. 12.09.2024)
2. Identify 3 verschiedene Lows:
   - Asia Session Low: z.B. 19800
   - Euro Session Low: z.B. 19650
   - US Session Low: z.B. 19500
3. Trigger broken_low für alle 3
4. Verify: Alle 3 in Console als "AKTIVIERT" geloggt
5. Verify: Bei Deaktivierung und Rückkehr → "BLOCKIERT"

### Test 3: Cleanup Funktionalität

**Ziel:** Verify dass Listen bei Session-Ende bereinigt werden.

1. Trigger mehrere Levels (broken_low, broken_high)
2. Browser Console: Check Set sizes via Developer Tools
3. Skip bis Session-Ende (Grace Period abgelaufen)
4. Console: "🧹 [Session HL Cleanup]" mit Size = 0
5. Verify: Listen sind leer

---

## Prevention

### Design Patterns

**1. State Machine mit 3 Zuständen**
- Never active → can activate
- Active → stays active OR deactivates
- Was active → permanent block

**2. Separation of Concerns**
- Detection Logic (`getCurrentState()`)
- State Management (current/had Sets)
- Lifecycle Management (`getAllLevelsWithGracePeriod()`)

**3. Defensive Logging**
- Explizite "AKTIVIERT", "DEAKTIVIERT", "BLOCKIERT" Messages
- Macht Debugging und Testing einfach
- User kann in Console nachvollziehen was passiert

### Key Insights

**1. Deaktivierung ist der Schlüssel**
Nicht nur Aktivierung tracken, sondern auch erkennen WANN broken ausgeht → Das ist der Trigger für `current → had` Move!

**2. Grace Period ist perfekt für Cleanup**
Die existierende Grace Period Logic bestimmt wann Lines entfernt werden → Perfekter Trigger für Listen-Cleanup!

**3. Sets sind ideal**
- Schnelle Lookups (`O(1)`)
- Automatische Deduplizierung
- Einfache Filter-Operationen

**4. Price-Keys mit .toFixed(2)**
Floating Point Vergleiche sind problematisch → String-Keys mit 2 Dezimalstellen lösen das Problem.

### Mögliche Edge Cases

**1. Mehrere Levels sehr nah beieinander**
```javascript
Session Lows: 19500.00, 19500.50, 19501.00
```
→ Durch .toFixed(2) werden diese separat getrackt ✅

**2. Level wird neu gebildet nach Session-Ende**
```javascript
US Session 1: Low bei 19500 → aktiviert → deaktiviert → Session endet → bereinigt
US Session 2: Low bei 19500 → NEU gebildet → kann wieder aktiviert werden ✅
```
→ Cleanup entfernt alte Einträge, neues Level startet fresh ✅

**3. Schnelle Oszillationen**
```javascript
19490 (broken) → 19600 (aus) → 19490 (broken wieder)
```
→ Erste Aktivierung OK, bei zweiter "BLOCKIERT" ✅

---

## Commit Message

```
fix: Session High/Low Broken Detection - Mehrfach-Aktivierung verhindert

Problem:
- broken_low/broken_high aktivierten sich mehrfach beim gleichen Level
  (z.B. 11.09.2024 um 00:30 + 03:40 am US Low)
- Verwirrte RL Agent Training (gleicher Level = neues Signal)

Root Cause:
- Keine Persistierung welche Levels bereits aktiviert wurden
- Detection prüfte nur aktuellen Zustand, kein "Gedächtnis"

Lösung: "Einmal aus = für immer blockiert"
- 4 Tracking-Listen (Sets) implementiert:
  * currentBrokenHighs/Lows - gerade aktiv
  * hadBrokenHighs/Lows - war aktiv, jetzt aus (permanent blockiert)
- 3 Zustände: Noch nie → Aktiv → Blockiert
- near_low/near_high komplett entfernt (nur noch broken)
- Cleanup bei Session-Ende (Line Removal) + Go To Date

Änderungen:
- static/js/indicators.js:
  * Class Properties: 4 neue Sets (current/had)
  * getCurrentState(): Broken Detection mit State Tracking
  * Deaktivierungs-Logic: current → had Move
  * getAllLevelsWithGracePeriod(): Cleanup für neue Listen
- static/js/chart.js:
  * Chart Reinitialize: Liste-Cleanup
  * Go To Date: Liste-Cleanup

Testing:
- Manueller Test: 11.09.2024 00:30 + 03:40 (US Low)
- Erwartung: broken_low nur bei 00:30, bei 03:40 blockiert
- Console-Logs: "AKTIVIERT" → "DEAKTIVIERT" → "BLOCKIERT"

Prevention:
- State Machine mit Deaktivierungs-Detection
- Grace Period als natürlicher Reset-Trigger
```

---

## Debugging Tipps

### Problem: Signal aktiviert sich immer noch mehrfach

**Check 1: Console Logs**
```javascript
// Sollte bei erster Aktivierung erscheinen:
🔔 [Broken Low] AKTIVIERT für 19500.00 (First Break)

// Sollte bei Deaktivierung erscheinen:
⚠️ [Broken Low] DEAKTIVIERT für 19500.00 → PERMANENT BLOCKIERT!

// Sollte bei zweiter Aktivierung erscheinen:
🚫 [Broken Low] PERMANENT BLOCKIERT für 19500.00
```

Wenn "BLOCKIERT" nicht erscheint → Code wurde nicht korrekt implementiert.

**Check 2: Set Contents**
```javascript
// In Browser Console während Chart-Session:
const indicator = window.IndicatorManager.indicators
  .find(i => i.type === 'SESSION_HL').indicator;

console.log('Current:', indicator.currentBrokenLows);
console.log('Had:', indicator.hadBrokenLows);

// Output sollte Sets mit Price-Strings sein:
// Current: Set(1) { "19500.00" }  (wenn gerade aktiv)
// Had: Set(1) { "19500.00" }  (wenn deaktiviert)
```

**Check 3: Price-Key Format**
```javascript
// Verify dass .toFixed(2) verwendet wird:
const priceKey = sessionLow.toFixed(2);  // "19500.00"
```

### Problem: Listen werden nicht bereinigt

**Check 1: Cleanup wird aufgerufen**
```javascript
// Console sollte zeigen:
🧹 [Session HL Cleanup] Current: H=0 L=0 | Had: H=0 L=0
```

**Check 2: getAllLevelsWithGracePeriod wird regelmäßig aufgerufen**
Diese Methode wird bei jedem `update()` Call aufgerufen → sollte automatisch passieren.

**Check 3: currentValidPrices Set ist korrekt**
```javascript
// Sollte nur noch sichtbare Levels enthalten
console.log(currentValidLowPrices);  // Set(2) { "19650.00", "19500.00" }
```

---

## Datum

**Problem entdeckt:** Nach 36 Stunden Debugging
**Fix implementiert:** 2025-11-06
**Severity:** Medium (verwirrt RL Agent Training, aber kein Crash)
**Impact:** Verbesserte Signal-Qualität für RL Agent

**Design Decision:** Near Detection entfernt - RL Agent fokussiert nur auf echte Breakouts (broken)
**Tested by:** Manueller Test mit 11.09.2024 Daten
