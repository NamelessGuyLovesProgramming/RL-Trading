"""
Skip Renderer - Universal Skip Event Rendering System
Rendert Skip-Events dynamisch für jeden Timeframe mit Cross-Timeframe Kompatibilität
"""

from datetime import datetime
from typing import List, Dict, Any, Optional


class UniversalSkipRenderer:
    """
    Rendert Skip-Events dynamisch für jeden Timeframe - Single Source of Truth

    Verantwortlichkeiten:
    - Cross-Timeframe Skip-Event Rendering
    - Timeframe-Kompatibilitäts-Prüfung
    - Candle-Validierung (Kontaminations-Schutz)
    - Zeit-Anpassung für verschiedene Timeframes
    """

    # Timeframe zu Minuten Mapping
    TIMEFRAME_MINUTES = {
        '1m': 1, '2m': 2, '3m': 3, '5m': 5,
        '15m': 15, '30m': 30, '1h': 60, '4h': 240
    }

    def __init__(self, price_repository=None):
        """
        Initialisiert Skip Renderer

        Args:
            price_repository: Optional UnifiedPriceRepository für Price-Sync
        """
        self.price_repository = price_repository
        print("[UniversalSkipRenderer] Initialized")

    @staticmethod
    def get_timeframe_minutes(timeframe: str) -> int:
        """
        Konvertiert Timeframe zu Minuten

        Args:
            timeframe: Timeframe string (z.B. "5m", "1h")

        Returns:
            Anzahl Minuten
        """
        return UniversalSkipRenderer.TIMEFRAME_MINUTES.get(timeframe, 1)

    def render_skip_candles_for_timeframe(
        self,
        target_timeframe: str,
        skip_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rendert Skip-Events für spezifischen Timeframe

        Args:
            target_timeframe: Ziel-Timeframe
            skip_events: Liste von Skip-Events

        Returns:
            Liste von gerenderten Candles für target_timeframe
        """
        rendered_candles = []
        target_minutes = self.get_timeframe_minutes(target_timeframe)

        for skip_event in skip_events:
            event_time = skip_event['time']
            base_candle = skip_event['candle'].copy()  # Copy to prevent mutation
            original_tf = skip_event['original_timeframe']

            # Timeframe-Kompatibilität prüfen
            if self._is_timeframe_compatible(original_tf, target_timeframe):
                # Candle-Validierung (Kontaminations-Schutz)
                if self._is_candle_safe_for_timeframe(base_candle, target_timeframe):
                    # Timeframe-Anpassung
                    adapted_candle = self._adapt_candle_for_timeframe(
                        base_candle, original_tf, target_timeframe, event_time
                    )

                    # Price-Synchronization (falls Repository verfügbar)
                    if self.price_repository and self.price_repository.initialized:
                        synchronized_price = self.price_repository.get_synchronized_price_at_time(
                            adapted_candle['time'], target_timeframe
                        )
                        adapted_candle['close'] = synchronized_price
                        print(f"[CROSS-TF-PRICE-SYNC] {original_tf}->{target_timeframe}: "
                              f"{base_candle['close']:.2f} -> {synchronized_price:.2f}")

                    rendered_candles.append(adapted_candle)
                    print(f"[CROSS-TF-SKIP] {original_tf} Skip-Event -> {target_timeframe} verfügbar")
                else:
                    print(f"[CROSS-TF-SKIP] {original_tf} Skip-Event für {target_timeframe} "
                          f"GEFILTERT (Kontamination)")
            else:
                print(f"[CROSS-TF-SKIP] {original_tf} Skip-Event für {target_timeframe} INKOMPATIBEL")

        return rendered_candles

    @classmethod
    def _is_timeframe_compatible(cls, source_tf: str, target_tf: str) -> bool:
        """
        Prüft ob Timeframes kompatibel sind für Skip-Event Sharing

        Args:
            source_tf: Quell-Timeframe
            target_tf: Ziel-Timeframe

        Returns:
            True wenn kompatibel
        """
        # Gleicher Timeframe = immer kompatibel
        if source_tf == target_tf:
            return True

        # ENHANCED COMPATIBILITY: Beide Richtungen erlauben
        # 1. Higher -> Lower: 15m skip kann in 5m angezeigt werden (downsampling)
        # 2. Lower -> Higher: 5m skip kann in 15m aggregiert werden (upsampling)
        return True  # Filtering passiert in _adapt_candle_for_timeframe

    @classmethod
    def _is_candle_safe_for_timeframe(cls, candle: Dict[str, Any], target_timeframe: str) -> bool:
        """
        Validiert ob Kerze sicher für Ziel-Timeframe ist (Kontaminations-Schutz)

        Args:
            candle: Candle Dictionary
            target_timeframe: Ziel-Timeframe

        Returns:
            True wenn valide
        """
        try:
            # Basic null/undefined checks
            if not candle or not isinstance(candle, dict):
                return False

            # Required fields check
            required_fields = ['time', 'open', 'high', 'low', 'close']
            if not all(field in candle for field in required_fields):
                return False

            # OHLC value validation (realistic NQ range)
            ohlc_values = [candle['open'], candle['high'], candle['low'], candle['close']]
            for val in ohlc_values:
                if not isinstance(val, (int, float)) or val < 1000 or val > 50000:
                    return False

            return True

        except Exception:
            return False

    @classmethod
    def _adapt_candle_for_timeframe(
        cls,
        candle: Dict[str, Any],
        source_tf: str,
        target_tf: str,
        event_time: datetime
    ) -> Dict[str, Any]:
        """
        Adaptiert Kerze für Ziel-Timeframe (Zeit-Anpassung wenn nötig)

        Args:
            candle: Candle Dictionary
            source_tf: Quell-Timeframe
            target_tf: Ziel-Timeframe
            event_time: Event-Zeit

        Returns:
            Adaptierte Candle
        """
        adapted_candle = candle.copy()

        # Zeit-Anpassung für verschiedene Timeframes
        if source_tf != target_tf:
            target_minutes = cls.get_timeframe_minutes(target_tf)

            # Align to target timeframe boundaries
            aligned_time = event_time.replace(
                minute=(event_time.minute // target_minutes) * target_minutes,
                second=0,
                microsecond=0
            )
            adapted_candle['time'] = int(aligned_time.timestamp())

            print(f"[CROSS-TF-SKIP] Zeit-Anpassung: {source_tf}@{event_time} -> "
                  f"{target_tf}@{aligned_time}")

        return adapted_candle

    def create_skip_event(
        self,
        candle: Dict[str, Any],
        original_timeframe: str,
        master_clock: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Erstellt neues Skip-Event

        Args:
            candle: Candle Dictionary
            original_timeframe: Original Timeframe
            master_clock: Master Clock Dictionary (wird aktualisiert)

        Returns:
            Skip-Event Dictionary
        """
        # Master Clock synchronisieren
        if not master_clock.get('initialized', False):
            master_clock['current_time'] = datetime.fromtimestamp(candle['time'])
            master_clock['initialized'] = True
        else:
            master_clock['current_time'] = datetime.fromtimestamp(candle['time'])

        # Price synchronization
        synchronized_candle = candle.copy()
        if self.price_repository and self.price_repository.initialized:
            master_price = self.price_repository.get_synchronized_price_at_time(
                candle['time'], original_timeframe
            )
            synchronized_candle['close'] = master_price
            print(f"[PRICE-SYNC] {original_timeframe} skip candle price synchronized: "
                  f"{candle['close']:.2f} -> {master_price:.2f}")
        else:
            print(f"[PRICE-SYNC] WARNING: PriceRepository not initialized - "
                  f"no sync for {original_timeframe}")

        # Skip-Event erstellen
        skip_event = {
            'time': master_clock['current_time'],
            'candle': synchronized_candle,
            'original_timeframe': original_timeframe,
            'created_at': datetime.now()
        }

        return skip_event


class LegacyCompatibilityBridge:
    """
    Bridge zwischen alter global_skip_candles Logik und neuem Event System

    Ermöglicht Rückwärts-Kompatibilität mit Legacy-Code
    """

    def __init__(self, renderer: UniversalSkipRenderer, skip_events: List[Dict[str, Any]]):
        """
        Args:
            renderer: UniversalSkipRenderer Instanz
            skip_events: Referenz zur Skip-Events Liste
        """
        self.renderer = renderer
        self.skip_events = skip_events

    def get_legacy_skip_candles_for_timeframe(self, timeframe: str) -> List[Dict[str, Any]]:
        """
        Simuliert alte global_skip_candles[timeframe] Logik

        Args:
            timeframe: Timeframe

        Returns:
            Gerenderte Candles für Timeframe
        """
        return self.renderer.render_skip_candles_for_timeframe(timeframe, self.skip_events)

    def items(self):
        """Simuliert global_skip_candles.items() für Legacy-Code"""
        timeframes = ['1m', '2m', '3m', '5m', '15m', '30m', '1h', '4h']
        items = []
        for tf in timeframes:
            rendered_candles = self.renderer.render_skip_candles_for_timeframe(tf, self.skip_events)
            items.append((tf, rendered_candles))
        return items

    def __getitem__(self, timeframe: str) -> List[Dict[str, Any]]:
        """Simuliert global_skip_candles[timeframe] Access"""
        return self.get_legacy_skip_candles_for_timeframe(timeframe)

    def get(self, timeframe: str, default=None) -> List[Dict[str, Any]]:
        """Simuliert global_skip_candles.get(timeframe, default) Access"""
        try:
            return self.get_legacy_skip_candles_for_timeframe(timeframe)
        except:
            return default if default is not None else []
