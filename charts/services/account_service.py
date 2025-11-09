"""
Account Service für Chart Server
Verwaltet separate Accounts für RL-KI und Nutzer mit Trade Execution
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AccountService:
    """
    Service für Account Management mit Trade Execution

    Verwaltet zwei separate Accounts:
    - ai_account: Für RL-KI Trades (wenn RL online)
    - user_account: Für manuell Nutzer Trades (wenn RL offline)
    """

    def __init__(self, ai_balance: float = 500000.0, user_balance: float = 500000.0):
        """
        Initialisiert AccountService mit Startkapital

        Args:
            ai_balance: Start-Balance für RL-KI Account (default: 500k)
            user_balance: Start-Balance für Nutzer Account (default: 500k)
        """

        # RL-KI Account
        self.ai_account = {
            'balance': float(ai_balance),  # Startkapital in EUR
            'realized_pnl': 0.0,           # Realisierte Gewinne/Verluste
            'unrealized_pnl': 0.0,         # Unrealisierte Gewinne/Verluste
            'active_positions': {},        # {position_id: position_data}
            'closed_positions': [],        # Historie geschlossener Positionen
            'total_trades': 0,             # Anzahl Trades
            'winning_trades': 0,           # Anzahl Gewinn-Trades
            'losing_trades': 0             # Anzahl Verlust-Trades
        }

        # Nutzer Account
        self.user_account = {
            'balance': float(user_balance), # Startkapital in EUR
            'realized_pnl': 0.0,           # Realisierte Gewinne/Verluste
            'unrealized_pnl': 0.0,         # Unrealisierte Gewinne/Verluste
            'active_positions': {},        # {position_id: position_data}
            'closed_positions': [],        # Historie geschlossener Positionen
            'total_trades': 0,             # Anzahl Trades
            'winning_trades': 0,           # Anzahl Gewinn-Trades
            'losing_trades': 0             # Anzahl Verlust-Trades
        }

        logger.info(f"[AccountService] Initialized - AI: {ai_balance:,.0f}€, User: {user_balance:,.0f}€")

    def execute_trade(self,
                     position_data: Dict[str, Any],
                     is_rl_online: bool) -> Dict[str, Any]:
        """
        Führt Trade aus und weist ihn dem richtigen Account zu

        Args:
            position_data: Position-Daten (entry, sl, tp, direction, size, etc.)
            is_rl_online: True wenn RL online (→ ai_account), False wenn offline (→ user_account)

        Returns:
            Dict mit success, position_id, account_type, account_summary
        """
        account_type = 'ai' if is_rl_online else 'user'
        account = self.ai_account if is_rl_online else self.user_account

        position_id = position_data.get('id', f"pos_{datetime.now().timestamp()}")

        # Füge Position zum Account hinzu
        account['active_positions'][position_id] = {
            **position_data,
            'account_type': account_type,  # ← BUGFIX: Wird für SL/TP Auto-Close benötigt
            'opened_at': datetime.now().isoformat(),
            'unrealized_pnl': 0.0
        }

        account['total_trades'] += 1

        logger.info(f"[AccountService] Trade executed on {account_type} account: {position_id}")
        logger.info(f"[AccountService] Direction: {position_data.get('direction')}, "
                   f"Entry: {position_data.get('entry_price')}, "
                   f"Size: {position_data.get('size')}")

        return {
            'success': True,
            'position_id': position_id,
            'account_type': account_type,
            'account_summary': self.get_account_summary(account_type)
        }

    def update_position_pnl(self,
                           position_id: str,
                           current_price: float,
                           account_type: str = None) -> Dict[str, Any]:
        """
        Aktualisiert unrealized PnL für eine offene Position

        Args:
            position_id: Position ID
            current_price: Aktueller Marktpreis
            account_type: 'ai' oder 'user' (optional, sucht automatisch wenn None)

        Returns:
            Dict mit success, position_id, unrealized_pnl, account_summary
        """
        # Finde Position in beiden Accounts wenn account_type nicht angegeben
        if account_type is None:
            if position_id in self.ai_account['active_positions']:
                account_type = 'ai'
            elif position_id in self.user_account['active_positions']:
                account_type = 'user'
            else:
                return {
                    'success': False,
                    'error': f'Position {position_id} not found in any account'
                }

        account = self.ai_account if account_type == 'ai' else self.user_account

        if position_id not in account['active_positions']:
            return {
                'success': False,
                'error': f'Position {position_id} not found in {account_type} account'
            }

        position = account['active_positions'][position_id]

        # Berechne PnL basierend auf Direction
        entry_price = position['entry_price']
        size = position['size']
        direction = position['direction']

        if direction == 'long':
            pnl = (current_price - entry_price) * size
        else:  # short
            pnl = (entry_price - current_price) * size

        # Update Position PnL
        position['unrealized_pnl'] = pnl
        position['last_price'] = current_price
        position['last_update'] = datetime.now().isoformat()

        # Update Account Unrealized PnL (Summe aller offenen Positionen)
        total_unrealized = sum(
            pos['unrealized_pnl']
            for pos in account['active_positions'].values()
        )
        account['unrealized_pnl'] = total_unrealized

        return {
            'success': True,
            'position_id': position_id,
            'unrealized_pnl': pnl,
            'account_type': account_type,
            'account_summary': self.get_account_summary(account_type)
        }

    def close_position(self,
                      position_id: str,
                      close_price: float,
                      close_reason: str = 'manual',
                      account_type: str = None) -> Dict[str, Any]:
        """
        Schließt Position und realisiert PnL

        Args:
            position_id: Position ID
            close_price: Schließ-Preis
            close_reason: Grund ('manual', 'stop_loss', 'take_profit')
            account_type: 'ai' oder 'user' (optional, sucht automatisch)

        Returns:
            Dict mit success, realized_pnl, close_reason, account_summary
        """
        # Finde Position
        if account_type is None:
            if position_id in self.ai_account['active_positions']:
                account_type = 'ai'
            elif position_id in self.user_account['active_positions']:
                account_type = 'user'
            else:
                return {
                    'success': False,
                    'error': f'Position {position_id} not found'
                }

        account = self.ai_account if account_type == 'ai' else self.user_account

        if position_id not in account['active_positions']:
            return {
                'success': False,
                'error': f'Position {position_id} not found in {account_type} account'
            }

        position = account['active_positions'][position_id]

        # Berechne finales PnL
        entry_price = position['entry_price']
        size = position['size']
        direction = position['direction']

        if direction == 'long':
            realized_pnl = (close_price - entry_price) * size
        else:  # short
            realized_pnl = (entry_price - close_price) * size

        # Update Account
        account['balance'] += realized_pnl
        account['realized_pnl'] += realized_pnl

        # Update Statistics
        if realized_pnl > 0:
            account['winning_trades'] += 1
        else:
            account['losing_trades'] += 1

        # Move to closed positions
        closed_position = {
            **position,
            'closed_at': datetime.now().isoformat(),
            'close_price': close_price,
            'close_reason': close_reason,
            'realized_pnl': realized_pnl
        }
        account['closed_positions'].append(closed_position)

        # Remove from active positions
        del account['active_positions'][position_id]

        # Recalculate unrealized PnL
        total_unrealized = sum(
            pos['unrealized_pnl']
            for pos in account['active_positions'].values()
        )
        account['unrealized_pnl'] = total_unrealized

        logger.info(f"[AccountService] Position closed on {account_type} account: {position_id}")
        logger.info(f"[AccountService] Realized PnL: {realized_pnl:+.2f}€, Reason: {close_reason}")

        return {
            'success': True,
            'position_id': position_id,
            'realized_pnl': realized_pnl,
            'close_reason': close_reason,
            'account_type': account_type,
            'account_summary': self.get_account_summary(account_type)
        }

    def get_account_summary(self, account_type: str) -> Dict[str, Any]:
        """
        Gibt Account-Summary zurück

        Args:
            account_type: 'ai' oder 'user'

        Returns:
            Dict mit balance, realized_pnl, unrealized_pnl, etc.
        """
        account = self.ai_account if account_type == 'ai' else self.user_account

        total_equity = account['balance'] + account['unrealized_pnl']
        win_rate = 0.0
        if account['total_trades'] > 0:
            win_rate = (account['winning_trades'] / account['total_trades']) * 100

        return {
            'balance': account['balance'],
            'realized_pnl': account['realized_pnl'],
            'unrealized_pnl': account['unrealized_pnl'],
            'total_equity': total_equity,
            'active_positions_count': len(account['active_positions']),
            'total_trades': account['total_trades'],
            'winning_trades': account['winning_trades'],
            'losing_trades': account['losing_trades'],
            'win_rate': win_rate
        }

    def get_all_accounts_summary(self) -> Dict[str, Any]:
        """
        Gibt Summary beider Accounts zurück

        Returns:
            Dict mit ai_account und user_account summaries
        """
        return {
            'ai_account': self.get_account_summary('ai'),
            'user_account': self.get_account_summary('user')
        }

    def get_active_positions(self, account_type: str = None) -> List[Dict[str, Any]]:
        """
        Gibt aktive Positionen zurück

        Args:
            account_type: 'ai', 'user' oder None (beide)

        Returns:
            Liste von Positions-Dicts
        """
        if account_type == 'ai':
            return list(self.ai_account['active_positions'].values())
        elif account_type == 'user':
            return list(self.user_account['active_positions'].values())
        else:
            # Beide Accounts
            ai_positions = [
                {**pos, 'account_type': 'ai'}
                for pos in self.ai_account['active_positions'].values()
            ]
            user_positions = [
                {**pos, 'account_type': 'user'}
                for pos in self.user_account['active_positions'].values()
            ]
            return ai_positions + user_positions

    def reset_account(self, account_type: str) -> Dict[str, Any]:
        """
        Setzt Account auf Startwerte zurück

        Args:
            account_type: 'ai' oder 'user'

        Returns:
            Dict mit success, account_summary
        """
        account = self.ai_account if account_type == 'ai' else self.user_account

        account.update({
            'balance': 500000.0,
            'realized_pnl': 0.0,
            'unrealized_pnl': 0.0,
            'active_positions': {},
            'closed_positions': [],
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0
        })

        logger.info(f"[AccountService] {account_type} account reset to default values")

        return {
            'success': True,
            'account_type': account_type,
            'account_summary': self.get_account_summary(account_type)
        }

    def set_balance(self, account_type: str, new_balance: float) -> Dict[str, Any]:
        """
        Setzt Balance für einen Account (nur wenn keine offenen Positionen)

        Args:
            account_type: 'ai' oder 'user'
            new_balance: Neue Balance in EUR

        Returns:
            Dict mit success, error (falls vorhanden), account_summary
        """
        account = self.ai_account if account_type == 'ai' else self.user_account

        # Validierung: Keine Balance-Änderung bei offenen Positionen
        if len(account['active_positions']) > 0:
            error_msg = f"Balance kann nicht geändert werden: {len(account['active_positions'])} offene Position(en) vorhanden"
            logger.warning(f"[AccountService] {error_msg} ({account_type})")
            return {
                'success': False,
                'error': error_msg,
                'active_positions_count': len(account['active_positions'])
            }

        # Balance setzen
        old_balance = account['balance']
        account['balance'] = float(new_balance)

        logger.info(f"[AccountService] {account_type} balance updated: {old_balance:,.0f}€ → {new_balance:,.0f}€")

        return {
            'success': True,
            'account_type': account_type,
            'old_balance': old_balance,
            'new_balance': new_balance,
            'account_summary': self.get_account_summary(account_type)
        }

    def has_active_positions(self) -> Dict[str, Any]:
        """
        Prüft ob irgendein Account offene Positionen hat

        Returns:
            Dict mit has_positions, ai_count, user_count
        """
        ai_count = len(self.ai_account['active_positions'])
        user_count = len(self.user_account['active_positions'])
        total = ai_count + user_count

        return {
            'has_positions': total > 0,
            'total_count': total,
            'ai_count': ai_count,
            'user_count': user_count
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialisiert AccountService State für Persistierung

        Returns:
            Dict mit ai_account und user_account State
        """
        return {
            'ai_account': {
                'balance': self.ai_account['balance'],
                'realized_pnl': self.ai_account['realized_pnl'],
                'unrealized_pnl': self.ai_account['unrealized_pnl'],
                'active_positions': dict(self.ai_account['active_positions']),
                'closed_positions': list(self.ai_account['closed_positions']),
                'total_trades': self.ai_account['total_trades'],
                'winning_trades': self.ai_account['winning_trades'],
                'losing_trades': self.ai_account['losing_trades']
            },
            'user_account': {
                'balance': self.user_account['balance'],
                'realized_pnl': self.user_account['realized_pnl'],
                'unrealized_pnl': self.user_account['unrealized_pnl'],
                'active_positions': dict(self.user_account['active_positions']),
                'closed_positions': list(self.user_account['closed_positions']),
                'total_trades': self.user_account['total_trades'],
                'winning_trades': self.user_account['winning_trades'],
                'losing_trades': self.user_account['losing_trades']
            }
        }

    def load_from_dict(self, state: Dict[str, Any]) -> bool:
        """
        Lädt AccountService State aus persistiertem Dict

        Args:
            state: Dict mit ai_account und user_account State

        Returns:
            True wenn erfolgreich geladen
        """
        try:
            # AI Account laden
            if 'ai_account' in state:
                ai_state = state['ai_account']
                self.ai_account['balance'] = float(ai_state.get('balance', 500000.0))
                self.ai_account['realized_pnl'] = float(ai_state.get('realized_pnl', 0.0))
                self.ai_account['unrealized_pnl'] = float(ai_state.get('unrealized_pnl', 0.0))
                self.ai_account['active_positions'] = dict(ai_state.get('active_positions', {}))
                self.ai_account['closed_positions'] = list(ai_state.get('closed_positions', []))
                self.ai_account['total_trades'] = int(ai_state.get('total_trades', 0))
                self.ai_account['winning_trades'] = int(ai_state.get('winning_trades', 0))
                self.ai_account['losing_trades'] = int(ai_state.get('losing_trades', 0))

            # User Account laden
            if 'user_account' in state:
                user_state = state['user_account']
                self.user_account['balance'] = float(user_state.get('balance', 500000.0))
                self.user_account['realized_pnl'] = float(user_state.get('realized_pnl', 0.0))
                self.user_account['unrealized_pnl'] = float(user_state.get('unrealized_pnl', 0.0))
                self.user_account['active_positions'] = dict(user_state.get('active_positions', {}))
                self.user_account['closed_positions'] = list(user_state.get('closed_positions', []))
                self.user_account['total_trades'] = int(user_state.get('total_trades', 0))
                self.user_account['winning_trades'] = int(user_state.get('winning_trades', 0))
                self.user_account['losing_trades'] = int(user_state.get('losing_trades', 0))

            logger.info(f"[AccountService] State geladen - AI Positions: {len(self.ai_account['active_positions'])}, "
                       f"User Positions: {len(self.user_account['active_positions'])}")
            return True

        except Exception as e:
            logger.error(f"[AccountService] Fehler beim Laden des State: {e}")
            return False
