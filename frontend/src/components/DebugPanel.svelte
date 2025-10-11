<script>
  import { websocket } from '../stores/websocket.js';
  import { debugMode, debugSpeed, debugPlaying } from '../stores/debug.js';
  import { currentTimeframe } from '../stores/chart.js';

  let startDate = '';
  let speed = 1.0;
  let isPlaying = false;

  // Subscribe to debug stores
  debugSpeed.subscribe(value => { speed = value; });
  debugPlaying.subscribe(value => { isPlaying = value; });

  function startDebug() {
    if (!startDate) {
      alert('Please select a start date');
      return;
    }

    websocket.send({
      type: 'go_to_date',
      date: startDate,
      timeframe: $currentTimeframe
    });

    debugMode.update(state => ({ ...state, active: true, currentDate: startDate }));
  }

  function togglePlay() {
    isPlaying = !isPlaying;
    debugPlaying.set(isPlaying);

    websocket.send({
      type: 'toggle_play'
    });

    debugMode.update(state => ({ ...state, isPlaying }));
  }

  function nextCandle() {
    websocket.send({
      type: 'skip',
      timeframe: $currentTimeframe
    });
  }

  function updateSpeed() {
    debugSpeed.set(speed);
    websocket.send({
      type: 'set_speed',
      speed: speed
    });

    debugMode.update(state => ({ ...state, speed }));
  }
</script>

<div class="debug-panel">
  <h3>🐛 Debug Mode</h3>

  <div class="control-group">
    <label for="start-date">Start Date:</label>
    <input
      id="start-date"
      type="date"
      bind:value={startDate}
      placeholder="2024-01-01"
    />
    <button on:click={startDebug} class="btn-primary">
      🚀 Go To Date
    </button>
  </div>

  <div class="control-group">
    <button on:click={togglePlay} class="btn-play">
      {isPlaying ? '⏸️ Pause' : '▶️ Play'}
    </button>
    <button on:click={nextCandle} class="btn-next">
      ⏭️ Next
    </button>
  </div>

  <div class="control-group">
    <label for="speed-range">Speed: {speed.toFixed(1)}x</label>
    <input
      id="speed-range"
      type="range"
      min="0.5"
      max="10"
      step="0.5"
      bind:value={speed}
      on:change={updateSpeed}
    />
  </div>

  {#if $debugMode.active}
    <div class="status">
      <span class="status-indicator active"></span>
      <span>Debug Mode Active</span>
    </div>
  {:else}
    <div class="status">
      <span class="status-indicator inactive"></span>
      <span>Debug Mode Inactive</span>
    </div>
  {/if}
</div>

<style>
  .debug-panel {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f1424 100%);
    border: 2px solid #089981;
    border-radius: 12px;
    padding: 24px;
    margin: 20px 0;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
  }

  h3 {
    margin: 0 0 20px 0;
    color: #089981;
    font-size: 20px;
    font-weight: 600;
  }

  .control-group {
    margin: 16px 0;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }

  label {
    color: #d1d4dc;
    font-size: 14px;
    font-weight: 500;
    min-width: 100px;
  }

  input[type="date"] {
    background: #0a0e27;
    border: 1px solid #2B2B43;
    border-radius: 6px;
    padding: 10px 14px;
    color: #d1d4dc;
    font-size: 14px;
    flex: 1;
    min-width: 150px;
  }

  input[type="date"]:focus {
    outline: none;
    border-color: #089981;
  }

  input[type="range"] {
    flex: 1;
    min-width: 150px;
    height: 6px;
    background: #2B2B43;
    border-radius: 3px;
    outline: none;
  }

  input[type="range"]::-webkit-slider-thumb {
    appearance: none;
    width: 18px;
    height: 18px;
    background: #089981;
    border-radius: 50%;
    cursor: pointer;
  }

  input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: #089981;
    border-radius: 50%;
    cursor: pointer;
    border: none;
  }

  button {
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
  }

  .btn-primary {
    background: #089981;
    color: white;
  }

  .btn-primary:hover {
    background: #0aac96;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(8, 153, 129, 0.3);
  }

  .btn-play {
    background: #2563eb;
    color: white;
  }

  .btn-play:hover {
    background: #1d4ed8;
  }

  .btn-next {
    background: #8b5cf6;
    color: white;
  }

  .btn-next:hover {
    background: #7c3aed;
  }

  .status {
    margin-top: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px;
    background: rgba(8, 153, 129, 0.1);
    border-radius: 6px;
  }

  .status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }

  .status-indicator.active {
    background: #089981;
    box-shadow: 0 0 10px rgba(8, 153, 129, 0.5);
    animation: pulse 2s infinite;
  }

  .status-indicator.inactive {
    background: #6b7280;
  }

  .status span {
    color: #d1d4dc;
    font-size: 14px;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }
</style>
