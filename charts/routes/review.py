"""
Trade Review Routes
Endpoints für Trade-Review nach Training
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
import pickle
import json
from typing import List, Dict, Optional
import hashlib
import pandas as pd

def setup_review_routes(app):
    """Setup Review Routes"""

    @app.get('/review', tags=["review"])
    async def review_page():
        """Trade Review Page"""
        with open('templates/review.html', 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())

    @app.get('/feedback-list', tags=["feedback"])
    async def feedback_list_page():
        """User Feedback List Page"""
        with open('templates/feedback-list.html', 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())

    @app.get('/api/feedback/list', tags=["feedback"])
    async def get_feedback_list():
        """Get all saved user feedbacks"""
        try:
            feedback_dir = Path('feedback/training_feedback')
            if not feedback_dir.exists():
                return {'success': True, 'feedbacks': []}

            feedbacks = []
            for feedback_file in sorted(feedback_dir.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    with open(feedback_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        feedbacks.append({
                            'filename': feedback_file.name,
                            'trade_id': data.get('trade_id'),
                            'timestamp': data.get('timestamp'),
                            'action': data.get('action'),
                            'entry_price': data.get('entry_price'),
                            'exit_price': data.get('exit_price'),
                            'pnl': data.get('pnl'),
                            'rating': data.get('human_evaluation', {}).get('rating'),
                            'rating_label': data.get('human_evaluation', {}).get('rating_label'),
                            'rating_value': data.get('human_evaluation', {}).get('rating_value')
                        })
                except Exception as e:
                    print(f"[Feedback] Error loading {feedback_file}: {e}")
                    continue

            return {
                'success': True,
                'feedbacks': feedbacks,
                'total': len(feedbacks)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete('/api/feedback/{filename}', tags=["feedback"])
    async def delete_feedback(filename: str):
        """Delete a saved feedback by filename"""
        try:
            feedback_dir = Path('feedback/training_feedback')

            # Filename could already have .json extension or not
            if not filename.endswith('.json'):
                feedback_file = feedback_dir / f"{filename}.json"
            else:
                feedback_file = feedback_dir / filename

            if not feedback_file.exists():
                raise HTTPException(status_code=404, detail=f'Feedback not found: {feedback_file}')

            feedback_file.unlink()

            return {
                'success': True,
                'message': f'Feedback {filename} deleted'
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


    @app.get('/review/trades', tags=["review"])
    async def get_review_trades(
        n: int = 10,
        mode: str = 'mixed',
        training_log: Optional[str] = None
    ):
        """
        Lädt TOP N Trades aus Training für Review

        Query Params:
            - training_log: Pfad zum Training-Log (optional)
            - n: Anzahl Trades (default: 10)
            - mode: best/worst/mixed (default: mixed)

        Returns:
            JSON mit Trade-Liste
        """
        try:
            # Find latest training log if not specified
            if not training_log:
                training_log = _find_latest_training_log()

            if not training_log:
                raise HTTPException(status_code=404, detail='No training log found')

            # Load trades from log
            trades = _load_trades_from_log(training_log)

            if not trades:
                raise HTTPException(status_code=404, detail='No trades found in log')

            # Select TOP N
            selected_trades = _select_top_trades(trades, n, mode)

            # Format for frontend
            formatted_trades = []
            for idx, trade in enumerate(selected_trades):
                formatted_trades.append({
                    'id': f"trade_{idx:04d}",
                    'timestamp': trade.get('timestamp', ''),
                    'step': trade.get('step', 0),
                    'action': trade.get('action', 'unknown'),
                    'entry_price': trade.get('entry_price', 0),
                    'sl_price': trade.get('sl_price', 0),
                    'tp_price': trade.get('tp_price', 0),
                    'pnl': trade.get('pnl', 0),
                    'shares': trade.get('shares', 0),
                    'state_hash': _generate_state_hash(trade)
                })

            return {
                'success': True,
                'trades': formatted_trades,
                'total': len(formatted_trades),
                'mode': mode,
                'training_log': str(training_log)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get('/review/candles/{trade_timestamp}', tags=["review"])
    async def get_trade_candles(trade_timestamp: str, candles_before: int = 25, candles_after: int = 25):
        """
        Lädt historische Kerzen rund um einen Trade

        Args:
            trade_timestamp: ISO timestamp des Trades (z.B. "2024-01-02 00:20:00")
            candles_before: Anzahl Kerzen vor dem Trade (default: 25)
            candles_after: Anzahl Kerzen nach dem Trade (default: 25)

        Returns:
            JSON mit Candle-Daten im Lightweight Charts Format
        """
        try:
            # Load 5m candle data
            data_path = Path('src/data/aggregated/5m/nq-2024.csv')
            if not data_path.exists():
                raise HTTPException(status_code=404, detail='Candle data not found')

            df = pd.read_csv(data_path)
            df.columns = [col.lower() for col in df.columns]

            # Assume first column is timestamp
            time_col = df.columns[0]
            df[time_col] = pd.to_datetime(df[time_col])
            df = df.sort_values(time_col).reset_index(drop=True)

            # Parse trade timestamp
            trade_time = pd.to_datetime(trade_timestamp)

            # Find nearest index
            time_diff = (df[time_col] - trade_time).abs()
            idx = time_diff.idxmin()

            # Get candles around trade
            start_idx = max(0, idx - candles_before)
            end_idx = min(len(df), idx + candles_after + 1)

            candles_df = df.iloc[start_idx:end_idx]

            # Format for Lightweight Charts
            candles = []
            for _, row in candles_df.iterrows():
                candles.append({
                    'time': int(row[time_col].timestamp()),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close'])
                })

            return {
                'success': True,
                'candles': candles,
                'trade_index': idx - start_idx,
                'total': len(candles)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class FeedbackSubmission(BaseModel):
        trade_id: str
        state_hash: str
        action: Optional[str] = None
        feedback: Dict
        notes: Optional[str] = ""

    @app.post('/review/feedback', tags=["review"])
    async def submit_feedback(submission: FeedbackSubmission):
        """
        Speichert User-Feedback für einen Trade

        Body:
            {
                "trade_id": "trade_0001",
                "state_hash": "abc123",
                "action": "buy",
                "feedback": {
                    "entry_timing": 0.8,      // 0-1
                    "sl_tp_placement": 1.0,
                    "pattern_quality": 0.4
                },
                "notes": "Entry war gut..."
            }

        Returns:
            Success confirmation
        """
        try:
            trade_id = submission.trade_id
            state_hash = submission.state_hash
            feedback = submission.feedback
            notes = submission.notes

            # Validate
            if not trade_id or not feedback:
                raise HTTPException(status_code=400, detail='Missing trade_id or feedback')

            # Save feedback
            feedback_path = Path('feedback') / 'criterion_feedback.json'
            feedback_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing feedback
            if feedback_path.exists():
                with open(feedback_path, 'r') as f:
                    all_feedback = json.load(f)
            else:
                all_feedback = {'reviews': []}

            # Add new feedback
            all_feedback['reviews'].append({
                'trade_id': trade_id,
                'state_hash': state_hash,
                'feedback': feedback,
                'notes': notes,
                'timestamp': str(pd.Timestamp.now())
            })

            # Save
            with open(feedback_path, 'w') as f:
                json.dump(all_feedback, f, indent=2)

            return {
                'success': True,
                'message': 'Feedback saved',
                'total_reviews': len(all_feedback['reviews'])
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


def _find_latest_training_log():
    """Findet den neuesten Training-Log"""
    # Check common locations
    log_dir = Path('src/training_logs')

    if not log_dir.exists():
        # Try alternate location
        log_dir = Path('training_logs')

    if not log_dir.exists():
        return None

    # Find latest pickle file
    log_files = list(log_dir.glob('*.pkl'))
    if not log_files:
        return None

    # Sort by modification time
    latest = max(log_files, key=lambda p: p.stat().st_mtime)
    return latest


def _load_trades_from_log(log_path: Path) -> List[Dict]:
    """Lädt Trades aus Training-Log"""
    try:
        with open(log_path, 'rb') as f:
            data = pickle.load(f)

        # Extract trades
        if isinstance(data, dict):
            trades = data.get('trades', [])
        elif isinstance(data, list):
            trades = data
        else:
            trades = []

        return trades

    except Exception as e:
        print(f"[Review] Error loading trades: {e}")
        return []


def _select_top_trades(trades: List[Dict], n: int, mode: str) -> List[Dict]:
    """Wählt TOP N Trades basierend auf Modus"""

    if mode == 'best':
        # Beste PnL
        sorted_trades = sorted(trades, key=lambda t: t.get('pnl', 0), reverse=True)
        return sorted_trades[:n]

    elif mode == 'worst':
        # Schlechteste PnL
        sorted_trades = sorted(trades, key=lambda t: t.get('pnl', 0))
        return sorted_trades[:n]

    elif mode == 'mixed':
        # 50% beste, 50% schlechteste
        half = n // 2
        sorted_trades = sorted(trades, key=lambda t: t.get('pnl', 0), reverse=True)
        best = sorted_trades[:half]
        worst = sorted_trades[-half:][::-1]  # Reverse to get worst first
        return best + worst

    else:
        # Default: first N
        return trades[:n]


def _generate_state_hash(trade: Dict) -> str:
    """Generiert State-Hash für Trade"""
    # Hash basierend auf step + price
    state_str = f"{trade.get('step', 0)}_{trade.get('entry_price', 0)}"
    return hashlib.md5(state_str.encode()).hexdigest()[:8]
