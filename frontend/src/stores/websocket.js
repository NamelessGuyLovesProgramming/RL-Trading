import { writable } from 'svelte/store';

export function createWebSocketStore(url) {
  const { subscribe, set, update } = writable({
    connected: false,
    data: null,
    error: null,
    reconnecting: false
  });

  let ws;
  let reconnectTimer;
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 10;
  const RECONNECT_DELAY = 3000;

  function connect() {
    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('[WS] Connected to', url);
        reconnectAttempts = 0;
        update(state => ({ ...state, connected: true, error: null, reconnecting: false }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[WS] Received:', data.type);
          update(state => ({ ...state, data }));
        } catch (err) {
          console.error('[WS] Parse error:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('[WS] Error:', error);
        update(state => ({ ...state, error: 'WebSocket connection error' }));
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        update(state => ({ ...state, connected: false }));

        // Auto-Reconnect
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts++;
          update(state => ({ ...state, reconnecting: true }));
          console.log(`[WS] Reconnecting... (Attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
        } else {
          console.error('[WS] Max reconnect attempts reached');
          update(state => ({
            ...state,
            reconnecting: false,
            error: 'Connection lost. Please refresh the page.'
          }));
        }
      };
    } catch (err) {
      console.error('[WS] Connection error:', err);
      update(state => ({ ...state, error: err.message }));
    }
  }

  connect();

  return {
    subscribe,
    send: (data) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        console.log('[WS] Sending:', data.type);
        ws.send(JSON.stringify(data));
        return true;
      } else {
        console.warn('[WS] Not connected. Message not sent:', data.type);
        return false;
      }
    },
    close: () => {
      clearTimeout(reconnectTimer);
      if (ws) {
        ws.close();
      }
    },
    reconnect: () => {
      reconnectAttempts = 0;
      connect();
    }
  };
}

// Create WebSocket store instance
export const websocket = createWebSocketStore('ws://localhost:8003/ws');
