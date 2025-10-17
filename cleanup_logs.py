#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entfernt unwichtige console.log Statements aus chart.js
Behält nur kritische Fehler und wichtige Aktionen
"""

import re

# Logs die ENTFERNT werden sollen (unwichtig)
PATTERNS_TO_REMOVE = [
    r"console\.log\('🔧[^']*'\)",
    r'console\.log\("🔧[^"]*"\)',
    r"console\.log\('✅ Chart initialisiert",
    r"console\.log\('✅ NQ-Daten geladen",
    r"console\.log\('✅.*Event Handler",
    r"console\.log\('✅.*Button",
    r"console\.log\('✅.*registered",
    r"console\.log\('📊 Lade",
    r"console\.log\('📊 Status",
    r"console\.log\('📊 Chart-Daten",
    r"console\.log\('🔗 WebSocket",
    r"console\.log\('📨 Message received",
    r"console\.log\('🌍 Global functions",
    r"console\.log\('DRASTIC",
    r"console\.log\('FINAL:",
    r"console\.log\('DELAYED:",
    r"console\.log\('API TEST",
    r"console\.log\('AUTO TEST",
    r"console\.log\('DIRECT TEST",
    r"console\.log\(`📊 Box ab Click",
    r"console\.log\(`📍 Box Kerzen",
    r"console\.log\(`📍 Box Timestamps",
    r"console\.log\(`💰 Preise:",
    r"console\.log\('📍 Click-Position",
    r"console\.log\(`📏 Timeframe",
    r"console\.log\(`🎯 Click-Kerze",
    r"console\.log\(`📦 Box:",
    r"console\.log\(`📦 Neue Position Box erstellt",
    r"console\.log\('➕ Box added",
    r"console\.log\('🎯 Active box",
    r"console\.log\('📐 TradingView Canvas",
    r"console\.log\('📄 Canvas",
    r"console\.log\('📊 Price Lines erstellt",
    r"\[SERVER LOG\]",
]

def cleanup_logs(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_lines = len(content.split('\n'))

    # Ersetze alle unwichtigen Logs
    for pattern in PATTERNS_TO_REMOVE:
        # Kommentiere die Zeile aus statt sie zu löschen (sicherer)
        content = re.sub(
            r'^(\s*)(' + pattern + r'[^;]*;)',
            r'\1// \2',
            content,
            flags=re.MULTILINE
        )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    new_lines = len(content.split('\n'))
    print(f"Cleanup abgeschlossen!")
    print(f"   Zeilen vorher: {original_lines}")
    print(f"   Zeilen nachher: {new_lines}")

if __name__ == '__main__':
    cleanup_logs('static/js/chart.js')
