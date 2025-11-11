# Bugfix: Skip & Trade Persistence nach Server-Neustart

**Datum**: 2025-11-11
**Priorität**: CRITICAL
**Status**: ✅ FIXED

---

## 🐛 Problem

Nach Server-Neustart:
1. **Zeit springt zurück** - Chart zeigt alte Zeit statt geskippter Zeit
2. **Trades tauchen wieder auf** - Geschlossene Trades (via SL/TP) sind wieder offen

### Beispiel
```
1. Skip von 08:00 → 08:20
2. Trade schließt sich bei TP (16708)
3. Server-Neustart
4. ❌ Zeit zurück auf 08:00
5. ❌ Trade wieder offen
```

---

## 🔍 Root Cause

### Problem 1: Zeit-Persistence
**Datei**: `charts/services/navigation_service.py:135-196`

```python
# ❌ VORHER: Zeit wurde NICHT gespeichert
def skip_forward(self, timeframe: str):
    skip_result = self.debug_controller.skip_with_real_data(timeframe)
    # ... skip logic ...
    return {'candle': candle, 'success': True}
    # Zeit nur im Memory - nicht persistiert!
```

**Datei**: `charts/chart_server.py:435`
```python
# ❌ Lädt immer Start-Zeit statt geskippter Zeit
saved_time = time_config.get('initial_go_to_date')
```

### Problem 2: Trade-State bei SL/TP Touch
**Datei**: `charts/routes/debug.py:220`

```python
# ❌ VORHER: Account-State wurde NICHT gespeichert
close_result = account_service.close_position(position_id, close_price, reason)
# await manager.broadcast(...)
# Kein save_account_state() → Trade-Closure nicht persistiert!
```

### Problem 3: Initialisierungs-Reihenfolge
**Datei**: `charts/chart_server.py:308 vs 330`

```python
# ❌ NavigationService vor ConfigService erstellt
navigation_service = NavigationService(..., config_service=config_service)  # Line 308
config_service = ConfigService()  # Line 330 - ZU SPÄT!
# → 'NoneType' object has no attribute 'update_time_config'
```

---

## ✅ Lösung

### Fix 1: Zeit nach Skip speichern
**Datei**: `charts/services/navigation_service.py`

```python
def __init__(self, ..., config_service):  # ← config_service hinzugefügt
    self.config_service = config_service

def skip_forward(self, timeframe: str):
    # ... skip logic ...

    # 💾 PERSISTENCE: Speichere aktuelle Zeit nach Skip
    current_time = self.unified_time.get_current_time()
    if current_time:
        self.config_service.update_time_config(
            current_debug_time=current_time.isoformat()
        )
        print(f"[NavigationService] Time saved to config: {current_time.isoformat()}")

    return {'candle': candle, 'success': True}
```

### Fix 2: Trade-State bei SL/TP Touch speichern
**Datei**: `charts/routes/debug.py:220-225`

```python
close_result = account_service.close_position(position_id, close_price, reason, account_type)
if close_result['success']:
    print(f"[SKIP] Position closed: {position_id} - {reason} at {close_price}")

    # 💾 PERSISTENCE: Speichere Account State nach SL/TP Touch
    config_service.save_account_state(account_service.to_dict())
    print(f"[SKIP] Account state saved after {reason}")

    # Broadcast position closure...
```

### Fix 3: Korrekte Zeit-Wiederherstellung
**Datei**: `charts/chart_server.py:435-437`

```python
# Priorisiere current_debug_time (nach Skip) über initial_go_to_date (Start-Zeit)
saved_time = time_config.get('current_debug_time') or time_config.get('initial_go_to_date')
```

### Fix 4: Initialisierungs-Reihenfolge
**Datei**: `charts/chart_server.py:308-310`

```python
# ✅ ConfigService VOR NavigationService
config_service = ConfigService()  # Zuerst!

navigation_service = NavigationService(
    ...,
    config_service=config_service  # Jetzt verfügbar
)
```

---

## 📊 Persistent State JSON

**Datei**: `charts/config/persistent_state.json`

```json
{
  "time": {
    "current_debug_time": "2024-01-03T08:20:00",  // ← Nach Skip
    "initial_go_to_date": "2024-01-03T08:00:00"   // ← Ursprung
  },
  "account_state": {
    "user_account": {
      "active_positions": { /* ... */ },           // ← Offene Trades
      "closed_positions": [ /* ... */ ]            // ← Geschlossene Trades
    }
  }
}
```

---

## 🧪 Verifikation

### Test-Workflow
```bash
1. Server starten → Zeit: 08:00
2. Skip 3x         → Zeit: 08:15
3. Check JSON      → "current_debug_time": "2024-01-03T08:15:00" ✅
4. Server restart  → Zeit: 08:15 ✅
5. Trade öffnen
6. Skip bis TP     → Trade schließt sich
7. Check JSON      → closed_positions[...] ✅
8. Server restart  → Trade bleibt geschlossen ✅
```

### Logs
```
[NavigationService] Skip forward: 5m
[NavigationService] Skip event saved: 5m -> Total: 1 events
[NavigationService] Time saved to config: 2024-01-03T08:05:00  ← ✅
[NavigationService] Skip completed: incomplete_candle

[SKIP] Position closed: pos_123 - take_profit at 16708.0
[SKIP] Account state saved after take_profit  ← ✅
```

---

## 📝 Betroffene Dateien

1. `charts/services/navigation_service.py` - Zeit-Speicherung
2. `charts/routes/debug.py` - Trade-State Speicherung
3. `charts/chart_server.py` - Zeit-Wiederherstellung & Init-Order
4. `charts/services/config_service.py` - Keine Änderungen (bereits korrekt)

---

## 🔒 Prevention

**Code Review Checklist:**
- [ ] Alle State-Änderungen persistieren?
- [ ] Dependency-Reihenfolge korrekt?
- [ ] Server-Neustart getestet?
- [ ] JSON-Config verifiziert?

**Test Cases:**
- Skip → Restart → Zeit korrekt?
- Trade öffnen → Skip bis SL → Restart → Trade geschlossen?
- Trade öffnen → Skip bis TP → Restart → Trade geschlossen?

---

## 📈 Impact

- **Kritikalität**: CRITICAL (Datenverlust)
- **Betroffene Features**: Skip, Trading, Persistence
- **User Impact**: Kein Fortschrittsverlust mehr
- **Performance**: Minimal (1 JSON-Write pro Skip)
