# Feedback History - Feature Dokumentation

## Übersicht

Die **Feedback History** ermöglicht es dem User, alle gespeicherten Trade-Bewertungen einzusehen und zu verwalten.

## Features

### 1. Feedback-Liste (`/feedback-list`)
- **Übersichtliche Darstellung** aller gespeicherten Feedbacks
- **Sortierung**: Neueste Feedbacks zuerst (nach Änderungsdatum)
- **Farbcodierte Rating-Badges**:
  - 👍👍 Sehr gut (grün)
  - 👍 Gut (hellgrün)
  - 😐 OK (orange)
  - 👎 Schlecht (rot)
  - 👎👎 Sehr schlecht (dunkelrot)

### 2. Trade-Details pro Feedback
Jedes Feedback zeigt:
- **Trade-ID** und **Timestamp**
- **Aktion**: LONG/SHORT
- **Entry Price**: Einstiegspreis
- **Exit Price**: Ausstiegspreis
- **PnL**: Profit/Loss (farbcodiert: grün = positiv, rot = negativ)

### 3. Feedback löschen
- **Delete-Button** bei jedem Feedback
- **Bestätigungsdialog** vor dem Löschen
- **Automatisches Reload** nach Löschung

### 4. Statistiken
- **Gesamt-Anzahl** der gespeicherten Feedbacks

## Zugriff auf die Feedback-Liste

Es gibt **2 Wege**, um zur Feedback-Liste zu gelangen:

1. **Navigation Toolbar**
   → Button "📝 Feedbacks" (oben rechts)

2. **User Account Panel**
   → Button "Feedback History" (unten im User Account Bereich, unter "Unrealized PnL")

Beide Buttons öffnen die Feedback-Liste in einem **neuen Tab**.

## Backend-Endpunkte

### GET `/feedback-list`
Lädt die HTML-Seite für die Feedback-Übersicht.

### GET `/api/feedback/list`
Gibt alle Feedbacks als JSON zurück.

**Response:**
```json
{
  "success": true,
  "feedbacks": [
    {
      "filename": "pos_1763573378.912667.json",
      "trade_id": "pos_1763573378.912667",
      "timestamp": "2024-11-19T18:29:38",
      "action": "long",
      "entry_price": 17010.50,
      "exit_price": 17012.50,
      "pnl": 198.00,
      "rating": "very_good",
      "rating_label": "Sehr gut",
      "rating_value": 1.0
    }
  ],
  "total": 1
}
```

### DELETE `/api/feedback/{filename}`
Löscht ein gespeichertes Feedback.

**Beispiel:**
```javascript
DELETE /api/feedback/pos_1763573378.912667.json
```

**Response:**
```json
{
  "success": true,
  "message": "Feedback pos_1763573378.912667.json deleted"
}
```

**Hinweis:** Der Endpoint unterstützt Filenames mit und ohne `.json`-Extension.

## Speicherort

Alle Feedbacks werden gespeichert in:
```
feedback/training_feedback/*.json
```

## Implementierung

### Backend-Routen
- **Datei**: `charts/routes/review.py`
- **Funktionen**:
  - `feedback_list_page()` - Line 26-29
  - `get_feedback_list()` - Line 31-67
  - `delete_feedback(filename)` - Line 69-94

### Frontend
- **HTML**: `templates/feedback-list.html`
- **JavaScript-Funktionen**:
  - `loadFeedbacks()` - Line 293-322
  - `renderFeedbacks()` - Line 324-332
  - `createFeedbackItem(feedback)` - Line 334-393
  - `deleteFeedback(filename)` - Line 417-439

### Chart-Integration
- **Datei**: `templates/chart.html`
- **Navigation Button**: Line 494
- **User Account Button**: Line 607-612

## Bugfixes

### Problem: Fehler beim Löschen von Dateien mit `.json` im Namen
**Symptom:**
- Fehler "undefined" beim Löschen von Feedbacks
- Betraf Files wie `ai_training_20251108_233217_1.json`

**Ursache:**
- Endpoint fügte immer `.json` hinzu → `filename.json.json`

**Fix:**
```python
# Vor dem Fix:
feedback_file = feedback_dir / f"{trade_id}.json"

# Nach dem Fix:
if not filename.endswith('.json'):
    feedback_file = feedback_dir / f"{filename}.json"
else:
    feedback_file = feedback_dir / filename
```

**Zusätzliche Fixes:**
- Parameter von `trade_id` → `filename` umbenannt
- Frontend sendet `feedback.filename` statt `feedback.trade_id`
- `encodeURIComponent()` für sichere URL-Übertragung

## Use Case

1. **User handelt** einen Trade (manuell oder während Playback)
2. **Trade wird geschlossen** (TP/SL erreicht)
3. **Feedback-Modal erscheint** automatisch
4. **User bewertet** den Trade (👍👍/👍/😐/👎/👎👎)
5. **Feedback wird gespeichert** in `feedback/training_feedback/`
6. **User öffnet Feedback-Liste** via Button
7. **User kann Feedback einsehen** und bei Bedarf löschen

## Vorteile

- ✅ **Übersichtliche Verwaltung** aller Trade-Bewertungen
- ✅ **Fehlerkorrektur möglich** (falsche Bewertungen löschen)
- ✅ **Transparenz** über gespeicherte Daten
- ✅ **Einfacher Zugriff** via 2 prominente Buttons
- ✅ **Automatisches Reload** nach Änderungen

## Zukünftige Erweiterungen

Mögliche Features:
- **Filterung** nach Rating (nur "Sehr gut" anzeigen)
- **Sortierung** nach PnL, Timestamp, etc.
- **Statistiken** (Durchschnittliches Rating, PnL-Verteilung)
- **Export** aller Feedbacks als CSV
- **Batch-Delete** (mehrere Feedbacks auf einmal löschen)
- **Edit-Funktion** (Rating nachträglich ändern)
