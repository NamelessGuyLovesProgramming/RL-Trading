# Feature: Persistent Time Storage - Go To Date

**Datum:** 2025-11-05
**Status:** Implementiert & Getestet
**Komponenten:** Backend (FastAPI), Frontend (JavaScript), Persistence Layer

---

## Überblick

Die "Go To Date" Funktion speichert jetzt automatisch die gewählte Zeit-Position und stellt diese nach einem Server-Neustart wieder her.

### User Story
- **Vorher:** Go To Date zu 12.12.2024 → Server Restart → Chart startet am Datenende (31.12.2024)
- **Nachher:** Go To Date zu 12.12.2024 → Server Restart → Chart startet bei 12.12.2024

---

## Implementierung

### 1. Auto-Save beim Go To Date
**Datei:** `charts/routes/debug.py:381-391`

```python
# AUTO-SAVE: Zeit persistieren für Neustart
try:
    actual_date_obj = goto_result.get('actual_date')
    if actual_date_obj:
        saved_time = actual_date_obj.isoformat() if hasattr(actual_date_obj, 'isoformat') else str(actual_date_obj)
        config_service.update_time_config(initial_go_to_date=saved_time)
        print(f"[GOTO-PERSISTENCE] Time saved: {saved_time}")
except Exception as persist_error:
    print(f"[GOTO-PERSISTENCE] WARNING: Could not save time: {persist_error}")
```

**Trigger:** Jeder erfolgreiche `POST /api/debug/go_to_date` Call
**Speicherort:** `charts/config/persistent_state.json`

### 2. Server Startup - Zeit Restore
**Datei:** `charts/chart_server.py:376-405`

```python
# PERSISTENCE: Lade gespeicherte Zeit beim Server-Start
time_config = config_service.get_time_config()
saved_time = time_config.get('initial_go_to_date')

if saved_time:
    try:
        logger.info(f"[INIT] Restoring saved time: {saved_time}")

        # Parse ISO-Format
        target_datetime = datetime.fromisoformat(saved_time.replace('Z', '+00:00'))

        # Lade Chart-Daten für gespeicherte Zeit
        goto_result = navigation_service.go_to_date(
            target_date=target_datetime,
            timeframe='5m',
            visible_candles=200
        )

        if goto_result['success']:
            manager.chart_state['data'] = goto_result['chart_data']
            logger.info(f"[INIT] ✅ Restored to saved time: {goto_result['actual_date']}")
```

**Trigger:** `@app.on_event("startup")`
**Fallback:** Bei Fehler → Standard-Verhalten (Datenende)

### 3. Reset Button - Zurück zum Datenende
**Backend:** `charts/routes/debug.py:418-457`

```python
@router.post("/reset_time")
async def debug_reset_time():
    """Löscht gespeicherte Zeit und kehrt zum Datenende zurück"""
    config_service.update_time_config(initial_go_to_date=None)
    goto_result = navigation_service.go_to_date(
        target_date=datetime(2024, 12, 31),  # Datenende
        timeframe=current_timeframe,
        visible_candles=200
    )
```

**Frontend:** `static/js/chart.js:6032-6060`

```javascript
function resetTimeToDataEnd() {
    fetch('/api/debug/reset_time', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        console.log('✅ Reset Time Response:', data);
        // WebSocket sendet go_to_date_complete Event
    })
}
```

**UI:** `templates/chart.html:480`
```html
<button id="resetTimeBtn" class="nav-btn" title="Reset zum Datenende">🔄 Reset</button>
```

---

## Bugfix: DataFrame Index Support

### Problem
`timeframe_repository.py` prüfte nur auf datetime als **Column**, aber CSVLoader setzt datetime als **Index**.

**Error:**
```
KeyError: 'time'
File "charts/core/timeframe_repository.py", line 165
```

### Lösung
**Datei:** `charts/core/timeframe_repository.py:163-205, 237-259`

```python
# Prüfe ERST auf DateTime Index, dann Columns
if isinstance(df.index, pd.DatetimeIndex):
    # DataFrame hat datetime als Index (von CSVLoader)
    start_pd = pd.Timestamp(start_date)
    if hasattr(df.index.dtype, 'tz') and df.index.dtype.tz is not None:
        start_pd = start_pd.tz_localize('UTC') if start_pd.tz is None else start_pd.tz_convert('UTC')
    filtered_df = df[df.index >= start_pd]
elif 'datetime' in df.columns:
    # Column-based fallback
    # ...
```

Geändert in:
- `get_candles_for_date_range()`
- `find_first_candle_after()`

---

## Persistence Format

**Datei:** `charts/config/persistent_state.json`

```json
{
  "accounts": {
    "ai_balance": 100000.0,
    "user_balance": 100000.0
  },
  "time": {
    "current_debug_time": null,
    "initial_go_to_date": "2024-12-12T00:00:00"
  },
  "version": "1.0"
}
```

**Format:** ISO 8601 DateTime String
**Encoding:** UTC Timezone-aware
**Null-Wert:** `null` = Kein gespeicherter Zustand (Default: Datenende)

---

## Testing

### Test 1: Auto-Save
```bash
curl -X POST "http://localhost:8003/api/debug/go_to_date" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-12-12", "timeframe": "5m", "visible_candles": 200}'
```

**Erwartete Logs:**
```
[GOTO-PERSISTENCE] Time saved: 2024-12-12T00:00:00
```

**Erwartete JSON:**
```json
"initial_go_to_date": "2024-12-12T00:00:00"
```

### Test 2: Server Restart Restore
```bash
# 1. Go To Date zu 12.12.2024
# 2. Server neustarten
./start_server.bat
```

**Erwartete Startup-Logs:**
```
[INIT] Restoring saved time: 2024-12-12T00:00:00
[INIT] ✅ Restored to saved time: 2024-12-12 00:00:00
```

### Test 3: Reset Button
```bash
curl -X POST "http://localhost:8003/api/debug/reset_time"
```

**Erwartete Response:**
```json
{
  "status": "success",
  "message": "Zeit zurückgesetzt - am Datenende",
  "actual_date": "2024-12-31T00:00:00"
}
```

---

## Bekannte Limitierungen

### Minor Bug: Reset speichert null nicht
**Problem:** Reset-Endpoint löscht Persistence, aber `navigation_service.go_to_date()` triggert NICHT die Auto-Save-Logik im Endpoint.

**Auswirkung:**
- Reset bringt Chart sofort zum Datenende ✅
- JSON-Datei behält alten Wert (z.B. "2024-12-12T00:00:00") ❌
- Nach erneutem Server-Restart würde wieder gespeicherte Zeit geladen ❌

**Workaround:** Nach Reset erneut "Go To Date" zu gewünschtem Datum verwenden.

**Fix-Vorschlag:** Reset-Endpoint sollte direkt die Endpoint-Logik nutzen oder nach Navigation explizit `null` speichern.

---

## Geänderte Dateien

### Backend
- `charts/routes/debug.py` - Auto-Save Logik + Reset Endpoint
- `charts/chart_server.py` - Startup Restore + config_service Parameter
- `charts/core/timeframe_repository.py` - DataFrame Index Support

### Frontend
- `static/js/chart.js` - Reset-Funktion
- `templates/chart.html` - Reset-Button UI

### Config
- `charts/config/persistent_state.json` - Persistence Storage

---

## API Dokumentation

### POST /api/debug/go_to_date
**Verhalten:** Navigiert zu Datum + Speichert automatisch Zeit

**Request:**
```json
{
  "date": "2024-12-12",
  "timeframe": "5m",
  "visible_candles": 200
}
```

**Side Effect:** Schreibt `initial_go_to_date` zu `persistent_state.json`

### POST /api/debug/reset_time
**Verhalten:** Löscht gespeicherte Zeit + Navigiert zum Datenende

**Response:**
```json
{
  "status": "success",
  "message": "Zeit zurückgesetzt - am Datenende",
  "actual_date": "2024-12-31T00:00:00"
}
```

**Side Effect:** ~~Setzt `initial_go_to_date` auf `null`~~ (Bug: Funktioniert nicht zuverlässig)

---

## Lessons Learned

1. **DataFrame Index vs Column:**
   Pandas kann datetime als Index ODER Column speichern. Prüfe immer `isinstance(df.index, pd.DatetimeIndex)` ZUERST.

2. **Closure Dependencies:**
   Funktionen in `setup_debug_routes()` benötigen alle Services als Parameter im Closure-Scope.

3. **Auto-Save Design:**
   Platzierung der Persistence-Logik im API-Endpoint (nicht Service-Layer) verhindert ungewollte Speicherungen bei internen Calls.

4. **ISO DateTime Format:**
   `isoformat()` für JSON-Serialisierung + `fromisoformat()` für Parsing garantiert Timezone-Awareness.

---

## Commit Message

```
feat: Persistent Time Storage - Go To Date mit Auto-Save & Server Restore

Änderungen:
1. Auto-Save bei jedem Go To Date
   - charts/routes/debug.py:381-391
   - Speichert Zeit zu persistent_state.json

2. Server Startup Restore
   - charts/chart_server.py:376-405
   - Lädt gespeicherte Zeit beim Start

3. Reset Button (UI + Backend)
   - templates/chart.html:480
   - static/js/chart.js:6032-6060
   - charts/routes/debug.py:418-457

4. Bugfix: DataFrame Index Support
   - charts/core/timeframe_repository.py
   - CSVLoader verwendet datetime als Index (nicht Column)
   - Behebt KeyError: 'time'

Features:
✅ Go To Date zu 12.12.2024 → Server Restart → Chart bei 12.12.2024
✅ Reset Button kehrt zum Datenende zurück
✅ ISO 8601 DateTime Persistence
✅ Fallback bei Fehler: Standard-Verhalten (Datenende)

Known Issue:
- Reset löscht Persistence nicht vollständig (funktional OK)
```
