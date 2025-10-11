<script>
  import { onMount, onDestroy } from 'svelte';
  import { createChart } from 'lightweight-charts';
  import { chartData, positions, skipEvents } from '../stores/chart.js';
  import { websocket } from '../stores/websocket.js';

  let chartContainer;
  let chart;
  let candlestickSeries;
  let lineSeries = [];
  let markers = [];

  onMount(() => {
    // Initialize TradingView Lightweight Chart
    chart = createChart(chartContainer, {
      width: chartContainer.clientWidth,
      height: 600,
      layout: {
        background: { color: '#0a0e27' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#1a2332', visible: true },
        horzLines: { color: '#1a2332', visible: true },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          width: 1,
          color: '#758696',
          style: 0,
        },
        horzLine: {
          width: 1,
          color: '#758696',
          style: 0,
        },
      },
      rightPriceScale: {
        borderColor: '#2B2B43',
      },
      timeScale: {
        borderColor: '#2B2B43',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // Add candlestick series
    candlestickSeries = chart.addCandlestickSeries({
      upColor: '#089981',
      downColor: '#f23645',
      borderVisible: false,
      wickUpColor: '#089981',
      wickDownColor: '#f23645',
    });

    // Subscribe to chart data changes
    const unsubscribeChartData = chartData.subscribe(data => {
      if (data && data.length > 0) {
        console.log('[Chart] Updating with', data.length, 'candles');
        candlestickSeries.setData(data);
        chart.timeScale().fitContent();
      }
    });

    // Subscribe to positions changes
    const unsubscribePositions = positions.subscribe(pos => {
      if (pos && pos.length > 0) {
        console.log('[Chart] Updating positions:', pos.length);
        updatePositionLines(pos);
      }
    });

    // Subscribe to skip events
    const unsubscribeSkipEvents = skipEvents.subscribe(events => {
      if (events && events.length > 0) {
        console.log('[Chart] Updating skip events:', events.length);
        updateSkipMarkers(events);
      }
    });

    // Handle window resize
    const handleResize = () => {
      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth
        });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      unsubscribeChartData();
      unsubscribePositions();
      unsubscribeSkipEvents();
      window.removeEventListener('resize', handleResize);
      if (chart) {
        chart.remove();
      }
    };
  });

  function updatePositionLines(pos) {
    // Clear existing lines
    lineSeries.forEach(line => chart.removeSeries(line));
    lineSeries = [];

    pos.forEach(position => {
      // Entry line
      const entryLine = chart.addLineSeries({
        color: position.direction === 'long' ? '#089981' : '#f23645',
        lineWidth: 2,
        lineStyle: 0,
      });
      entryLine.setData([
        { time: position.entry_time, value: position.entry_price }
      ]);
      lineSeries.push(entryLine);

      // SL line
      const slLine = chart.addLineSeries({
        color: '#f23645',
        lineWidth: 1,
        lineStyle: 2,
      });
      slLine.setData([
        { time: position.entry_time, value: position.sl_price }
      ]);
      lineSeries.push(slLine);

      // TP line
      const tpLine = chart.addLineSeries({
        color: '#089981',
        lineWidth: 1,
        lineStyle: 2,
      });
      tpLine.setData([
        { time: position.entry_time, value: position.tp_price }
      ]);
      lineSeries.push(tpLine);
    });
  }

  function updateSkipMarkers(events) {
    const newMarkers = events.map(event => ({
      time: event.time,
      position: 'aboveBar',
      color: '#ff9800',
      shape: 'arrowDown',
      text: 'Skip'
    }));

    if (candlestickSeries && newMarkers.length > 0) {
      candlestickSeries.setMarkers(newMarkers);
      markers = newMarkers;
    }
  }
</script>

<div bind:this={chartContainer} class="chart-container"></div>

<style>
  .chart-container {
    width: 100%;
    height: 600px;
    position: relative;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
  }
</style>
