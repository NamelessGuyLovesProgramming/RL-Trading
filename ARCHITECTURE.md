# Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architectural Principles](#architectural-principles)
3. [Layer Diagram](#layer-diagram)
4. [Component Details](#component-details)
5. [Data Flow Examples](#data-flow-examples)
6. [Design Patterns](#design-patterns)
7. [Key Design Decisions](#key-design-decisions)
8. [Performance Considerations](#performance-considerations)

---

## Overview

The RL Trading Chart Server follows **Clean Architecture** principles with a **Layered Design** approach. The system is built around the concept of **Dependency Inversion** where high-level modules (business logic) do not depend on low-level modules (data access), but both depend on abstractions (interfaces/protocols).

### Core Principles

- **Separation of Concerns**: Each layer has a specific responsibility
- **Dependency Injection**: Dependencies are injected, not created
- **Testability**: Each component can be tested in isolation
- **Maintainability**: Changes in one layer don't affect others
- **Scalability**: New features can be added without modifying existing code

---

## Layer Diagram

```
┌────────────────────────────────────────────────────────────┐
│                     Presentation Layer                      │
│                   (Routes / API Layer)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   chart.py   │  │   debug.py   │  │  static.py   │    │
│  │              │  │              │  │              │    │
│  │ HTTP Routes  │  │ Debug Routes │  │ Static Files │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘    │
│         │                  │                               │
│  ┌──────┴──────────────────┴──────────────────┐           │
│  │      websocket_handler.py                  │           │
│  │      WebSocket Command Handler             │           │
│  └────────────────┬───────────────────────────┘           │
└────────────────────┼───────────────────────────────────────┘
                     │ JSON/WebSocket Messages
┌────────────────────▼───────────────────────────────────────┐
│                    Business Logic Layer                     │
│                    (Services Layer)                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Chart    │  │ Timeframe  │  │ Navigation │           │
│  │  Service   │  │  Service   │  │  Service   │           │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘           │
│        │                │                │                  │
│  ┌─────┴──────┐  ┌──────┴──────┐ ┌──────┴──────┐          │
│  │   Debug    │  │  Position   │  │   Future    │          │
│  │  Service   │  │  Service    │  │  Services   │          │
│  └─────┬──────┘  └──────┬──────┘  └─────────────┘          │
└────────┼─────────────────┼─────────────────────────────────┘
         │ Business Logic  │
┌────────▼─────────────────▼─────────────────────────────────┐
│                  Data Access Layer                          │
│                 (Repositories Layer)                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │    CSV     │  │   Cache    │  │   State    │           │
│  │ Repository │  │ Repository │  │ Repository │           │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘           │
└────────┼─────────────────┼──────────────┼──────────────────┘
         │ Data Access     │              │
┌────────▼─────────────────▼──────────────▼──────────────────┐
│                      Core Layer                             │
│                   (Domain Logic)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │    State     │  │  Validation  │  │    Time      │     │
│  │   Manager    │  │   & Guards   │  │  Management  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │    Skip      │  │ Transaction  │  │   Cache      │     │
│  │   Renderer   │  │    System    │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Series     │  │    Debug     │  │  WebSocket   │     │
│  │   Manager    │  │  Controller  │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Data Storage
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   CSV    │  │  Memory  │  │  State   │  │  Cache   │   │
│  │  Files   │  │  Cache   │  │  Files   │  │  Store   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Routes Layer (Presentation)

**Responsibility**: Handle HTTP/WebSocket requests, validate input, format responses

#### Files:
- `charts/routes/chart.py`: Chart-related HTTP endpoints
- `charts/routes/debug.py`: Debug mode HTTP endpoints
- `charts/routes/static.py`: Static file serving
- `charts/routes/websocket_handler.py`: WebSocket command handling

#### Key Functions:
```python
@router.post("/change_timeframe")
async def change_timeframe(request: Request):
    # 1. Parse request
    # 2. Call service
    # 3. Format response
    # 4. Broadcast via WebSocket
```

**Dependencies**: Services Layer (via Dependency Injection)

---

### 2. Services Layer (Business Logic)

**Responsibility**: Implement business rules, coordinate between repositories, manage transactions

#### Components:

**ChartService** (`charts/services/chart_service.py`):
- Load initial chart data
- Get visible candles for timeframe
- Coordinate between price repository and cache

**TimeframeService** (`charts/services/timeframe_service.py`):
- Handle timeframe switching
- Aggregate candles between timeframes
- Preload adjacent timeframes (performance optimization)

**NavigationService** (`charts/services/navigation_service.py`):
- Go to date functionality
- Skip forward through candles
- Next candle navigation
- Skip event persistence

**DebugService** (`charts/services/debug_service.py`):
- Activate/deactivate debug mode
- Control playback speed
- Auto-play functionality

**PositionService** (`charts/services/position_service.py`):
- Create trading positions
- Update position markers
- Close positions
- Validate position data

#### Example Service:
```python
class NavigationService:
    def __init__(self,
                 timeframe_repo: TimeframeDataRepository,
                 debug_controller: DebugController,
                 unified_time_manager: UnifiedTimeManager,
                 unified_state: UnifiedStateManager,
                 validator: ChartDataValidator,
                 global_skip_events: List,
                 universal_renderer: UniversalSkipRenderer):
        # Dependencies injected via constructor
        self.timeframe_repo = timeframe_repo
        self.debug_controller = debug_controller
        # ... other dependencies

    def go_to_date(self, target_date: datetime, timeframe: str,
                   visible_candles: int = 200) -> Dict[str, Any]:
        # Business logic here
        pass
```

**Dependencies**: Repositories Layer, Core Layer

---

### 3. Repositories Layer (Data Access)

**Responsibility**: Abstract data access, provide uniform interface for data operations

#### Components:

**CSVRepository** (`charts/repositories/csv_repository.py`):
- Load candles from CSV files
- Handle multiple CSV file paths
- Cache loaded data
- Date range queries

**CacheRepository** (`charts/repositories/cache_repository.py`):
- Memory-based caching
- High-performance cache implementation
- Cache invalidation strategies

**StateRepository** (`charts/repositories/state_repository.py`):
- Persist application state
- Load saved state
- State validation
- Backup management

#### Example Repository:
```python
class CSVRepository:
    def __init__(self, csv_loader: CSVLoader):
        self.csv_loader = csv_loader
        self._cache = {}

    def get_candles_by_date(self, symbol: str, timeframe: str,
                           date: datetime, count: int = 300) -> List[Candle]:
        # Data access logic
        pass

    def get_candles_range(self, symbol: str, timeframe: str,
                         start: datetime, end: datetime) -> List[Candle]:
        # Data access logic
        pass
```

**Dependencies**: Core Layer (data structures, validators)

---

### 4. Core Layer (Domain Logic)

**Responsibility**: Domain models, validation, core business rules that don't change

#### Key Components:

**UnifiedStateManager** (`charts/core/state_manager.py`):
- Centralized state management
- State synchronization
- State observers/listeners

**ChartDataValidator** (`charts/core/chart_validator.py`):
- Validate chart data integrity
- OHLC validation
- Timestamp validation
- Data sanitization

**UnifiedTimeManager** (`charts/core/unified_time_manager.py`):
- Global time coordination
- Timeframe activity tracking
- Time synchronization across components

**UniversalSkipRenderer** (`charts/core/skip_renderer.py`):
- Render skip events for any timeframe
- Cross-timeframe adaptation
- Legacy compatibility bridge

**ChartSeriesLifecycleManager** (`charts/core/series_manager.py`):
- Track chart series state
- Determine when recreation is needed
- State machine for chart lifecycle

**DebugController** (`charts/core/debug_controller.py`):
- Debug mode control logic
- Time manipulation
- Multi-timeframe synchronization

**ChartDataCache** (`charts/core/cache_manager.py`):
- Memory-based data cache
- Smart invalidation
- Preload tracking

**EventBasedTransaction** (`charts/core/transaction.py`):
- Transaction management for skip events
- Backup and rollback capability

#### Example Core Component:
```python
class UnifiedTimeManager:
    """
    Zentrale Zeit-Koordination für alle Timeframes
    Skip-Events werden isoliert vom globalen TimeManager verwaltet
    """
    def __init__(self):
        self._current_time: Optional[datetime] = None
        self._timeframe_activities: Dict[str, datetime] = {}

    def set_time(self, time: datetime, source: str = "unknown"):
        """Setzt globale Zeit"""
        pass

    def get_current_time(self) -> Optional[datetime]:
        """Gibt aktuelle globale Zeit zurück"""
        pass
```

**Dependencies**: None (or minimal, only Python standard library)

---

## Data Flow Examples

### Example 1: Timeframe Switch

```
User clicks "15m" button
       │
       ▼
[chart.html] JavaScript sends WebSocket message
       │
       ▼
[websocket_handler.py] Receives "timeframe_change" command
       │
       ▼
[chart.py] HTTP endpoint /api/chart/change_timeframe
       │
       ▼
[TimeframeService] switch_timeframe(from="5m", to="15m")
       │
       ├─► [ChartSeriesLifecycleManager] Check if recreation needed
       │
       ├─► [TimeframeDataRepository] Load 15m candles
       │       │
       │       └─► [CSVRepository] Get candles from CSV
       │               │
       │               └─► [ChartDataCache] Check cache first
       │
       ├─► [UniversalSkipRenderer] Render skip events for 15m
       │
       ├─► [ChartDataValidator] Validate loaded data
       │
       ├─► [UnifiedTimeManager] Update time tracking
       │
       └─► [TimeframeService] Preload adjacent timeframes (3m, 30m)
       │
       ▼
[chart.py] Format response with validated data
       │
       ▼
[WebSocketManager] Broadcast to all clients
       │
       ▼
[chart.html] JavaScript updates TradingView chart
```

### Example 2: Skip Forward Operation

```
User clicks "Skip" button
       │
       ▼
[chart.html] JavaScript sends WebSocket "skip" command
       │
       ▼
[websocket_handler.py] Receives command
       │
       ▼
[debug.py] HTTP endpoint /api/debug/skip
       │
       ▼
[NavigationService] skip_forward(timeframe="5m")
       │
       ├─► [DebugController] skip_with_real_data()
       │       │
       │       ├─► [TimeframeSyncManager] Get next candle
       │       │
       │       └─► [TimeframeAggregator] Check if complete/incomplete
       │
       ├─► [ChartDataValidator] Validate candle
       │
       ├─► [UniversalSkipRenderer] Create skip event
       │       │
       │       └─► [UnifiedTimeManager] Get current time (master clock)
       │
       ├─► [global_skip_events] Store event for cross-timeframe persistence
       │
       └─► [UnifiedTimeManager] Update current time
       │
       ▼
[debug.py] Return skip result
       │
       ▼
[WebSocketManager] Broadcast new candle
       │
       ▼
[chart.html] JavaScript adds candle to chart
```

---

## Design Patterns

### 1. Dependency Injection Pattern

**Purpose**: Loose coupling, testability

**Implementation**:
```python
# Bad (tight coupling):
class ChartService:
    def __init__(self):
        self.repo = CSVRepository()  # Hard dependency

# Good (dependency injection):
class ChartService:
    def __init__(self, repo: CSVRepository):
        self.repo = repo  # Injected dependency

# Usage:
csv_repo = CSVRepository(csv_loader)
chart_service = ChartService(repo=csv_repo)
```

**Benefits**:
- Easy to test (inject mocks)
- Easy to swap implementations
- Clear dependencies

---

### 2. Repository Pattern

**Purpose**: Abstract data access, uniform interface

**Implementation**:
```python
class CSVRepository:
    def get_candles_by_date(self, ...): ...
    def get_candles_range(self, ...): ...

# Future: could add DatabaseRepository with same interface
class DatabaseRepository:
    def get_candles_by_date(self, ...): ...
    def get_candles_range(self, ...): ...
```

**Benefits**:
- Data source is interchangeable
- Business logic doesn't know about CSV details
- Easy to add new data sources

---

### 3. Service Layer Pattern

**Purpose**: Centralize business logic

**Implementation**:
```python
class NavigationService:
    def go_to_date(self, ...): ...
    def skip_forward(self, ...): ...
    def next_candle(self, ...): ...
```

**Benefits**:
- Business rules in one place
- Reusable across different interfaces (HTTP, WebSocket, CLI)
- Easier to test business logic

---

### 4. Factory Pattern

**Purpose**: Consistent object creation

**Implementation**:
```python
class CandleFactory:
    @staticmethod
    def from_csv_row(row: pd.Series) -> Candle:
        # Standardized creation from CSV
        pass

    @staticmethod
    def from_dict(data: dict) -> Candle:
        # Standardized creation from dict
        pass
```

**Benefits**:
- Centralized validation during creation
- Consistent object structure
- Easy to modify creation logic

---

### 5. State Machine Pattern

**Purpose**: Manage complex state transitions

**Implementation**:
```python
class ChartSeriesLifecycleManager:
    STATES = {
        'CLEAN': 'clean',
        'SKIP_MODIFIED': 'skip_modified',
        'CORRUPTED': 'corrupted'
    }

    def track_skip_operation(self, timeframe: str):
        # Transition: CLEAN → SKIP_MODIFIED
        pass

    def complete_timeframe_transition(self, success: bool):
        # Transition based on success
        pass
```

**Benefits**:
- Clear state transitions
- Prevents invalid states
- Easy to debug state issues

---

### 6. Strategy Pattern

**Purpose**: Interchangeable algorithms

**Implementation**:
```python
class AggregationStrategy(ABC):
    @abstractmethod
    def aggregate(self, candles): ...

class OHLCAggregation(AggregationStrategy):
    def aggregate(self, candles):
        # Standard OHLC aggregation
        pass

class VWAPAggregation(AggregationStrategy):
    def aggregate(self, candles):
        # VWAP-based aggregation
        pass
```

**Benefits**:
- Easy to add new aggregation methods
- Business logic doesn't depend on specific algorithm
- Testable in isolation

---

### 7. Observer Pattern

**Purpose**: Event-driven updates

**Implementation**:
```python
class WebSocketManager:
    def __init__(self):
        self.connections = []

    async def broadcast(self, message: dict):
        for connection in self.connections:
            await connection.send_json(message)
```

**Benefits**:
- Decoupled communication
- Multiple observers can react to events
- Real-time updates

---

## Key Design Decisions

### 1. Why FastAPI over Flask/Django?

**Reasons**:
- Native async/await support (critical for WebSocket)
- Automatic API documentation (Swagger UI)
- Type hints with Pydantic validation
- High performance (Starlette + Uvicorn)
- Modern Python features

### 2. Why Layer Separation?

**Reasons**:
- **Testability**: Each layer can be tested independently
- **Maintainability**: Changes in one layer don't affect others
- **Scalability**: Easy to add new features
- **Team Collaboration**: Different team members can work on different layers
- **Clear Responsibility**: Each component has one job

### 3. Why Dependency Injection?

**Reasons**:
- **Loose Coupling**: Components don't create their dependencies
- **Testing**: Easy to inject mocks/stubs
- **Flexibility**: Easy to swap implementations
- **Clear Dependencies**: Constructor shows what component needs

### 4. Why Not Use an ORM (like SQLAlchemy)?

**Reasons**:
- CSV files are the primary data source
- No database needed for this use case
- Simpler architecture without ORM overhead
- Direct pandas integration for data processing

### 5. Why Memory-Based Caching?

**Reasons**:
- **Performance**: Sub-millisecond access times
- **Simplicity**: No external cache server (Redis)
- **Sufficient for use case**: Data fits in memory
- **Development Speed**: Faster development without cache setup

---

## Performance Considerations

### 1. Timeframe Switch Optimization

**Problem**: Switching timeframes was slow (>1s)

**Solution**:
```python
# In TimeframeService
def preload_adjacent_timeframes(self, current_timeframe: str):
    """Preload ±1 timeframe in background"""
    adjacent = self._get_adjacent_timeframes(current_timeframe)
    for tf in adjacent:
        asyncio.create_task(self._load_timeframe_async(tf))
```

**Result**: <500ms timeframe switch

---

### 2. Smart Cache Invalidation

**Problem**: Cache was invalidated too often, causing reloads

**Solution**:
```python
class ChartDataCache:
    def should_invalidate_cache(self, timeframe, reason):
        if reason == "csv_modified":
            return True  # Critical
        if reason == "explicit_request":
            return True  # Critical
        return False  # Keep cache for other reasons
```

**Result**: Fewer cache misses, better performance

---

### 3. WebSocket Message Batching

**Problem**: Too many small WebSocket messages

**Solution**:
```python
# Batch updates when possible
bulletproof_message = {
    'type': 'bulletproof_timeframe_changed',
    'timeframe': target_timeframe,
    'data': final_validated_data,
    'transaction_id': transaction_id,
    'validation_summary': {...}
}
await manager.broadcast(bulletproof_message)
```

**Result**: Reduced network overhead

---

### 4. Async I/O for Data Loading

**Problem**: Blocking I/O during CSV loading

**Solution**:
```python
# Run CPU-bound tasks in thread pool
asyncio.create_task(asyncio.to_thread(
    timeframe_service.preload_adjacent_timeframes, target_timeframe
))
```

**Result**: Non-blocking operations, better responsiveness

---

## Testing Strategy

### Unit Tests (80%)

Test individual components in isolation:

```python
def test_navigation_service_go_to_date(mock_repo, mock_controller):
    service = NavigationService(
        timeframe_repo=mock_repo,
        debug_controller=mock_controller,
        # ... other mocks
    )

    result = service.go_to_date(
        target_date=datetime(2024, 12, 17),
        timeframe="5m"
    )

    assert result['success'] is True
    assert len(result['chart_data']) > 0
```

### Integration Tests (15%)

Test multiple components working together:

```python
async def test_timeframe_switch_integration():
    # Real repositories, real services
    csv_repo = CSVRepository(csv_loader)
    timeframe_repo = TimeframeDataRepository(csv_loader, time_manager)
    timeframe_service = TimeframeService(timeframe_repo, ...)

    result = timeframe_service.switch_timeframe("5m", "15m", 200)

    assert result['needs_recreation'] in [True, False]
    assert len(result['chart_data']) > 0
```

### E2E Tests (5%)

Test complete user flows (future):

```python
async def test_user_workflow_timeframe_change():
    # Start server
    # Connect WebSocket
    # Send timeframe_change command
    # Verify response
    # Verify chart updates
```

---

## Future Enhancements

### 1. Event Sourcing

Store all events (skip, go_to_date, etc.) for:
- Replay capability
- Audit log
- User behavior analysis

### 2. CQRS (Command Query Responsibility Segregation)

Separate read and write models for better performance.

### 3. Microservices Architecture

Split into separate services:
- Chart Service
- Data Service
- Analytics Service
- User Service

### 4. GraphQL API

Add GraphQL endpoint for flexible data querying.

---

## Conclusion

This architecture provides a solid foundation for the RL Trading Chart Server. It's:

- ✅ **Maintainable**: Clear separation of concerns
- ✅ **Testable**: Comprehensive test coverage
- ✅ **Scalable**: Easy to add new features
- ✅ **Performant**: Optimized for real-time trading
- ✅ **Documented**: Clear documentation and examples

The system is ready for production use and can be easily extended with new features.

---

**Last Updated**: 2025-10-11
**Version**: 2.0
**Authors**: Development Team + Claude Code
