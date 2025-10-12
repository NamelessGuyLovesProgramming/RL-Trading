# RL Trading - Reinforcement Learning Trading System

Professional trading system combining RL agent training with a real-time chart server.

## 🚀 Quick Start

### Chart Server (Port 8003)
```bash
./run_tests_and_start.bat
```
Browser: http://localhost:8003

### Tests
```bash
./run_tests.bat          # Interactive menu
./run_tests.bat all      # All tests
./run_tests.bat coverage # Coverage report
```

## 📁 Project Structure

```
RL-Trading/
├── src/              # RL Training Core (Agent, Environment, Rewards)
├── charts/           # Chart Server (Clean Architecture)
├── tests/            # Chart Server Test Suite
├── static/           # Web Assets (CSS, JS)
├── templates/        # HTML Templates
├── models/           # Trained RL Models
├── logs/             # Training & Server Logs
├── scripts/          # Utility Scripts
└── docs/             # 📚 Complete Documentation
```

## 📚 Documentation

**Full documentation available in [`docs/`](docs/):**

- **[docs/README.md](docs/README.md)** - Complete project documentation
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture & design patterns
- **[docs/API.md](docs/API.md)** - Chart Server API reference
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Release notes & version history
- **[docs/BUGFIX_DOCUMENTATION.md](docs/BUGFIX_DOCUMENTATION.md)** - Bug fixes & solutions
- **[docs/refactor_plan_option2.md](docs/refactor_plan_option2.md)** - Refactoring roadmap

## 🏗️ Architecture

### Chart Server (Clean Architecture)
- **Routes** → **Services** → **Repositories** → **Core**
- Dependency Injection, Repository Pattern, Service Layer Pattern
- 78 Unit Tests (100% passing), 27 Integration Tests (96% passing)
- FastAPI + WebSocket + TradingView Lightweight Charts

### RL Training
- PPO Agent with custom trading environment
- Reward shaping for profitable trading strategies
- TensorBoard integration for training monitoring

## 🧪 Testing

```bash
./run_tests.bat                  # Interactive menu
./run_tests.bat unit             # Unit tests only
./run_tests.bat integration      # Integration tests only
./run_tests.bat coverage         # Coverage report (opens in browser)
```

## 📦 Requirements

```bash
pip install -r requirements.txt
```

## 🎯 Key Features

- Real-time chart visualization with TradingView
- Multi-timeframe support (1m, 2m, 3m, 5m, 15m, 30m, 1h, 4h)
- Debug mode with playback controls
- Short position tool with SL/TP
- RL agent training & backtesting
- Performance-optimized caching
- Template modularization (95.9% token reduction)

## 📊 Performance Metrics

| Feature | Performance |
|---------|------------|
| Timeframe Switch | < 500ms |
| Go-To-Date (First Use) | < 1s |
| Skip Forward (First Use) | < 200ms |
| Test Coverage | > 80% |

---

**Built with Clean Architecture principles** | **Maintained with Best Practices**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
