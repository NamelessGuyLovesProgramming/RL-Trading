# RL Trading Chart Server 2.0

**Professional Trading Chart Server** mit Clean Architecture, FastAPI Backend und TradingView Lightweight Charts Integration.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-78%2F78-brightgreen.svg)](./tests/)
[![Coverage](https://img.shields.io/badge/coverage-80%25%2B-brightgreen.svg)]()

---

## 🚀 Quick Start

### Installation

```bash
# Clone Repository
git clone <repository-url>
cd RL-Trading

# Install Dependencies
pip install -r requirements.txt
```

### Start Server

```bash
# Start Chart Server
py charts/chart_server.py

# Server runs on http://localhost:8003
```

### Run Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# With coverage
pytest tests/ --cov=charts --cov-report=html
```

---

## 🏗️ Architecture

### Clean Architecture mit Layered Design

```
┌─────────────────────────────────────┐
│         Routes (API Layer)          │
│   WebSocket, HTTP Endpoints         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Services (Business Logic)      │
│  Chart, Navigation, Timeframe, etc. │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Repositories (Data Access)      │
│      CSV, Cache, State              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        Core (Domain Layer)          │
│  State, Validation, Time Management │
└─────────────────────────────────────┘
```

### Key Components

- **Routes Layer**: FastAPI endpoints for HTTP and WebSocket
- **Services Layer**: Business logic (ChartService, TimeframeService, NavigationService, DebugService, PositionService)
- **Repositories Layer**: Data access abstraction (CSV, Cache, State)
- **Core Layer**: Domain models and validation
- **Models Layer**: Data classes and domain objects

---

## 📁 Project Structure

```
RL-Trading/
├── charts/                     # Chart Server Application
│   ├── chart_server.py        # FastAPI Entry Point (~395 LOC)
│   │
│   ├── core/                  # Domain Layer
│   │   ├── state_manager.py
│   │   ├── chart_validator.py
│   │   ├── price_repository.py
│   │   ├── websocket_manager.py
│   │   ├── data_loader.py
│   │   ├── timeframe_*.py
│   │   ├── skip_renderer.py
│   │   ├── transaction.py
│   │   ├── cache_manager.py
│   │   ├── series_manager.py
│   │   └── debug_controller.py
│   │
│   ├── services/              # Business Logic Layer
│   │   ├── chart_service.py
│   │   ├── timeframe_service.py
│   │   ├── navigation_service.py
│   │   ├── debug_service.py
│   │   └── position_service.py
│   │
│   ├── routes/                # API/WebSocket Routes
│   │   ├── websocket_handler.py
│   │   ├── chart.py
│   │   ├── debug.py
│   │   └── static.py
│   │
│   ├── models/                # Domain Models
│   │   ├── chart_data.py
│   │   ├── skip_event.py
│   │   ├── position.py
│   │   └── timeframe.py
│   │
│   ├── repositories/          # Data Access Layer
│   │   ├── csv_repository.py
│   │   ├── cache_repository.py
│   │   └── state_repository.py
│   │
│   ├── config/                # Configuration
│   │   ├── settings.py
│   │   └── constants.py
│   │
│   └── utils/                 # Utilities
│       ├── serializers.py
│       └── validators.py
│
├── tests/                     # Test Suite (Unified)
│   ├── unit/                  # Unit Tests (80%)
│   │   ├── test_core/        # 78 tests
│   │   ├── test_services/
│   │   ├── test_models/
│   │   └── test_repositories/
│   │
│   └── integration/           # Integration Tests (20%)
│       ├── test_chart_server_integration.py
│       ├── test_data_loading.py
│       └── test_skip_event_persistence.py
│
├── templates/                 # HTML Templates
│   └── chart.html            # TradingView Chart Page
│
├── requirements.txt           # Dependencies
├── pytest.ini                # pytest Configuration
└── README.md                 # This file
```

---

## 🎯 Key Features

### 📊 Real-Time Trading Charts
- TradingView Lightweight Charts integration
- Multi-timeframe support (1m, 2m, 3m, 5m, 15m, 30m, 1h, 4h)
- WebSocket real-time updates
- Responsive and smooth performance

### 🐛 Debug Mode
- Historical data simulation
- Time travel (Go to Date)
- Skip forward through candles
- Speed control (1x-15x)
- Auto-play mode

### 📈 Trading Features
- Short/Long position visualization
- Entry, Stop-Loss, Take-Profit markers
- Position management
- Real-time P&L calculation

### ⚡ Performance Optimizations
- **Timeframe-Switch Preloading**: Adjacent timeframes are preloaded in background
- **Smart Cache Invalidation**: Only invalidates cache when necessary
- **Memory-based caching**: Sub-millisecond data access
- **Async WebSocket handling**: Non-blocking real-time updates

### 🧪 Comprehensive Testing
- 78+ unit tests (100% passing)
- 27+ integration tests
- >80% code coverage
- Pytest-based test suite

---

## 🔧 API Reference

### FastAPI Documentation

Visit `http://localhost:8003/docs` for interactive API documentation (Swagger UI).

### WebSocket Commands

#### Get Chart Data
```json
{
  "type": "get_chart_data",
  "timeframe": "5m",
  "visible_candles": 200
}
```

#### Change Timeframe
```json
{
  "type": "timeframe_change",
  "timeframe": "15m",
  "visible_candles": 200
}
```

#### Go To Date
```json
{
  "type": "go_to_date",
  "date": "2024-12-17",
  "timeframe": "5m"
}
```

#### Skip Forward
```json
{
  "type": "skip",
  "timeframe": "5m"
}
```

### HTTP Endpoints

- `GET /` - Chart HTML page
- `GET /api/chart/status` - Server status
- `GET /api/chart/data` - Current chart data
- `POST /api/chart/change_timeframe` - Change timeframe
- `POST /api/debug/skip` - Skip forward
- `POST /api/debug/go_to_date` - Go to date
- `POST /api/debug/set_speed` - Set debug speed
- `POST /api/debug/toggle_play` - Toggle auto-play

See full API documentation at `/docs`.

---

## 🎨 Design Patterns

### 1. Dependency Injection
```python
class ChartService:
    def __init__(self,
                 price_repo: UnifiedPriceRepository,
                 cache_repo: CacheRepository,
                 validator: ChartDataValidator):
        self.price_repo = price_repo
        self.cache_repo = cache_repo
        self.validator = validator
```

### 2. Repository Pattern
```python
class CSVRepository:
    def get_candles_by_date(self, symbol, timeframe, date): ...
    def get_candles_range(self, symbol, timeframe, start, end): ...
```

### 3. Service Layer Pattern
```python
class NavigationService:
    def go_to_date(self, date): ...
    def skip_forward(self, count): ...
    def next_candle(self): ...
```

### 4. Factory Pattern
```python
class CandleFactory:
    @staticmethod
    def from_csv_row(row): ...
    @staticmethod
    def from_dict(data): ...
```

---

## 📊 Performance Metrics

| Metric | Before Refactor | After Refactor | Improvement |
|--------|----------------|----------------|-------------|
| LOC (chart_server.py) | 7,354 | 395 | **95% reduction** |
| Test Coverage | ~40% | >80% | **+40%** |
| Unit Tests | 15 | 78 | **5x more** |
| Timeframe Switch | >1s | <500ms | **50% faster** |
| Go To Date | >2s | <1s | **50% faster** |
| Skip Operation | >500ms | <200ms | **60% faster** |

---

## 🛠️ Development

### Configuration

Environment variables can be set in `.env`:

```bash
# Server
HOST=0.0.0.0
PORT=8003

# Data
DATA_PATH=src/data/aggregated
DEFAULT_SYMBOL=NQ=F
DEFAULT_TIMEFRAME=5m

# Cache
CACHE_SIZE_MB=100
ENABLE_CACHE=true

# Debug
DEBUG_MODE=false
```

### Running Tests

```bash
# All tests with verbose output
pytest tests/ -v

# Specific test file
pytest tests/unit/test_core/test_skip_renderer.py -v

# With coverage report
pytest tests/ --cov=charts --cov-report=html
open htmlcov/index.html

# Integration tests only
pytest tests/integration/ -v
```

### Code Quality

```bash
# Format code with black
black charts/ tests/

# Lint with flake8
flake8 charts/ tests/

# Type checking (optional)
mypy charts/
```

---

## 🔄 Migration from v1.0

The system has been completely refactored from a monolithic 7,354 LOC file to a clean, modular architecture:

**Key Changes:**
- ✅ Streamlit app removed (replaced with FastAPI + HTML/JS)
- ✅ Clean Architecture implemented
- ✅ Dependency Injection throughout
- ✅ Comprehensive test suite (78+ unit tests)
- ✅ Performance optimizations
- ✅ Repository Pattern for data access
- ✅ Service Layer for business logic

See [CHANGELOG.md](./CHANGELOG.md) for detailed migration notes.

---

## 📚 Additional Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed architecture documentation
- [API.md](./API.md) - Complete API reference
- [REFACTOR_PLAN_OPTION2.md](./REFACTOR_PLAN_OPTION2.md) - Refactoring plan and progress

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Make sure all tests pass (`pytest tests/ -v`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## ⚠️ Disclaimers

- **No Financial Advice**: This is a research and learning project
- **Paper Trading Only**: Never use real money without extensive testing
- **Risk Management**: Always implement proper risk controls in any trading system

---

## 🎯 Roadmap

- [x] Clean Architecture refactor
- [x] Comprehensive test suite
- [x] Performance optimizations
- [x] Documentation
- [ ] Advanced analytics dashboard
- [ ] Multi-symbol support
- [ ] Backtesting engine
- [ ] Strategy builder UI
- [ ] Svelte frontend (optional)

---

**Built with ❤️ using FastAPI, TradingView Charts, and Clean Architecture principles**

*For legacy RL Trading System documentation, see [LEGACY_README.md](./LEGACY_README.md)*
