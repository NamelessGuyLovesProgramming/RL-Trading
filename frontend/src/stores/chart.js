import { writable, derived } from 'svelte/store';

// Chart data store
export const chartData = writable([]);

// Current timeframe
export const currentTimeframe = writable('5m');

// Visible candle count
export const visibleCandles = writable(200);

// Loading state
export const isLoading = writable(false);

// Positions
export const positions = writable([]);

// Skip events
export const skipEvents = writable([]);

// Chart info
export const chartInfo = derived(
  [chartData, currentTimeframe],
  ([$chartData, $currentTimeframe]) => ({
    candleCount: $chartData.length,
    timeframe: $currentTimeframe,
    hasData: $chartData.length > 0
  })
);

// Available timeframes
export const timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h'];
