# Timezone-Aware Feature Extraction Fix

## Problem
Feature-Extraction schlug fehl mit:
```
TypeError: Cannot subtract tz-naive and tz-aware datetime-like objects
```

**Ursache:**
- Production DataFrame: UTC-aware (`datetime64[ns, UTC]`)
- Timestamps von Frontend: timezone-naive
- Pandas verbietet Vergleiche zwischen tz-aware und tz-naive datetimes

**Impact:**
- Market Context Features hatten Default-Werte (0.0, 1.0)
- Trade-Specific Features: duration=0, max_drawdown=0.0
- 17-Feature System war unbrauchbar für RL Training

## Lösung

### Intelligente Timezone-Anpassung
Beide Dateien automatisch an DataFrame anpassen:

**charts/core/market_context_extractor.py (calculate_trade_features)**
```python
# Match timezone awareness to DataFrame index
if df.index.tz is not None:
    # DataFrame is timezone-aware -> make timestamps timezone-aware
    if entry_dt.tz is None:
        entry_dt = entry_dt.tz_localize(df.index.tz)
    if exit_dt.tz is None:
        exit_dt = exit_dt.tz_localize(df.index.tz)
else:
    # DataFrame is timezone-naive -> remove timezone from timestamps
    if entry_dt.tz is not None:
        entry_dt = entry_dt.replace(tzinfo=None)
    if exit_dt.tz is not None:
        exit_dt = exit_dt.replace(tzinfo=None)
```

**charts/routes/websocket_handler.py (_extract_market_context_features)**
```python
# Find entry candle index
entry_dt = pd.to_datetime(entry_time)

# Match timezone awareness to DataFrame index
if df.index.tz is not None:
    if entry_dt.tz is None:
        entry_dt = entry_dt.tz_localize(df.index.tz)
else:
    if entry_dt.tz is not None:
        entry_dt = entry_dt.replace(tzinfo=None)
```

## Validation Results

### Before Fix
```
distance_to_ema20_pct: 0.0        # ❌ Default
volume_ratio: 1.0                 # ❌ Fallback
atr_value: 0.0                    # ❌ Default
rr_ratio: 0.0                     # ❌ Default
trade_duration_candles: 0         # ❌ Fehler
max_drawdown_pct: 0.0             # ❌ Fehler
```

### After Fix
```
distance_to_ema20_pct: 0.02       # ✅ Berechnet
volume_ratio: 0.77                # ✅ Berechnet
atr_value: 15.82                  # ✅ Berechnet
recent_high_distance_pct: -0.45   # ✅ Berechnet
recent_low_distance_pct: 0.21     # ✅ Berechnet
position_in_range: 0.324          # ✅ Berechnet
rr_ratio: 2.00                    # ✅ Berechnet
trade_duration_candles: 51        # ✅ Berechnet
max_drawdown_pct: -0.35           # ✅ Berechnet
```

## Test Command
```bash
py scripts/test_features.py
```

Alle Validierungen: ✅ PASSED
- 7 Market Context Features
- 2 Trade-Specific Features
- Keine NaN/Inf Werte
- Alle Ranges korrekt

## Benefits
1. **Robustheit:** Funktioniert mit timezone-aware UND timezone-naive DataFrames
2. **Production-Ready:** CSVLoader nutzt `.tz_localize('UTC')` → funktioniert
3. **Test-Ready:** Test-Scripts ohne Timezone → funktioniert
4. **Kein Breaking Change:** Bestehender Code bleibt kompatibel

## Related Files
- `charts/core/market_context_extractor.py` - Lines 226-237
- `charts/routes/websocket_handler.py` - Lines 65-73
- `scripts/test_features.py` - Validation script
- `docs/FEATURE_SPECIFICATION.md` - 17-Feature Spec
