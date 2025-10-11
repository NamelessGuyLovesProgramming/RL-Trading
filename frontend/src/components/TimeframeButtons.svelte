<script>
  import { websocket } from '../stores/websocket.js';
  import { currentTimeframe, timeframes, visibleCandles } from '../stores/chart.js';

  function changeTimeframe(newTimeframe) {
    if ($currentTimeframe === newTimeframe) return;

    console.log('[TimeframeButtons] Changing timeframe:', $currentTimeframe, '->', newTimeframe);

    websocket.send({
      type: 'timeframe_change',
      timeframe: newTimeframe,
      visible_candles: $visibleCandles
    });

    currentTimeframe.set(newTimeframe);
  }
</script>

<div class="timeframe-container">
  <h4>Timeframe</h4>
  <div class="button-group">
    {#each timeframes as tf}
      <button
        class="tf-button"
        class:active={$currentTimeframe === tf}
        on:click={() => changeTimeframe(tf)}
      >
        {tf}
      </button>
    {/each}
  </div>
</div>

<style>
  .timeframe-container {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f1424 100%);
    border: 2px solid #2B2B43;
    border-radius: 12px;
    padding: 20px;
    margin: 20px 0;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
  }

  h4 {
    margin: 0 0 16px 0;
    color: #d1d4dc;
    font-size: 16px;
    font-weight: 600;
  }

  .button-group {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .tf-button {
    background: #0a0e27;
    border: 2px solid #2B2B43;
    color: #d1d4dc;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s ease;
    min-width: 60px;
  }

  .tf-button:hover {
    border-color: #089981;
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(8, 153, 129, 0.2);
  }

  .tf-button.active {
    background: #089981;
    border-color: #089981;
    color: white;
    box-shadow: 0 4px 12px rgba(8, 153, 129, 0.4);
  }

  .tf-button:active {
    transform: translateY(0);
  }
</style>
