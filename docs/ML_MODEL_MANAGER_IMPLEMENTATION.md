# ML Model Manager - Implementierungs-Dokumentation

**Erstellt**: 2025-11-09
**Ziel**: Chart-UI für RL Model Training, Testing & Management
**Status**: 🔴 In Planung

---

## 📋 Executive Summary

Implementierung eines **ML Operations Panels** im Trading Chart UI für:
- **A)** Neue Models trainieren (mit Namen & Steps-Auswahl)
- **B)** Continue Learning (weiteres Training auf existierendem Model)
- **C)** Model Evaluation (Performance auf Test-Daten)
- **D)** Model Hot-Swapping (ohne Server-Restart)

**Kritisch**: Walk-Forward Testing zur Vermeidung von Overfitting!

---

## 🎯 Feature Requirements

### **A) Neues Model Trainieren**

**User Flow:**
1. User klickt "🎓 Train New Model"
2. Dialog öffnet sich:
   - Model Name eingeben (z.B. "strategy_v1")
   - Steps wählen (10K, 50K, 100K)
   - Training Period anzeigen (Auto: 70% der Daten)
3. User klickt "Start Training"
4. Training läuft im Background
5. Live Progress Updates im UI
6. Bei Completion: Model automatisch laden

**Output:**
- `models/strategy_v1.zip` - PPO Model
- `models/strategy_v1.metadata.json` - Performance Metrics
- `models/strategy_v1_test_results.json` - Test-Performance

### **B) Continue Learning**

**User Flow:**
1. User wählt existierendes Model aus Dropdown
2. Klickt "📈 Continue Training (+10K)"
3. System lädt Model + Env-Config aus Metadaten
4. Trainiert weitere 10K Steps
5. Speichert als neue Version: `strategy_v1_continued.zip`

**Warnung**: Zeige Warnung wenn Test-Performance schlechter wird!

### **C) Model Evaluation**

**User Flow:**
1. User wählt Model aus Dropdown
2. Klickt "📊 Evaluate on Test Set"
3. System läuft Model auf Test-Daten (Out-of-Sample!)
4. Zeigt Results:
   - Final Balance (Train vs Test)
   - Win Rate (Train vs Test)
   - Equity Curve Visualization
   - Overfitting Warning (wenn Test << Train)

### **D) Model Hot-Swapping**

**User Flow:**
1. User wählt Model aus Dropdown
2. Model wird sofort geladen (kein Server-Restart!)
3. KI-Modus nutzt neues Model
4. Metadaten im UI updaten

---

## 🏗️ Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                    BROWSER (Chart UI)                       │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Model Dropdown │  │ Train Dialog │  │ Progress Panel │  │
│  └────────────────┘  └──────────────┘  └────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │ WebSocket + REST API
┌───────────────────────▼─────────────────────────────────────┐
│              CHART SERVER (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ML Operations Router (/api/ml/*)                    │   │
│  │  • POST /train       - Start Training                │   │
│  │  • POST /continue    - Continue Training             │   │
│  │  • POST /evaluate    - Evaluate Model                │   │
│  │  • POST /load_model  - Hot-Swap Model                │   │
│  │  • GET  /models      - List All Models               │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Training Manager (src/training_manager.py)          │   │
│  │  • Spawns Training Worker Process                    │   │
│  │  • Monitors Progress via IPC                         │   │
│  │  • Streams Updates via WebSocket                     │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │ subprocess.Popen()
┌───────────────────────▼─────────────────────────────────────┐
│         TRAINING WORKER (src/train_worker.py)               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Walk-Forward Training Loop:                         │   │
│  │  1. Split Data (70% Train, 30% Test)                 │   │
│  │  2. Train PPO Model                                  │   │
│  │  3. Evaluate on Test Set                             │   │
│  │  4. Save Model + Metadata                            │   │
│  │  5. Report Results via stdout (JSON)                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Walk-Forward Testing Strategy

**Best Practice aus Research**: Trainiere NICHT auf ganzen Daten!

### **Strategie 1: Simple Train/Test Split (70/30)**

```
Timeline: Jan 2024 ────────────────────────── Dec 2024
          ├──────────────────┬──────────────┤
          Training (70%)     Test (30%)
          Jan - Sep 15       Sep 16 - Dec
```

**Vorteile:**
- ✅ Einfach zu implementieren
- ✅ Erkennt Overfitting (Test << Train)
- ✅ Standard in ML

**Nachteile:**
- ⚠️ Nur 1 Test-Period (könnte Zufall sein)

### **Strategie 2: Walk-Forward Testing (Empfohlen!)**

```
Timeline: Jan 2024 ────────────────────────── Dec 2024

Round 1:  [Train: Jan-Feb] → [Test: Mar]
Round 2:  [Train: Apr-May] → [Test: Jun]
Round 3:  [Train: Jul-Aug] → [Test: Sep]
Round 4:  [Train: Oct-Nov] → [Test: Dec]

Final Score = Average(Test1, Test2, Test3, Test4)
```

**Vorteile:**
- ✅ Robuster (4 Test-Periods statt 1)
- ✅ Simuliert Live-Trading besser
- ✅ Erkennt Market Regime Changes

**Nachteile:**
- ⚠️ 4x länger Training-Zeit
- ⚠️ Komplexere Implementierung

### **Entscheidung: Strategie 1 für MVP, später Strategie 2**

---

## 📁 Datei-Struktur

### **Neue Dateien:**

```
src/
├── training_manager.py          # Manages training processes
├── train_worker.py              # Background training script
└── model_metadata.py            # Metadata handling

charts/routes/
└── ml_operations.py             # ML API endpoints

static/js/
├── model-manager.js             # UI Component
└── training-progress.js         # Live progress updates

static/css/
└── model-manager.css            # Styling

templates/
└── (chart.html updated)         # Adds Model Manager Panel

models/
├── strategy_v1.zip              # PPO Model
├── strategy_v1.metadata.json   # Metadata
└── strategy_v1_test_results.json # Test performance
```

---

## 🔧 Implementierung Details

### **1. Model Metadaten Format**

**Datei**: `models/{model_name}.metadata.json`

```json
{
  "model_name": "strategy_v1",
  "created_at": "2024-11-09T04:30:00",
  "training_config": {
    "total_steps": 50000,
    "learning_rate": 0.0003,
    "n_steps": 64,
    "batch_size": 32
  },
  "data_split": {
    "train_start": "2024-01-01",
    "train_end": "2024-09-15",
    "test_start": "2024-09-16",
    "test_end": "2024-12-31",
    "train_candles": 49702,
    "test_candles": 21301
  },
  "train_performance": {
    "final_balance": 105450.0,
    "initial_balance": 100000.0,
    "total_return": 0.0545,
    "total_trades": 234,
    "winning_trades": 152,
    "losing_trades": 82,
    "win_rate": 0.6496,
    "avg_win": 450.23,
    "avg_loss": -230.45,
    "max_drawdown": 0.0234
  },
  "test_performance": {
    "final_balance": 102100.0,
    "initial_balance": 100000.0,
    "total_return": 0.021,
    "total_trades": 98,
    "winning_trades": 59,
    "losing_trades": 39,
    "win_rate": 0.6020,
    "avg_win": 420.15,
    "avg_loss": -245.67,
    "max_drawdown": 0.0312
  },
  "overfitting_score": 0.15,
  "env_config": {
    "observation_space": 30,
    "action_space": 3,
    "initial_cash": 100000.0,
    "enable_patterns": false,
    "reward_config": {}
  },
  "version": "1.0"
}
```

**Overfitting Score Berechnung:**
```python
overfitting_score = (train_return - test_return) / train_return
# 0.0 = Perfect (same performance)
# 0.5 = Moderate overfitting
# 1.0 = Extreme overfitting (test return = 0)
```

---

### **2. API Endpoints Specification**

#### **GET /api/ml/models**

**Response:**
```json
{
  "models": [
    {
      "name": "strategy_v1",
      "created_at": "2024-11-09T04:30:00",
      "total_steps": 50000,
      "train_return": 0.0545,
      "test_return": 0.021,
      "overfitting_score": 0.15,
      "is_loaded": true
    },
    {
      "name": "quick_test_20251107",
      "created_at": "2024-11-07T21:37:00",
      "total_steps": 1000,
      "train_return": -0.023,
      "test_return": null,
      "overfitting_score": null,
      "is_loaded": false
    }
  ],
  "current_model": "strategy_v1"
}
```

#### **POST /api/ml/train**

**Request:**
```json
{
  "model_name": "strategy_v2",
  "total_steps": 50000,
  "train_split": 0.7,
  "learning_rate": 0.0003,
  "n_steps": 64,
  "batch_size": 32
}
```

**Response:**
```json
{
  "status": "started",
  "job_id": "train_20241109_043000",
  "estimated_duration_seconds": 3600,
  "message": "Training started in background. Listen to WebSocket for progress."
}
```

#### **POST /api/ml/load_model**

**Request:**
```json
{
  "model_name": "strategy_v1"
}
```

**Response:**
```json
{
  "status": "success",
  "model_name": "strategy_v1",
  "metadata": { /* ... full metadata ... */ },
  "message": "Model loaded successfully. AI mode will use this model."
}
```

#### **POST /api/ml/evaluate**

**Request:**
```json
{
  "model_name": "strategy_v1"
}
```

**Response:**
```json
{
  "status": "started",
  "job_id": "eval_20241109_043000",
  "message": "Evaluation started. Listen to WebSocket for results."
}
```

#### **POST /api/ml/continue**

**Request:**
```json
{
  "base_model": "strategy_v1",
  "new_model_name": "strategy_v1_continued",
  "additional_steps": 10000
}
```

**Response:**
```json
{
  "status": "started",
  "job_id": "continue_20241109_043000",
  "message": "Continue training started."
}
```

---

### **3. WebSocket Messages**

**Training Progress:**
```json
{
  "type": "training_progress",
  "job_id": "train_20241109_043000",
  "model_name": "strategy_v2",
  "current_step": 12345,
  "total_steps": 50000,
  "progress": 0.2469,
  "eta_seconds": 2700,
  "live_metrics": {
    "balance": 101234.5,
    "total_trades": 45,
    "win_rate": 0.6222
  }
}
```

**Training Completed:**
```json
{
  "type": "training_completed",
  "job_id": "train_20241109_043000",
  "model_name": "strategy_v2",
  "success": true,
  "train_performance": { /* ... */ },
  "test_performance": { /* ... */ },
  "overfitting_score": 0.12,
  "duration_seconds": 3456,
  "model_path": "models/strategy_v2.zip"
}
```

**Training Error:**
```json
{
  "type": "training_error",
  "job_id": "train_20241109_043000",
  "error": "OutOfMemoryError",
  "message": "Training failed: Not enough memory to load data",
  "traceback": "..."
}
```

---

### **4. UI Component Wireframe**

```
┌─────────────────────────────────────────────────────────┐
│  🤖 MODEL MANAGER                                  [×]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📦 Current Model:                                      │
│  ┌───────────────────────────────────────────────────┐ │
│  │ strategy_v1                                    ▼ │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  📊 Model Info:                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │  • Created: 09.11.2024 04:30                      │ │
│  │  • Steps: 50,000                                  │ │
│  │  • Train: 105,450€ (+5.45%) ✅                    │ │
│  │  • Test:  102,100€ (+2.10%) ⚠️                    │ │
│  │  • Win Rate: 64.96% (Train) | 60.20% (Test)      │ │
│  │  • Overfitting Score: 0.15 (Low) ✅               │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  🎯 Actions:                                            │
│  ┌───────────────────────────────────────────────────┐ │
│  │  [🎓 Train New Model]                             │ │
│  │  [📈 Continue Training (+10K)]                    │ │
│  │  [📊 Evaluate on Test Set]                        │ │
│  │  [🔄 Reload Model]                                │ │
│  │  [📋 Compare Models]                              │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  📈 Training Progress: (hidden when not training)      │
│  ┌───────────────────────────────────────────────────┐ │
│  │  strategy_v2                                      │ │
│  │  Progress: [████████████░░░░] 12,345 / 50,000    │ │
│  │  ETA: 45m 20s                                     │ │
│  │                                                   │ │
│  │  Live Metrics:                                    │ │
│  │  • Balance: 101,234€ (+1.23%)                    │ │
│  │  • Trades: 45 (Win: 62.2%)                       │ │
│  │                                                   │ │
│  │  [⏸ Pause]  [⏹ Stop Training]                    │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

### **5. Training Dialog**

```
┌─────────────────────────────────────────────────────────┐
│  🎓 NEW MODEL TRAINING                            [×]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Model Name:                                            │
│  ┌───────────────────────────────────────────────────┐ │
│  │ strategy_v2                                       │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Training Steps:                                        │
│  ┌───────────────────────────────────────────────────┐ │
│  │  ( ) Quick Test   - 1,000    (~2 min)   ⚠️       │ │
│  │  ( ) Minimum      - 10,000   (~15 min)           │ │
│  │  (•) Recommended  - 50,000   (~1 hour)  ⭐       │ │
│  │  ( ) Production   - 100,000  (~2 hours)          │ │
│  │  ( ) Custom       [______]                        │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ⚠️ Minimum 10,000 steps recommended for trading!      │
│                                                         │
│  📊 Data Split:                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │  Training (70%):  2024-01-01 to 2024-09-15       │ │
│  │                   49,702 candles                  │ │
│  │                                                   │ │
│  │  Testing (30%):   2024-09-16 to 2024-12-31       │ │
│  │                   21,301 candles                  │ │
│  │                                                   │ │
│  │  ✅ Out-of-Sample Testing Enabled                │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  Advanced Options:  [▼ Show]                           │
│  ┌───────────────────────────────────────────────────┐ │
│  │  Learning Rate:   [0.0003]                        │ │
│  │  N Steps:         [64]                            │ │
│  │  Batch Size:      [32]                            │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  ⏱️ Estimated Duration: ~60 minutes                    │
│                                                         │
│  [Cancel]                         [Start Training]    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔨 Implementierungs-Schritte

### **Phase 1: Backend Foundation** (Kritisch!)

1. **Model Metadaten System** (`src/model_metadata.py`)
   - Klasse: `ModelMetadata`
   - Methoden: `save()`, `load()`, `validate()`
   - Auto-generierung beim Training

2. **Train/Test Split Logic** (`src/env.py` erweitern)
   - Methode: `get_train_test_split(split_ratio=0.7)`
   - Returns: `(train_df, test_df)`
   - Zeitbasiert (nicht random!)

3. **Training Worker** (`src/train_worker.py`)
   - CLI-Script für Background Training
   - Args: `--name`, `--steps`, `--split`, etc.
   - Output: JSON Progress via stdout
   - Speichert: Model + Metadata

4. **Training Manager** (`src/training_manager.py`)
   - Spawnt Training Worker als subprocess
   - Monitort stdout für Progress
   - Broadcasts via WebSocket
   - Cleanup bei Errors

5. **ML API Router** (`charts/routes/ml_operations.py`)
   - FastAPI Router mit allen Endpoints
   - Integration mit Training Manager
   - Model Loading/Unloading
   - Error Handling

### **Phase 2: Frontend UI**

6. **Model Manager Component** (`static/js/model-manager.js`)
   - Collapsible Panel (rechts oder links)
   - Model Dropdown mit Metadaten
   - Action Buttons
   - WebSocket Listener

7. **Training Dialog** (`static/js/training-dialog.js`)
   - Modal Dialog für New Training
   - Form Validation
   - Submit via API

8. **Progress Component** (`static/js/training-progress.js`)
   - Live Progress Bar
   - ETA Calculation
   - Stop/Pause Buttons

9. **Styling** (`static/css/model-manager.css`)
   - Dark Theme
   - Responsive
   - Animations

### **Phase 3: Integration**

10. **Chart Template Update** (`templates/chart.html`)
    - Include JS/CSS Files
    - Add Model Manager Container

11. **Server Integration** (`charts/chart_server.py`)
    - Register ML Router
    - Initialize Training Manager
    - Hot-Reload für Models

### **Phase 4: Testing & Polish**

12. **Testing**
    - Unit Tests für Metadaten
    - Integration Tests für API
    - Manual UI Testing

13. **Documentation**
    - User Guide
    - API Docs
    - Troubleshooting

---

## 🚨 Kritische Punkte

### **1. Overfitting Prevention**

**MUST HAVE:**
- ✅ Train/Test Split (NIEMALS auf Test trainieren!)
- ✅ Overfitting Score anzeigen
- ✅ Warnung wenn Test << Train

### **2. Process Management**

**MUST HAVE:**
- ✅ Training läuft in separatem Prozess (blockiert UI nicht)
- ✅ Graceful Shutdown bei Errors
- ✅ Cleanup von abgebrochenen Jobs

### **3. Data Consistency**

**MUST HAVE:**
- ✅ Env-Config in Metadaten speichern (für Continue Learning!)
- ✅ Validate Config beim Laden
- ✅ Crash-Prevention bei inkompatiblen Models

### **4. User Feedback**

**MUST HAVE:**
- ✅ Live Progress Updates (nicht blockieren!)
- ✅ Clear Error Messages
- ✅ Overfitting Warnings

---

## 📈 Success Metrics

**Nach Implementierung sollte User können:**

1. ✅ Neues Model in 3 Klicks trainieren
2. ✅ Training Progress live sehen
3. ✅ Train vs Test Performance vergleichen
4. ✅ Overfitting sofort erkennen
5. ✅ Models ohne Server-Restart wechseln
6. ✅ Continue Training auf existierendem Model

---

## 🔄 Erweiterungen (Later)

1. **Walk-Forward Testing** (Strategie 2)
   - 4 Trainings-Rounds statt 1
   - Average Performance

2. **Hyperparameter Tuning**
   - Automatic Grid Search
   - Best Model Selection

3. **Model Comparison View**
   - Side-by-Side Metrics
   - Equity Curve Overlay

4. **TensorBoard Integration**
   - Live Loss/Reward Graphs
   - Link im UI

5. **Cloud Training**
   - Offload zu GPU Server
   - Faster Training

---

## 🛠️ Code Snippets (Referenz)

### **Model Metadata Class**

```python
# src/model_metadata.py
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class TrainingConfig:
    total_steps: int
    learning_rate: float
    n_steps: int
    batch_size: int

@dataclass
class DataSplit:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_candles: int
    test_candles: int

@dataclass
class Performance:
    final_balance: float
    initial_balance: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    max_drawdown: float

class ModelMetadata:
    def __init__(
        self,
        model_name: str,
        training_config: TrainingConfig,
        data_split: DataSplit,
        train_performance: Performance,
        test_performance: Optional[Performance] = None,
        env_config: Optional[Dict[str, Any]] = None
    ):
        self.model_name = model_name
        self.created_at = datetime.now().isoformat()
        self.training_config = training_config
        self.data_split = data_split
        self.train_performance = train_performance
        self.test_performance = test_performance
        self.env_config = env_config or {}
        self.version = "1.0"

        # Calculate overfitting score
        self.overfitting_score = self._calculate_overfitting()

    def _calculate_overfitting(self) -> Optional[float]:
        if not self.test_performance:
            return None

        train_return = self.train_performance.total_return
        test_return = self.test_performance.total_return

        if train_return <= 0:
            return None

        return (train_return - test_return) / train_return

    def save(self, models_dir: Path = Path("models")):
        """Save metadata to JSON file"""
        filepath = models_dir / f"{self.model_name}.metadata.json"

        data = {
            "model_name": self.model_name,
            "created_at": self.created_at,
            "training_config": asdict(self.training_config),
            "data_split": asdict(self.data_split),
            "train_performance": asdict(self.train_performance),
            "test_performance": asdict(self.test_performance) if self.test_performance else None,
            "overfitting_score": self.overfitting_score,
            "env_config": self.env_config,
            "version": self.version
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return filepath

    @classmethod
    def load(cls, model_name: str, models_dir: Path = Path("models")) -> 'ModelMetadata':
        """Load metadata from JSON file"""
        filepath = models_dir / f"{model_name}.metadata.json"

        with open(filepath, 'r') as f:
            data = json.load(f)

        return cls(
            model_name=data['model_name'],
            training_config=TrainingConfig(**data['training_config']),
            data_split=DataSplit(**data['data_split']),
            train_performance=Performance(**data['train_performance']),
            test_performance=Performance(**data['test_performance']) if data['test_performance'] else None,
            env_config=data.get('env_config', {})
        )
```

---

## ✅ Resumption Checklist

**Nach Unterbrechung - starte hier:**

1. [ ] Lies diese Doku komplett
2. [ ] Check Todo-Liste (`TodoWrite`)
3. [ ] Wo war ich? → Suche "in_progress" in Todos
4. [ ] Code Review: Was ist schon implementiert?
5. [ ] Continue mit nächstem Step aus Phase-Plan

**Quick Status Check Commands:**
```bash
# Welche Models existieren?
dir models\*.zip

# Welche Metadaten existieren?
dir models\*.metadata.json

# Welche Routen sind registriert?
grep -r "ml_operations" charts/

# Welche JS Files existieren?
dir static\js\model*.js
```

---

**END OF DOCUMENT**
