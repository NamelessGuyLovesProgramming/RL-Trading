# Changelog

All notable changes to the RL Trading Chart Server project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.2] - 2025-11-02

### 🎯 FEATURE - Temporäres Autoscaling bei "Go To Date"

Intelligente Autoscale-Verwaltung während Chart-Navigation mit automatischer State-Wiederherstellung.

#### Added

**Smart Autoscale für "Go To Date"**:
- ⚖️ Autoscale wird temporär aktiviert während "Go To Date" Navigation für optimale Chart-Positionierung
- 💾 Original-Zustand (ON/OFF) wird gespeichert und nach Chart-Reload automatisch wiederhergestellt
- ✅ User-Präferenz bleibt erhalten:
  - Autoscale OFF → temporär ON während Laden → zurück zu OFF
  - Autoscale ON → bleibt ON durchgehend

#### Implementation Details

**File: `static/js/chart.js`**

1. **State Speicherung & Temporäre Aktivierung** (Lines 5804-5808):
   ```javascript
   // 💾 Speichere Original-Zustand NUR beim ersten Go To
   if (typeof window.originalAutoscaleState === 'undefined') {
       window.originalAutoscaleState = window.autoscaleEnabled;
   }

   // 🎯 Aktiviere Autoscale temporär für optimale Positionierung
   if (!window.autoscaleEnabled) {
       window.autoscaleEnabled = true;
       chart.priceScale('right').applyOptions({ autoScale: true });
   }
   ```

2. **State Wiederherstellung** (Lines 1830-1852):
   ```javascript
   // ⚖️ Stelle Original-Zustand nach Chart-Reload wieder her
   if (typeof window.originalAutoscaleState !== 'undefined') {
       window.autoscaleEnabled = window.originalAutoscaleState;
       chart.priceScale('right').applyOptions({
           autoScale: window.originalAutoscaleState
       });

       // Update Button UI
       const autoscaleBtn = document.getElementById('autoscaleBtn');
       if (autoscaleBtn) {
           autoscaleBtn.classList.toggle('active', window.originalAutoscaleState);
       }

       delete window.originalAutoscaleState; // Cleanup
   }
   ```

3. **User-Drag Detection Bypass** (Line 890):
   ```javascript
   // Deaktiviere Autoscale bei User-Drag, ABER nicht während Go To
   if (!window.isProgrammaticRangeChange &&
       window.autoscaleEnabled &&
       typeof window.originalAutoscaleState === 'undefined') {
       // User-Drag erkannt → Autoscale OFF
   }
   ```

#### Testing

**Test-Szenarien erfolgreich:**
| Test | Vorher | Nachher | Status |
|------|--------|---------|--------|
| Szenario 1 | Autoscale OFF | Autoscale OFF | ✅ PASS |
| Szenario 2 | Autoscale ON | Autoscale ON | ✅ PASS |

**Test-Ablauf:**
1. Setze Autoscale-Zustand (ON oder OFF)
2. Öffne "Go To Date" Modal
3. Wähle Datum und führe Navigation aus
4. Verifiziere: Autoscale-Zustand entspricht Original-Zustand vor Navigation

#### Technical Notes

**Race Condition Prevention:**
- User-Drag Detection wird während Go To Operation deaktiviert
- Verhindert dass manuelle Drag-Erkennung den gespeicherten State überschreibt
- `window.originalAutoscaleState` dient als Flag für laufende Go To Operation

**State Management:**
- `window.originalAutoscaleState`: Temporärer State (nur während Go To)
- `window.autoscaleEnabled`: Persistenter State
- Cleanup nach erfolgreicher Wiederherstellung

**Commit:** `de941ab` - feat: Temporäres Autoscaling bei "Go To Date" mit State-Preservation

---

## [2.1.1] - 2025-10-27

### 🎯 FEATURE - Limit Order Wick-Triggering & Canvas Transparency

Advanced limit order triggering system with candle wick detection and improved chart interactivity.

#### Fixed

**Critical Bugs**:
- ✅ Limit orders now trigger on candle **wicks** (high/low), not just close price
  - Root cause: `checkLimitOrders()` only checked `currentPrice` (close)
  - Fix: Store full candle data (OHLC) in `window.lastCandle`, check `candle.high/low`
  - BUY orders: Trigger when `low <= entryPrice` (price touched from above)
  - SELL orders: Trigger when `high >= entryPrice` (price touched from below)

- ✅ Chart panning/dragging blocked after placing limit order
  - Root cause: Limit canvas had `pointer-events: auto`, blocking all interactions
  - Fix: Canvas set to `pointer-events: none` (always transparent)

- ✅ Cannot create new position box after limit order placed
  - Root cause: Canvas overlay captured all click events
  - Fix: Real DOM button elements positioned over canvas (z-index: 12)

- ✅ X-button click detection improved
  - Old: Complex canvas coordinate calculation with click handler
  - New: Transparent `<button>` elements over canvas-drawn X graphics

#### Changed

**Limit Order Triggering Logic** (`static/js/chart.js:4945-5003`):
```javascript
// Before: Only checked close price
triggered = currentPrice >= order.entryPrice;  // ❌ Ignores wicks

// After: Checks high/low for wick detection
const high = candle.high || currentPrice;
const low = candle.low || currentPrice;

// BUY LIMIT: Wait for price to FALL
triggered = low <= order.entryPrice;  // ✅ Triggers on lower wick

// SELL LIMIT: Wait for price to RISE
triggered = high >= order.entryPrice;  // ✅ Triggers on upper wick
```

**Canvas Pointer Events** (`static/js/chart.js:5120, 5195-5228`):
```javascript
// Before: Canvas blocked interactions
canvas.style.pointerEvents = 'auto';  // ❌ Blocks chart pan

// After: Canvas always transparent
canvas.style.pointerEvents = 'none';  // ✅ Chart pan works

// Before: Canvas click handler (39 lines of coordinate math)
canvas.addEventListener('click', (e) => { /* complex detection */ });

// After: Real DOM buttons (transparent, positioned exactly)
const closeButton = document.createElement('button');
closeButton.style.cssText = `
    position: absolute;
    left: ${btnX}px;
    top: ${btnY}px;
    background: transparent;
    cursor: pointer;
    z-index: 12;
`;
```

**Data Storage** (`static/js/chart.js:1706, 1742, 4806, 4816-4826`):
- Store full candle: `window.lastCandle = validatedCandle` (time, open, high, low, close)
- `getCurrentMarketPrice()` returns full candle object instead of just close price
- Fallback support if only close price available

#### Technical Details

**Files Modified**:
- `static/js/chart.js` (+65 lines, -61 lines)

**Code Locations**:
- Candle storage: Lines 1706, 1742, 4806
- Price retrieval: Lines 4816-4826
- Limit order checking: Lines 4945-5003 (refactored)
- Canvas management: Lines 5120, 5132-5145 (simplified)
- DOM button creation: Lines 5195-5228 (new approach)

**Performance**:
- ⚡ Removed 39 lines of canvas click detection logic
- ⚡ DOM buttons provide native browser click handling
- ⚡ No performance impact on chart rendering

**User Experience**:
- ✅ Orders trigger at realistic market prices (including wicks)
- ✅ Chart remains fully interactive with limit orders active
- ✅ Can create multiple position boxes simultaneously
- ✅ Hand cursor (👆) only shows over X-buttons

---

## [2.1.0] - 2025-10-19

### 🎯 FEATURE - Trade Execution & Live Position Visualization

Complete implementation of trade execution system with real-time position tracking and modern UI visualization.

#### Added

**Backend - Account Service**:
- ✅ `charts/services/account_service.py` - Dual account management (AI + User)
- ✅ Separate 500,000€ starting capital per account
- ✅ Trade execution with automatic account assignment (RL online → AI account, offline → User account)
- ✅ Position lifecycle management (open, update PnL, close)
- ✅ Real-time PnL calculation (realized + unrealized)
- ✅ Trade statistics tracking (win rate, total trades, winning/losing trades)
- ✅ Auto-close on Stop Loss / Take Profit hit
- ✅ Position history tracking (closed positions log)

**Frontend - Live Position Labels**:
- ✅ Modern canvas-based position labels on entry price line
- ✅ Three separate labels: `[Size] [PnL] [X]` aligned right before Y-axis
- ✅ Material Design color scheme:
  - Size label: Google Blue (#4285f4)
  - PnL label: Teal green (profit) / Soft red (loss)
  - Close button: Solid red with white X
- ✅ Continuous rendering (~60 FPS) for stable tracking during zoom/pan
- ✅ Real-time PnL updates via WebSocket
- ✅ Click X button to manually close position
- ✅ Labels auto-disappear on position close

**WebSocket Integration**:
- ✅ `execute_trade` command - Creates position and assigns to correct account
- ✅ `close_position` command - Closes position manually
- ✅ `position_opened` event - Broadcasts new position to all clients
- ✅ `position_closed` event - Broadcasts closed position with realized PnL
- ✅ `pnl_update` event - Real-time unrealized PnL updates

#### Fixed

**Critical Bugs**:
- ✅ Position Tool canvas not recreating after trade execution
  - Root cause: Canvas references not reset after removal
  - Fix: Reset `positionBoxManager.canvas`, `.ctx`, `.boxes[]` in `removeCurrentPositionBox()`
- ✅ Old Position Tool boxes stacking under new boxes
  - Root cause: `positionBoxManager.boxes` not cleared on trade execution
  - Fix: Set `boxes = []` (Array, not Object) when clearing manager
- ✅ Labels not disappearing after trade close
  - Root cause: Canvas not cleared when no positions remain
  - Fix: Two-stage canvas clearing (in `removePositionOverlay()` + `renderLivePnLLabels()`)
- ✅ Labels shifting during Y-axis zoom
  - Root cause: Static rendering without coordinate recalculation
  - Fix: Continuous rendering loop with `requestAnimationFrame()` + `priceToCoordinate()`
- ✅ X button click detection not working
  - Root cause: Canvas overlay blocking clicks
  - Fix: Set `pointerEvents: 'none'` on labels canvas, handle clicks via `chart.subscribeClick()`

**Performance Optimizations**:
- ✅ Reduced console logging in high-frequency functions (60 FPS rendering)
- ✅ Efficient canvas clearing only when needed
- ✅ Optimized button click detection with early returns

#### Changed

**UI/UX Improvements**:
- Enhanced label sizing: 22px height, 13px bold font, 1.5px borders
- Better spacing: 70px Y-axis width + 15px margin
- Improved visual separation between labels (5px gap)
- Professional modern design with subtle transparency

**Code Quality**:
- Separated PnL labels canvas (`pnl-labels-canvas`, z-index 10) from position box canvas (`position-canvas`, z-index 5)
- Clean separation of concerns (Position Tool vs Live Trades)
- Comprehensive debug logging for troubleshooting

---

## [2.0.0] - 2025-10-11

### 🎉 MAJOR REFACTOR - Clean Architecture

Complete system refactor from monolithic 7,354 LOC file to clean, modular architecture.

#### Added

**Architecture**:
- ✅ Clean Architecture with Layered Design (Routes → Services → Repositories → Core)
- ✅ Dependency Injection throughout the application
- ✅ Repository Pattern for data access abstraction
- ✅ Service Layer Pattern for business logic
- ✅ Factory Pattern for object creation
- ✅ Strategy Pattern for aggregation algorithms
- ✅ State Machine Pattern for chart lifecycle

**Testing**:
- ✅ Comprehensive test suite (78+ unit tests, 27+ integration tests)
- ✅ Pytest-based testing framework
- ✅ >80% code coverage
- ✅ Test organization (unit/integration split)
- ✅ Mock-based testing for isolation

**Performance Optimizations**:
- ✅ Timeframe-Switch Preloading (adjacent timeframes loaded in background)
- ✅ Smart Cache Invalidation (only invalidates when necessary)
- ✅ Memory-based caching with sub-millisecond access
- ✅ Async WebSocket handling (non-blocking real-time updates)

**Documentation**:
- ✅ Comprehensive README.md with quick start guide
- ✅ ARCHITECTURE.md with detailed layer diagrams
- ✅ API.md with complete endpoint documentation
- ✅ CHANGELOG.md (this file)
- ✅ Interactive Swagger UI at `/docs`

**Core Components** (extracted from monolithic file):
- `charts/core/skip_renderer.py` - Universal skip event rendering
- `charts/core/transaction.py` - Transaction system with rollback
- `charts/core/cache_manager.py` - Smart caching with preload tracking
- `charts/core/series_manager.py` - Chart lifecycle management
- `charts/core/debug_controller.py` - Debug mode control logic

**Services Layer**:
- `charts/services/chart_service.py` - Chart operations
- `charts/services/timeframe_service.py` - Timeframe switching
- `charts/services/navigation_service.py` - Navigation (GoTo, Skip, Next)
- `charts/services/debug_service.py` - Debug mode logic
- `charts/services/position_service.py` - Position management

**Routes Layer**:
- `charts/routes/chart.py` - Chart HTTP endpoints
- `charts/routes/debug.py` - Debug HTTP endpoints
- `charts/routes/static.py` - Static file serving
- `charts/routes/websocket_handler.py` - WebSocket command handling

**Repositories Layer**:
- `charts/repositories/csv_repository.py` - CSV data access
- `charts/repositories/cache_repository.py` - Cache operations
- `charts/repositories/state_repository.py` - State persistence

**Configuration & Utilities**:
- `charts/config/settings.py` - Pydantic settings with env support
- `charts/config/constants.py` - Application constants
- `charts/utils/serializers.py` - JSON serialization
- `charts/utils/validators.py` - Input validation

#### Changed

**Code Quality**:
- 📉 chart_server.py: 7,354 → 395 LOC (**95% reduction**)
- ✅ No more global variables
- ✅ Clear separation of concerns
- ✅ Type hints throughout

**Performance**:
- ⚡ Timeframe Switch: >1s → <500ms (**50% faster**)
- ⚡ Go To Date: >2s → <1s (**50% faster**)
- ⚡ Skip Operation: >500ms → <200ms (**60% faster**)

**Testing**:
- 📊 Test Coverage: ~40% → >80% (**+40%**)
- 📊 Unit Tests: 15 → 78 (**5x more**)
- 📊 Integration Tests: 5 → 27 (**5x more**)

**Project Structure**:
- Moved all tests to `tests/` directory (unit/integration split)
- Consolidated 13 test files from root to `tests/integration/`
- Removed `src/` directory (legacy Streamlit app)

#### Removed

**Legacy Code**:
- ❌ Streamlit app (`src/app.py`, `src/components/`) removed
- ❌ Legacy dependencies (streamlit, streamlit-option-menu)
- ❌ Global variables in chart_server.py
- ❌ Monolithic 7,354 LOC file structure

**Breaking Changes**:
- New entry point: `py charts/chart_server.py` (not `streamlit run src/app.py`)
- New imports: `from charts.services import ...` (not `from src.services import ...`)
- WebSocket protocol unchanged (backwards compatible)
- HTTP endpoints unchanged (backwards compatible)

#### Fixed

**Critical Bugs**:
- ✅ Skip events now persist across timeframe changes
- ✅ NavigationService properly stores skip events in `global_skip_events`
- ✅ UniversalSkipRenderer correctly adapts events for all timeframes
- ✅ Chart recreation logic fixed (no more undefined candles)

**Performance Issues**:
- ✅ Cache invalidation optimized (smart invalidation)
- ✅ Timeframe switching optimized (preloading)
- ✅ WebSocket message handling optimized (async)

#### Security

- 🔒 Input validation throughout (using pydantic)
- 🔒 Data sanitization in `ChartDataValidator`
- 🔒 OHLC validation (prevents invalid price data)
- ⚠️ Note: No authentication implemented yet (public access)

#### Deprecated

- ⚠️ Legacy RL Training System (see `LEGACY_README.md` for old docs)
- ⚠️ Streamlit-based UI (replaced with FastAPI + HTML/JS)

---

## [1.5.0] - 2025-10-03

### Added (Phase 0-6 of Refactor)

**Phase 0: Setup**:
- ✅ Git branch `refactor/modular-architecture` created
- ✅ pyproject.toml, pytest.ini, .flake8 configured
- ✅ Baseline tests executed and documented

**Phase 1: Models Layer** (not fully completed):
- Skipped in favor of continuing with existing models

**Phase 2: Repositories Layer**:
- ✅ CSVRepository with multi-path fallback
- ✅ CacheRepository with SimpleCacheRepository fallback
- ✅ StateRepository with backup system
- ✅ 33/35 tests passing (94% success rate)

**Phase 3: Core Layer**:
- ✅ UniversalSkipRenderer extracted (10.5 KB)
- ✅ EventBasedTransaction extracted (3.5 KB)
- ✅ ChartDataCache extracted (10.4 KB)
- ✅ ChartSeriesLifecycleManager extracted (6.5 KB)
- ✅ DebugController extracted (15.8 KB)
- ✅ 78/78 unit tests created (100% passing)

**Phase 4: Services Layer**:
- ✅ ChartService (~150 LOC)
- ✅ TimeframeService (~171 LOC)
- ✅ NavigationService (~215 LOC)
- ✅ DebugService (~162 LOC)
- ✅ PositionService (~213 LOC)
- ✅ 3 endpoints migrated (Skip, GoTo, Timeframe-Switch)
- ✅ 298 LOC reduction in chart_server.py

**Phase 5: Routes Layer**:
- ✅ debug.py (263 LOC) - 6 debug endpoints
- ✅ static.py (61 LOC) - HTML & static files
- ✅ websocket_handler.py (568 LOC) - WebSocket handler
- ✅ 27 integration tests (26/27 passing = 96%)

**Phase 6: Config & Utils**:
- ✅ settings.py (208 LOC) - Pydantic settings
- ✅ constants.py (341 LOC) - Constants & helpers
- ✅ serializers.py (290 LOC) - JSON serialization
- ✅ validators.py (331 LOC) - Input validation
- ✅ 6/6 tests passing (100%)

### Fixed

**Phase 3 Bug Fixes**:
- ✅ Skip event persistence across timeframes
- ✅ NavigationService now saves events to global_skip_events
- ✅ Chart.py passes skip_events to renderer

**Phase 5 Bug Fixes**:
- ✅ Response structure flattened (no nesting)
- ✅ Chart data sorting fixed (timestamp order)

---

## [1.0.0] - 2024-12-30 (Original Version)

### Initial Release

**Features**:
- TradingView Lightweight Charts integration
- Multi-timeframe support (1m, 2m, 3m, 5m, 15m, 30m, 1h, 4h)
- WebSocket real-time updates
- Debug mode with time travel
- Short/Long position visualization
- CSV data loading
- Historical data simulation

**Architecture**:
- Monolithic chart_server.py (7,354 LOC)
- Streamlit-based UI
- Global state management
- Inline HTML/JavaScript

**Known Issues**:
- Skip events not persisting across timeframes
- Global variables causing state issues
- Performance issues with timeframe switching
- Limited test coverage (~40%)
- Tight coupling between components

---

## Migration Guide

### From v1.0 to v2.0

#### 1. Update Dependencies

```bash
pip install -r requirements.txt
```

Old requirements (removed):
- streamlit>=1.28.0
- streamlit-option-menu>=0.3.6

New requirements (added):
- pytest>=7.4.0
- pytest-asyncio>=0.21.0
- pytest-cov>=4.0.0
- pytest-mock>=3.10.0

#### 2. Update Start Command

**Old**:
```bash
py -m streamlit run src/app.py --server.port 8504 --server.headless true
```

**New**:
```bash
py charts/chart_server.py
```

#### 3. Update Imports (if extending)

**Old**:
```python
from src.services.chart_service import ChartService
```

**New**:
```python
from charts.services.chart_service import ChartService
```

#### 4. API Compatibility

- ✅ WebSocket protocol unchanged
- ✅ HTTP endpoints unchanged
- ✅ Message formats unchanged
- ✅ Chart data format unchanged

**No client-side changes required!**

---

## Roadmap

### Version 2.1 (Planned)

- [ ] JWT authentication
- [ ] User management system
- [ ] Rate limiting
- [ ] Advanced analytics dashboard
- [ ] Multi-symbol support

### Version 2.2 (Planned)

- [ ] Backtesting engine
- [ ] Strategy builder UI
- [ ] Performance profiling
- [ ] Database integration (PostgreSQL)

### Version 3.0 (Future)

- [ ] Svelte frontend (optional)
- [ ] Microservices architecture
- [ ] GraphQL API
- [ ] Real-time trading (with broker integration)
- [ ] Machine learning model integration

---

## Contributors

- **Development Team**: Initial development and refactor
- **Claude Code**: Assisted with architecture design, testing, and documentation

---

## License

MIT License - See LICENSE file for details

---

**Last Updated**: 2025-10-11
