# RL Trading System mit Human-in-the-Loop Feedback

Ein interaktives Reinforcement Learning Trading System mit **modularisierter Streamlit Trading App**, inspiriert vom Trackmania Beispiel, wo gezieltes Human Feedback verwendet wird, um der KI spezifische Trading-Patterns beizubringen.

## 🚀 Zwei Modi verfügbar:

### 1. **Streamlit Trading App** (Neu - Modularisiert)
```bash
# Neue modularisierte Trading App starten
py -m streamlit run src/app.py --server.port 8504 --server.headless true
```
- TradingView Lightweight Charts
- NQ=F Standard-Asset, UTC+2 Zeitzone
- Debug-Modus mit historischer Simulation
- Modularisierte, erweiterbare Architektur

### 2. **RL Training System** (Original)
```bash
# RL Training mit Human Feedback
python src/main.py --mode demo --episodes 3
```
- Human-in-the-Loop Training
- Pattern Detection (FVG, Order Blocks)
- Live Data Integration

## 🎯 Kern-Features

### 🤖 Modulares Reward System
- **PnL Rewards**: Standard Trading Performance
- **FVG Rewards**: Fair Value Gap Bonuses (wie Trackmania Drift-Punkte)
- **Order Block Rewards**: Support/Resistance Trading
- **Liquidity Zone Rewards**: Magnet-Zonen für Preisbewegungen
- **Human Feedback**: Manuelles Training durch Bewertungen
- **Risk Management**: Bestrafung für schlechtes Risk Management

### 📊 Pattern Detection
- **Fair Value Gaps (FVG)**: Preislücken die als Magnete wirken
- **Order Blocks**: High-Volume Support/Resistance Zonen
- **Liquidity Zones**: Bereiche mit hoher Liquidität
- **Market Structure**: Trend-Erkennung (Higher Highs/Lower Lows)

### 🔴 Live Data Integration
- **Binance WebSocket**: Real-time Kerzendaten
- **Historical Data**: REST API für Backtesting
- **Multi-Timeframe**: 1m, 5m, 15m, 1h Support
- **Error Handling**: Automatische Reconnection

### 🎮 Human-in-the-Loop Training
- **Demo Mode**: Menschliche Demonstrationen sammeln
- **Interactive Training**: Periodisches Feedback während Training
- **Pattern Learning**: KI lernt von deinen Trading-Entscheidungen
- **Adaptive Learning**: Learning Rate basierend auf Performance

## 🚀 Quick Start

### Installation

```bash
# Clone Repository
git clone <repository-url>
cd RL-Trading

# Install Dependencies
pip install -r requirements.txt

# Setup Environment
cp .env.template .env
# Edit .env mit deinen Binance API Keys (optional)
```

### Demo Mode (Empfohlen für Anfang)

```bash
# Sammle menschliche Demonstrationen
python src/main.py --mode demo --episodes 3

# Mit spezifischem Symbol
python src/main.py --mode demo --symbol ETHUSDT --episodes 5
```

In diesem Modus tradest du manuell und bewertest deine eigenen Trades. Das System lernt von deinen Entscheidungen.

### Training Mode

```bash
# Training mit Human Feedback
python src/main.py --mode train --timesteps 20000

# Mit Live-Daten (API Keys erforderlich)
python src/main.py --mode train --live --timesteps 10000
```

Während des Trainings wirst du periodisch nach Feedback für die Performance des Agents gefragt.

### Evaluation Mode

```bash
# Evaluiere trainierten Agent
python src/main.py --mode eval --episodes 10

# Mit spezifischem Modell
python src/main.py --mode eval --model models/trading_agent_20231201_143022 --episodes 5
```

## 📁 Projektstruktur

```
RL-Trading/
├── .claude/                    # Claude Code Settings
├── .claude-preferences.md      # Entwickler Preferences & Standards
├── src/                        # Hauptquellcode (modularisiert)
│   ├── app.py                  # Streamlit Trading App (NEU)
│   ├── main.py                 # RL Training Entry Point
│   ├── config/                 # Konfigurationsdateien
│   │   └── settings.py         # App-weite Einstellungen
│   ├── components/             # UI Components (NEU)
│   │   ├── chart.py           # TradingView Chart Komponente
│   │   ├── sidebar.py         # Sidebar mit Einstellungen
│   │   └── trading_panel.py   # Trading Panel & Controls
│   ├── data/                   # Datenverarbeitung
│   │   └── yahoo_finance.py   # Yahoo Finance API Integration
│   ├── utils/                  # Hilfsfunktionen
│   │   └── constants.py       # Asset-Definitionen & Konstanten
│   ├── env.py                  # Trading Environment mit Reward Shaping
│   ├── rewards.py              # Modulare Reward-Komponenten
│   ├── patterns.py             # Pattern Detection (FVG, Order Blocks)
│   ├── agent.py                # PPO Agent mit Custom Features
│   └── data_feed.py            # Binance API Integration
├── tests/                      # Tests (zukünftig)
├── backup_20250917/            # Backup der alten Struktur
├── models/                     # Gespeicherte Modelle
├── requirements.txt            # Python Dependencies
├── .env.template              # Environment Template
└── README.md                  # Diese Datei
```

## 🎮 Wie das Human Feedback funktioniert

### 1. Demo Mode - Sammle Demonstrationen
Genau wie im Trackmania Video, wo der Entwickler manuell driftet:

```python
# Du tradest manuell:
Your action (0=Hold, 1=Buy, 2=Sell): 1
✅ Trade executed: BUY at $45,230.50

# Du bewertest deinen Trade:
Rate this trade (-1=bad, 0=neutral, 1=good): 1
📝 Feedback recorded: 1.0
```

### 2. Training Mode - Periodisches Feedback
Während das AI trainiert, fragst du periodisch:

```python
=== FEEDBACK REQUEST ===
Recent average reward: 12.5
Episode: 50

Recent trades:
  buy at 45230.50
  sell at 45280.20
  buy at 45150.30

Rate recent performance (-1 to 1, or skip): 0.8
```

### 3. Pattern-spezifisches Feedback
Das System erkennt wenn bestimmte Patterns auftreten:

```python
🎯 Patterns: FVG=True, OB=True
# AI traded in einer FVG Zone bei einem Order Block
# Dein Feedback: +1 (gut!)
# → System lernt: "FVG + Order Block = gute Trading-Gelegenheit"
```

## ⚙️ Konfiguration

### Reward Gewichtungen anpassen

```python
# Während Training oder in Code:
env.set_reward_weight("fvg", 1.5)        # Mehr FVG Fokus
env.set_reward_weight("human", 3.0)      # Human Feedback wichtiger
env.set_reward_weight("risk_management", 0.8)  # Weniger Risk Focus
```

### Environment Parameter

```python
env = InteractiveTradingEnv(
    df=data,
    initial_cash=10000,          # Starting Capital
    transaction_cost=0.001,      # 0.1% Trading Fees
    max_position_size=1.0,       # Max 100% invested
    enable_patterns=True,        # Pattern Detection aktiviert
    reward_config={
        'weights': {
            'pnl': 1.0,
            'fvg': 0.8,
            'human': 2.0
        }
    }
)
```

## 📈 Beispiel Training Session

```bash
# 1. Sammle erst Demonstrationen
python src/main.py --mode demo --episodes 5

# 2. Trainiere mit deinem Feedback
python src/main.py --mode train --timesteps 20000

# 3. Evaluiere Performance
python src/main.py --mode eval --episodes 10

# 4. Weitere Verbesserungen mit mehr Feedback
python src/main.py --mode train --timesteps 10000
```

## 🔴 Live Trading (Paper)

**⚠️ WARNUNG: Nur mit gut-trainierten Modellen verwenden!**

```bash
# Setup API Keys in .env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here

# Starte Live Paper Trading
python src/main.py --mode live --live
```

## 📊 Monitoring & Analysis

### Training Logs
- TensorBoard Logs in `./tensorboard_logs/`
- Wandb Integration optional verfügbar
- Human Feedback wird in `.pkl` Dateien gespeichert

### Performance Metriken
- Portfolio Value & PnL
- Sharpe Ratio & Max Drawdown
- Win Rate & Trade Count
- Pattern Hit Rate (FVG, Order Blocks)

## 🤝 Contributing

Dieses System ist designed um erweitert zu werden:

1. **Neue Patterns hinzufügen**: Erweitere `patterns.py`
2. **Neue Rewards**: Füge Komponenten in `rewards.py` hinzu
3. **Andere Assets**: Modifiziere `data_feed.py` für Forex/Stocks
4. **Different Agents**: Implementiere SAC oder andere RL Algorithms

## 📚 Inspiration

Dieses System ist inspiriert vom [Trackmania AI Video](https://www.youtube.com/watch?v=Ih8EfvOzBOY), wo gezeigt wurde wie Human Feedback verwendet werden kann um einer AI spezifische Verhaltensweisen beizubringen - in dem Fall Driften.

Hier bringen wir der AI bei:
- **FVG Zones** wie Drift-Punkte anzusteuern
- **Order Blocks** wie Checkpoints zu respektieren
- **Risk Management** wie Speed Control zu praktizieren
- **Pattern Recognition** wie Track-Analyse zu betreiben

## ⚠️ Disclaimers

- **Kein Financial Advice**: Dies ist ein Lern-/Forschungsprojekt
- **Paper Trading**: Verwende nie echtes Geld ohne extensive Tests
- **API Limits**: Respektiere Binance Rate Limits
- **Risk Management**: Implementiere immer Stop-Losses in Live Trading

## 🎯 Roadmap

- [ ] Streamlit Dashboard für Live Monitoring
- [ ] More Pattern Types (Volume Profile, etc.)
- [ ] Portfolio Optimization Features
- [ ] Multi-Asset Trading Support
- [ ] Advanced Risk Management
- [ ] Backtesting Engine mit Walk-Forward Analysis

---

**Happy Trading! 🚀📈**

*"Teaching AI to trade is like teaching it to drift - it's all about the right feedback at the right moments."*