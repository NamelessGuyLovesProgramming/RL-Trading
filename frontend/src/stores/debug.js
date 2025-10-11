import { writable } from 'svelte/store';

export const debugMode = writable({
  active: false,
  currentDate: null,
  speed: 1.0,
  isPlaying: false
});

export const debugSpeed = writable(1.0);
export const debugPlaying = writable(false);
