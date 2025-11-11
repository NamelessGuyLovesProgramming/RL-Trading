# RL Training Features - Finale Spezifikation

**Erstellt:** 2025-11-11
**Zweck:** Dokumentation der 17 Features für RL Model Training
**Status:** Genehmigt - Bereit für Implementierung

---

## 🎯 Überblick

Das RL-Modell lernt aus **17 Features pro Trade**:
- 9 Trade-Basics
- 7 Market-Context Features (Snapshot bei Entry!)
- 1 Human Rating

**Ziel:** 200 bewertete Trades → KI lernt was gute/schlechte Entries sind

---

## 📊 Feature-Liste (17 Total)

### **1. Trade-Basics (9 Features)**

| # | Feature | Typ | Beschreibung | Beispiel |
|---|---------|-----|--------------|----------|
| 1 | `entry_price` | float | Entry Preis in $ | 10000.50 |
| 2 | `sl_price` | float | Stop Loss in $ | 9950.00 |
| 3 | `tp_price` | float | Take Profit in $ | 10200.00 |
| 4 | `exit_price` | float | Tatsächlicher Exit in $ | 10180.25 |
| 5 | `entry_time` | ISO string | Wann eingestiegen | "2024-01-03T14:30:00" |
| 6 | `exit_time` | ISO string | Wann ausgestiegen | "2024-01-03T16:45:00" |
| 7 | `trade_duration_candles` | int | Anzahl 5m-Kerzen im Trade | 27 |
| 8 | `realized_pnl` | float | Gewinn/Verlust in $ | +180.25 |
| 9 | `max_drawdown_pct` | float | Max Drawdown in % | -0.8 |

### **2. Market-Context (7 Features) - Snapshot bei Entry!**

| # | Feature | Typ | Beschreibung | Beispiel | Berechnung |
|---|---------|-----|--------------|----------|------------|
| 10 | `distance_to_ema20_pct` | float | Abstand zu EMA-20 in % | +0.5 | `(entry_price - ema20) / ema20 * 100` |
| 11 | `volume_ratio` | float | Entry-Vol / Ø-Volume | 1.5 | `entry_volume / avg_volume_20` |
| 12 | `atr_value` | float | Average True Range | 25.0 | Standard ATR(14) |
| 13 | `recent_high_distance_pct` | float | Abstand zu 50-Kerzen High | -1.0 | `(entry - high50) / entry * 100` |
| 14 | `recent_low_distance_pct` | float | Abstand zu 50-Kerzen Low | +2.0 | `(entry - low50) / entry * 100` |
| 15 | `position_in_range` | float | Position im 50-Kerzen Range | 0.67 | `(entry - low) / (high - low)` |
| 16 | `rr_ratio` | float | Risk/Reward Ratio | 5.0 | `(tp - entry) / (entry - sl)` |

### **3. Human Feedback (1 Feature)**

| # | Feature | Typ | Beschreibung | Werte |
|---|---------|-----|--------------|-------|
| 17 | `rating` | float | Bewertung: gut/ok/schlecht | 1.0 / 0.5 / 0.0 |

---

## ❌ Bewusst NICHT inkludiert

| Feature | Warum nicht? |
|---------|--------------|
| **Session-Zeit** | Timezone-Risiko! Sommerzeit/Winterzeit könnte Fehler verursachen |
| **FVG/Inverse FVG** | Zu komplex ohne LSTM - später hinzufügen wenn nötig |
| **Entry/Exit-Kerze OHLC** | Redundant - Max Drawdown zeigt Volatilität bereits |
| **Alle Kerzen zwischen Entry/Exit** | Zu viele Daten - würde LSTM/Transformer brauchen |

---

## 🔍 Warum diese Features?

### **Trade-Basics:**
- KI lernt: "Wie sah der Trade aus?" (Preise, Dauer, Ergebnis)

### **Market-Context:**
- KI lernt: "War der Entry-Zeitpunkt gut gewählt?"
- Beispiele:
  - Entry nahe am High + hohes Volume → oft Reversal → schlecht
  - Entry unter EMA + niedriges Volume → gegen Trend → riskant
  - Gutes R:R Ratio (>2) aber Max Drawdown groß → SL zu eng

### **Human Rating:**
- Supervision Signal - KI weiß was "gut" ist

---

## 📐 Berechnungs-Details

### **Max Drawdown (Feature #9):**
```python
# Hole alle Kerzen zwischen Entry und Exit
candles = df.loc[entry_time:exit_time]

# Für Long Trade:
lowest_price = candles['low'].min()
max_drawdown_pct = (lowest_price - entry_price) / entry_price * 100

# Für Short Trade:
highest_price = candles['high'].max()
max_drawdown_pct = (highest_price - entry_price) / entry_price * 100
```

### **EMA-20 Distance (Feature #10):**
```python
df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
entry_ema = df.loc[entry_time, 'ema_20']
distance_pct = (entry_price - entry_ema) / entry_ema * 100
```

### **Volume Ratio (Feature #11):**
```python
avg_volume = df['volume'].iloc[-20:].mean()  # Letzte 20 Kerzen
entry_volume = df.loc[entry_time, 'volume']
volume_ratio = entry_volume / avg_volume
```

### **ATR (Feature #12):**
```python
high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
ranges = pd.concat([high_low, high_close, low_close], axis=1)
true_range = np.max(ranges, axis=1)
atr = true_range.rolling(14).mean()
entry_atr = atr.loc[entry_time]
```

### **Recent High/Low (Features #13-15):**
```python
lookback = 50  # 50 Kerzen = ~4 Stunden bei 5m
recent_data = df.iloc[-lookback:]
recent_high = recent_data['high'].max()
recent_low = recent_data['low'].min()

high_distance_pct = (entry_price - recent_high) / entry_price * 100
low_distance_pct = (entry_price - recent_low) / entry_price * 100
position_in_range = (entry_price - recent_low) / (recent_high - recent_low)
```

### **R:R Ratio (Feature #16):**
```python
risk = abs(entry_price - sl_price)
reward = abs(tp_price - entry_price)
rr_ratio = reward / risk
```

---

## ✅ Validierungs-Kriterien

**Nach Implementierung MUSS geprüft werden:**

1. **Range Checks:**
   - `distance_to_ema20_pct`: -10% bis +10%
   - `volume_ratio`: 0 bis 10 (extrem: bis 20)
   - `atr_value`: > 0
   - `position_in_range`: 0 bis 1
   - `max_drawdown_pct`: <= 0 (für Long), >= 0 (für Short)
   - `rr_ratio`: > 0

2. **NaN/Inf Checks:**
   - Keine NaN Werte
   - Keine Infinity Werte
   - Alle Features numerisch

3. **Logical Checks:**
   - `trade_duration_candles` >= 1
   - `exit_time` > `entry_time`
   - Wenn Trade gewonnen: `realized_pnl` > 0

---

## 📈 Training-Strategie

**Phase 1: Daten sammeln (200 Trades)**
- User tradet manuell
- Bewertet jeden Trade (gut/ok/schlecht)
- System speichert alle 17 Features

**Phase 2: Model Training**
- Input: 16 Features (1-16)
- Output: Vorhersage ob Trade gut/ok/schlecht
- Supervision: Feature 17 (rating)

**Phase 3: Model Anwendung**
- KI schaut auf aktuellen Market-Context
- Berechnet Features 10-16
- Entscheidet: Entry nehmen oder nicht?

---

## 🚨 Kritische Anmerkungen

**Warum NUR 17 Features?**
- Mit 200 Trades: ~12 Samples pro Feature
- Mehr Features = Overfitting-Risiko
- Weniger Features = Zu simple Patterns

**Warum Market-Context nur bei Entry?**
- KI soll Entry-Qualität lernen, nicht Trade-Management
- Trade-Management (Exit) ist separates Problem
- Fokus: "War Entry-Setup gut?"

**Können Features später erweitert werden?**
- JA! DB-Schema erweiterbar
- Später: Session-Zeit (mit pytz)
- Später: FVG/IFVG (wenn LSTM kommt)

---

## 📝 Nächste Schritte

1. ✅ Feature-Specification dokumentiert
2. ⏳ DB-Schema erweitern (neue Spalten)
3. ⏳ Feature-Extraction Code schreiben
4. ⏳ Validation Script schreiben
5. ⏳ Integration in Feedback-System
6. ⏳ Test mit 1 Trade
7. ⏳ Sammeln von 200 Trades

---

**Erstellt von:** Claude
**Reviewed von:** User
**Status:** APPROVED ✅
