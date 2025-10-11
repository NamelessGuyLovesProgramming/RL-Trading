<script>
  import { onMount } from 'svelte';
  import Chart from './components/Chart.svelte';
  import TimeframeButtons from './components/TimeframeButtons.svelte';
  import DebugPanel from './components/DebugPanel.svelte';
  import { websocket } from './stores/websocket.js';
  import { chartData, currentTimeframe, visibleCandles, positions, skipEvents } from './stores/chart.js';
  import { debugMode } from './stores/debug.js';

  let connectionStatus = 'connecting';

  onMount(() => {
    // Subscribe to WebSocket store
    const unsubscribe = websocket.subscribe(state => {
      if (state.connected) {
        connectionStatus = 'connected';

        // Request initial chart data
        websocket.send({
          type: 'get_chart_data',
          timeframe: $currentTimeframe,
          visible_candles: $visibleCandles
        });

        // Request debug state
        websocket.send({
          type: 'get_debug_state'
        });
      } else if (state.reconnecting) {
        connectionStatus = 'reconnecting';
      } else if (state.error) {
        connectionStatus = 'error';
      } else {
        connectionStatus = 'disconnected';
      }

      // Handle incoming messages
      if (state.data) {
        handleWebSocketMessage(state.data);
      }
    });

    return () => {
      unsubscribe();
      websocket.close();
    };
  });

  function handleWebSocketMessage(message) {
    console.log('[App] Handling message:', message.type);

    switch (message.type) {
      case 'chart_data':
      case 'goto_date_result':
        if (message.data && Array.isArray(message.data)) {
          chartData.set(message.data);
        }
        break;

      case 'bulletproof_timeframe_changed':
      case 'timeframe_changed':
        if (message.data && Array.isArray(message.data)) {
          chartData.set(message.data);
          if (message.timeframe) {
            currentTimeframe.set(message.timeframe);
          }
        }
        break;

      case 'skip_result':
        if (message.candle) {
          // Add skip event
          skipEvents.update(events => [...events, {
            time: message.candle.time,
            candle: message.candle
          }]);

          // Update chart data
          chartData.update(data => {
            const newData = [...data, message.candle];
            // Sort by time
            return newData.sort((a, b) => a.time - b.time);
          });
        }
        break;

      case 'add_position':
        if (message.position) {
          positions.update(pos => [...pos, message.position]);
        }
        break;

      case 'remove_position':
        if (message.position_id) {
          positions.update(pos => pos.filter(p => p.id !== message.position_id));
        }
        break;

      case 'debug_state':
        debugMode.set({
          active: message.active || false,
          currentDate: message.current_date || null,
          speed: message.speed || 1.0,
          isPlaying: message.auto_play || false
        });
        break;

      case 'speed_changed':
        debugMode.update(state => ({ ...state, speed: message.speed }));
        break;

      case 'play_toggled':
        debugMode.update(state => ({ ...state, isPlaying: message.is_playing }));
        break;

      case 'error':
        console.error('[App] Server error:', message.message);
        alert(`Server Error: ${message.message}`);
        break;

      default:
        console.warn('[App] Unknown message type:', message.type);
    }
  }
</script>

<main>
  <header>
    <h1>📊 RL Trading Chart Server 2.0</h1>
    <div class="connection-status">
      {#if connectionStatus === 'connected'}
        <span class="status-dot connected"></span>
        <span>Connected</span>
      {:else if connectionStatus === 'reconnecting'}
        <span class="status-dot reconnecting"></span>
        <span>Reconnecting...</span>
      {:else if connectionStatus === 'error'}
        <span class="status-dot error"></span>
        <span>Connection Error</span>
      {:else}
        <span class="status-dot disconnected"></span>
        <span>Disconnected</span>
      {/if}
    </div>
  </header>

  <div class="container">
    <TimeframeButtons />
    <Chart />
    <DebugPanel />
  </div>

  <footer>
    <p>
      Powered by <strong>Svelte</strong> + <strong>FastAPI</strong> + <strong>TradingView Lightweight Charts</strong>
    </p>
  </footer>
</main>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: #0a0e27;
    color: #d1d4dc;
  }

  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f1424 100%);
    padding: 20px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #2B2B43;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  h1 {
    margin: 0;
    font-size: 28px;
    font-weight: 700;
    background: linear-gradient(135deg, #089981 0%, #0aac96 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .connection-status {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: rgba(8, 153, 129, 0.1);
    border-radius: 20px;
    font-size: 14px;
    font-weight: 500;
  }

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }

  .status-dot.connected {
    background: #089981;
    box-shadow: 0 0 10px rgba(8, 153, 129, 0.5);
    animation: pulse 2s infinite;
  }

  .status-dot.reconnecting {
    background: #ff9800;
    animation: blink 1s infinite;
  }

  .status-dot.error {
    background: #f23645;
  }

  .status-dot.disconnected {
    background: #6b7280;
  }

  .container {
    flex: 1;
    max-width: 1600px;
    width: 100%;
    margin: 0 auto;
    padding: 40px 20px;
  }

  footer {
    background: #0f1424;
    padding: 20px;
    text-align: center;
    border-top: 2px solid #2B2B43;
    font-size: 14px;
    color: #6b7280;
  }

  footer strong {
    color: #089981;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }

  @keyframes blink {
    0%, 50% {
      opacity: 1;
    }
    51%, 100% {
      opacity: 0.3;
    }
  }
</style>
