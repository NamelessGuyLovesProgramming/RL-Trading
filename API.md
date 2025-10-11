# API Documentation

Complete API reference for the RL Trading Chart Server 2.0.

**Base URL**: `http://localhost:8003`

**Interactive Documentation**: Visit `/docs` for Swagger UI

---

## Table of Contents

1. [WebSocket API](#websocket-api)
2. [Chart Endpoints](#chart-endpoints)
3. [Debug Endpoints](#debug-endpoints)
4. [Static Endpoints](#static-endpoints)
5. [WebSocket Message Types](#websocket-message-types)
6. [Error Responses](#error-responses)

---

## WebSocket API

### Connect

```
ws://localhost:8003/ws
```

### WebSocket Message Format

All WebSocket messages follow this structure:

```json
{
  "type": "message_type",
  "param1": "value1",
  "param2": "value2"
}
```

### Supported Commands

#### 1. Get Chart Data

**Request**:
```json
{
  "type": "get_chart_data",
  "timeframe": "5m",
  "visible_candles": 200
}
```

**Response**:
```json
{
  "type": "chart_data",
  "data": [...],
  "timeframe": "5m",
  "count": 200
}
```

#### 2. Change Timeframe

**Request**:
```json
{
  "type": "timeframe_change",
  "timeframe": "15m",
  "visible_candles": 200
}
```

**Response**:
```json
{
  "type": "bulletproof_timeframe_changed",
  "timeframe": "15m",
  "data": [...],
  "transaction_id": "tf_transition_1234567890",
  "chart_recreation": false,
  "global_time": "2024-12-31T16:55:00",
  "validation_summary": {
    "original_count": 200,
    "validated_count": 200,
    "data_source": "timeframe_service",
    "skip_contamination": "CLEAN"
  }
}
```

#### 3. Go To Date

**Request**:
```json
{
  "type": "go_to_date",
  "date": "2024-12-17",
  "timeframe": "5m"
}
```

**Response**:
```json
{
  "type": "goto_date_result",
  "status": "success",
  "data": [...],
  "actual_date": "2024-12-17T09:30:00",
  "candles_loaded": 200
}
```

#### 4. Skip Forward

**Request**:
```json
{
  "type": "skip",
  "timeframe": "5m"
}
```

**Response**:
```json
{
  "type": "skip_result",
  "candle": {
    "time": 1734441600,
    "open": 20125.5,
    "high": 20135.2,
    "low": 20118.8,
    "close": 20132.1,
    "volume": 1250
  },
  "candle_type": "complete_candle",
  "new_time": "2024-12-17T10:35:00"
}
```

#### 5. Add Position

**Request**:
```json
{
  "type": "add_position",
  "position": {
    "id": "pos_123",
    "entry_price": 20100.0,
    "sl_price": 20050.0,
    "tp_price": 20200.0,
    "entry_time": "2024-12-17T10:00:00",
    "direction": "long"
  }
}
```

**Response**:
```json
{
  "type": "add_position",
  "position": {...}
}
```

#### 6. Remove Position

**Request**:
```json
{
  "type": "remove_position",
  "position_id": "pos_123"
}
```

**Response**:
```json
{
  "type": "remove_position",
  "position_id": "pos_123"
}
```

#### 7. Get Debug State

**Request**:
```json
{
  "type": "get_debug_state"
}
```

**Response**:
```json
{
  "type": "debug_state",
  "active": true,
  "current_date": "2024-12-17T10:35:00",
  "speed": 1.0,
  "auto_play": false,
  "timeframe": "5m"
}
```

#### 8. Set Speed

**Request**:
```json
{
  "type": "set_speed",
  "speed": 2.5
}
```

**Response**:
```json
{
  "type": "speed_changed",
  "speed": 2.5
}
```

#### 9. Toggle Play

**Request**:
```json
{
  "type": "toggle_play"
}
```

**Response**:
```json
{
  "type": "play_toggled",
  "is_playing": true,
  "speed": 1.0
}
```

---

## Chart Endpoints

### 1. Get Chart Status

```http
GET /api/chart/status
```

**Response**:
```json
{
  "status": "success",
  "chart_state": {
    "interval": "5m",
    "data_count": 200,
    "positions_count": 0
  }
}
```

### 2. Get Chart Data

```http
GET /api/chart/data
```

**Response**:
```json
{
  "status": "success",
  "data": [
    {
      "time": 1734441600,
      "open": 20125.5,
      "high": 20135.2,
      "low": 20118.8,
      "close": 20132.1,
      "volume": 1250
    }
  ],
  "interval": "5m",
  "count": 200
}
```

### 3. Change Timeframe

```http
POST /api/chart/change_timeframe
Content-Type: application/json

{
  "timeframe": "15m",
  "visible_candles": 200
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Timeframe-Switch: 5m -> 15m",
  "data": [...],
  "timeframe": "15m",
  "count": 200,
  "transaction_id": "tf_transition_1234567890",
  "transition_plan": {
    "needs_recreation": false,
    "reason": "no_recreation_needed"
  },
  "global_time": "2024-12-31T16:55:00",
  "system": "timeframe_service"
}
```

### 4. Add Position

```http
POST /api/chart/add_position
Content-Type: application/json

{
  "position": {
    "id": "pos_123",
    "entry_price": 20100.0,
    "sl_price": 20050.0,
    "tp_price": 20200.0,
    "entry_time": "2024-12-17T10:00:00",
    "direction": "long"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Position overlay added"
}
```

### 5. Remove Position

```http
POST /api/chart/remove_position
Content-Type: application/json

{
  "position_id": "pos_123"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Position overlay removed"
}
```

### 6. Sync Positions

```http
POST /api/chart/sync_positions
Content-Type: application/json

{
  "positions": [
    {
      "id": "pos_123",
      "entry_price": 20100.0,
      "sl_price": 20050.0,
      "tp_price": 20200.0,
      "entry_time": "2024-12-17T10:00:00",
      "direction": "long"
    }
  ]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Synchronized 1 positions"
}
```

---

## Debug Endpoints

### 1. Skip Forward

```http
POST /api/debug/skip
Content-Type: application/json

{
  "timeframe": "5m"
}
```

**Response**:
```json
{
  "status": "success",
  "new_time": "2024-12-17T10:35:00",
  "candle_type": "complete_candle",
  "candle": {
    "time": 1734441600,
    "open": 20125.5,
    "high": 20135.2,
    "low": 20118.8,
    "close": 20132.1,
    "volume": 1250
  }
}
```

### 2. Go To Date

```http
POST /api/debug/go_to_date
Content-Type: application/json

{
  "date": "2024-12-17",
  "timeframe": "5m"
}
```

**Response**:
```json
{
  "status": "success",
  "actual_date": "2024-12-17T09:30:00",
  "candles_loaded": 200,
  "data": [...]
}
```

### 3. Set Speed

```http
POST /api/debug/set_speed
Content-Type: application/json

{
  "speed": 2.5
}
```

**Response**:
```json
{
  "status": "success",
  "speed": 2.5
}
```

### 4. Toggle Play

```http
POST /api/debug/toggle_play
```

**Response**:
```json
{
  "status": "success",
  "is_playing": true,
  "speed": 1.0
}
```

### 5. Get Debug State

```http
GET /api/debug/state
```

**Response**:
```json
{
  "status": "success",
  "active": true,
  "current_date": "2024-12-17T10:35:00",
  "speed": 1.0,
  "auto_play": false,
  "timeframe": "5m"
}
```

### 6. Log Debug Message

```http
POST /api/debug/log
Content-Type: application/json

{
  "message": "Debug message from client",
  "level": "info"
}
```

**Response**:
```json
{
  "status": "success",
  "logged": true
}
```

---

## Static Endpoints

### 1. Serve Chart Page

```http
GET /
```

**Response**: HTML page with TradingView chart

### 2. Favicon

```http
GET /favicon.ico
```

**Response**: 404 (favicon not implemented)

### 3. Static Files

```http
GET /static/{file_path}
```

**Response**: Static file (JS, CSS, images)

---

## WebSocket Message Types

### Server → Client Messages

#### Chart Data Update
```json
{
  "type": "chart_data",
  "data": [...],
  "timeframe": "5m",
  "count": 200
}
```

#### Timeframe Changed
```json
{
  "type": "bulletproof_timeframe_changed",
  "timeframe": "15m",
  "data": [...],
  "transaction_id": "...",
  "chart_recreation": false
}
```

#### Chart Series Recreation
```json
{
  "type": "chart_series_recreation",
  "command": "recreate",
  "reason": "skip_operations",
  "transaction_id": "..."
}
```

#### Emergency Recovery
```json
{
  "type": "emergency_recovery_required",
  "transaction_id": "...",
  "error": "Error message",
  "recovery_action": "page_reload"
}
```

#### Position Updates
```json
{
  "type": "add_position",
  "position": {...}
}
```

```json
{
  "type": "remove_position",
  "position_id": "pos_123"
}
```

```json
{
  "type": "positions_sync",
  "positions": [...]
}
```

---

## Error Responses

### HTTP Error Response Format

```json
{
  "status": "error",
  "message": "Error description",
  "details": "Additional details (optional)"
}
```

### Common Error Codes

#### 400 Bad Request
```json
{
  "status": "error",
  "message": "Invalid timeframe specified"
}
```

#### 404 Not Found
```json
{
  "status": "error",
  "message": "Endpoint not found"
}
```

#### 500 Internal Server Error
```json
{
  "status": "error",
  "message": "Internal server error",
  "transaction_id": "...",
  "recovery_required": true
}
```

### WebSocket Error Messages

```json
{
  "type": "error",
  "message": "Invalid command",
  "original_message": {...}
}
```

---

## Rate Limiting

Currently, no rate limiting is implemented. However, best practices recommend:

- **HTTP Endpoints**: Max 100 requests/minute per IP
- **WebSocket Messages**: Max 10 messages/second

---

## Authentication

Currently, no authentication is required. All endpoints are publicly accessible.

**Future**: JWT-based authentication planned for production deployments.

---

## Data Models

### Candle

```typescript
interface Candle {
  time: number;        // Unix timestamp
  open: number;        // Open price
  high: number;        // High price
  low: number;         // Low price
  close: number;       // Close price
  volume?: number;     // Volume (optional)
}
```

### Position

```typescript
interface Position {
  id: string;          // Unique identifier
  entry_price: number; // Entry price
  sl_price: number;    // Stop-loss price
  tp_price: number;    // Take-profit price
  entry_time: string;  // ISO 8601 datetime
  direction: "long" | "short";
}
```

### Timeframe

```typescript
type Timeframe = "1m" | "2m" | "3m" | "5m" | "15m" | "30m" | "1h" | "4h";
```

---

## Examples

### Python Client Example

```python
import requests
import websockets
import asyncio
import json

# HTTP Request
response = requests.post(
    "http://localhost:8003/api/chart/change_timeframe",
    json={"timeframe": "15m", "visible_candles": 200}
)
print(response.json())

# WebSocket Client
async def websocket_client():
    uri = "ws://localhost:8003/ws"
    async with websockets.connect(uri) as websocket:
        # Send command
        await websocket.send(json.dumps({
            "type": "timeframe_change",
            "timeframe": "15m",
            "visible_candles": 200
        }))

        # Receive response
        response = await websocket.recv()
        print(json.loads(response))

asyncio.run(websocket_client())
```

### JavaScript Client Example

```javascript
// WebSocket Connection
const ws = new WebSocket('ws://localhost:8003/ws');

ws.onopen = () => {
    console.log('Connected');

    // Send command
    ws.send(JSON.stringify({
        type: 'timeframe_change',
        timeframe: '15m',
        visible_candles: 200
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};

// HTTP Request
fetch('http://localhost:8003/api/chart/change_timeframe', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        timeframe: '15m',
        visible_candles: 200
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for API version history.

---

**Last Updated**: 2025-10-11
**API Version**: 2.0
**Server Version**: 2.0.0
