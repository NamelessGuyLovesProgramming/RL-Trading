"""
Account Service für RL Trading
Verwaltet separate Account-States für KI und Nutzer
"""

class AccountService:
    def __init__(self):
        # RL-KI Account State
        self.ai_account = {
            'balance': 500000.0,           # Startkapital in EUR
            'realized_pnl': 0.0,           # Realisierte Gewinne/Verluste
            'unrealized_pnl': 0.0,         # Unrealisierte Gewinne/Verluste
            'active_positions': [],        # Aktive Positionen der KI
            'total_trades': 0,             # Anzahl Trades
            'win_rate': 0.0,              # Gewinnrate in %
            'max_drawdown': 0.0           # Maximaler Drawdown
        }

        # Nutzer Account State
        self.user_account = {
            'balance': 500000.0,           # Startkapital in EUR
            'realized_pnl': 0.0,           # Realisierte Gewinne/Verluste
            'unrealized_pnl': 0.0,         # Unrealisierte Gewinne/Verluste
            'active_positions': [],        # Aktive Positionen des Nutzers
            'total_trades': 0,             # Anzahl Trades
            'win_rate': 0.0,              # Gewinnrate in %
            'max_drawdown': 0.0           # Maximaler Drawdown
        }

    def get_ai_account_summary(self):
        """Gibt Account-Summary der KI zurück"""
        return {
            'balance': f"{self.ai_account['balance']:,.0f}€",
            'realized_pnl': f"{self.ai_account['realized_pnl']:+,.0f}€",
            'unrealized_pnl': f"{self.ai_account['unrealized_pnl']:+,.0f}€",
            'total_equity': f"{self.ai_account['balance'] + self.ai_account['unrealized_pnl']:,.0f}€"
        }

    def get_user_account_summary(self):
        """Gibt Account-Summary des Nutzers zurück"""
        return {
            'balance': f"{self.user_account['balance']:,.0f}€",
            'realized_pnl': f"{self.user_account['realized_pnl']:+,.0f}€",
            'unrealized_pnl': f"{self.user_account['unrealized_pnl']:+,.0f}€",
            'total_equity': f"{self.user_account['balance'] + self.user_account['unrealized_pnl']:,.0f}€"
        }

    def update_ai_position(self, position_pnl):
        """Aktualisiert KI Position PnL"""
        self.ai_account['unrealized_pnl'] = position_pnl

    def update_user_position(self, position_pnl):
        """Aktualisiert Nutzer Position PnL"""
        self.user_account['unrealized_pnl'] = position_pnl

    def close_ai_position(self, realized_pnl):
        """Schließt KI Position und realisiert PnL"""
        self.ai_account['realized_pnl'] += realized_pnl
        self.ai_account['balance'] += realized_pnl
        self.ai_account['unrealized_pnl'] = 0.0
        self.ai_account['total_trades'] += 1

    def close_user_position(self, realized_pnl):
        """Schließt Nutzer Position und realisiert PnL"""
        self.user_account['realized_pnl'] += realized_pnl
        self.user_account['balance'] += realized_pnl
        self.user_account['unrealized_pnl'] = 0.0
        self.user_account['total_trades'] += 1

# Globale Instanz für das Chart System
account_service = AccountService()