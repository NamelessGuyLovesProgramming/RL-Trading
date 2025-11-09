"""
Account Routes - API Endpoints für Account Management
Verwaltet AI & User Account Status und Trades
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Router-Instanz
router = APIRouter(prefix="/api/account", tags=["account"])


class UpdateBalanceRequest(BaseModel):
    """Request Model für Balance-Update"""
    ai_balance: Optional[float] = None
    user_balance: Optional[float] = None


def setup_account_routes(app, account_service, config_service):
    """
    Registriert Account-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
        account_service: AccountService-Instanz
        config_service: ConfigService-Instanz
    """

    @router.get("/status")
    async def get_account_status() -> Dict[str, Any]:
        """
        GET /api/account/status

        Gibt Account-Status für beide Accounts zurück (AI & User)

        Returns:
            {
                "status": "success",
                "ai_account": {...},
                "user_account": {...}
            }
        """
        try:
            summary = account_service.get_all_accounts_summary()

            return {
                "status": "success",
                "ai_account": summary["ai_account"],
                "user_account": summary["user_account"]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Fehler beim Laden der Account-Daten: {str(e)}"
            }

    @router.get("/positions")
    async def get_active_positions() -> Dict[str, Any]:
        """
        GET /api/account/positions

        Gibt alle aktiven Positionen zurück (AI & User)

        Returns:
            {
                "status": "success",
                "positions": [
                    {
                        "id": "pos_123",
                        "entry_price": 17500.0,
                        "sl_price": 17450.0,
                        "tp_price": 17600.0,
                        "direction": "long",
                        "account_type": "user",
                        "unrealized_pnl": 50.0,
                        ...
                    }
                ]
            }
        """
        try:
            # Hole alle aktiven Positionen (beide Accounts)
            positions = account_service.get_active_positions()

            return {
                "status": "success",
                "positions": positions,
                "count": len(positions)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Fehler beim Laden der Positionen: {str(e)}"
            }

    @router.post("/update-balance")
    async def update_balance(request: UpdateBalanceRequest) -> Dict[str, Any]:
        """
        POST /api/account/update-balance

        Aktualisiert Account-Balances (nur wenn keine offenen Positionen)

        Request Body:
            {
                "ai_balance": 100000,    # Optional
                "user_balance": 200000   # Optional
            }

        Returns:
            {
                "status": "success",
                "ai_account": {...},
                "user_account": {...}
            }
        """
        try:
            # Prüfe ob offene Positionen vorhanden
            positions_check = account_service.has_active_positions()
            if positions_check['has_positions']:
                return {
                    "status": "error",
                    "message": f"Balance kann nicht geändert werden: {positions_check['total_count']} offene Position(en) vorhanden",
                    "active_positions": {
                        "ai_count": positions_check['ai_count'],
                        "user_count": positions_check['user_count'],
                        "total": positions_check['total_count']
                    }
                }

            results = {}

            # Update AI Balance
            if request.ai_balance is not None:
                ai_result = account_service.set_balance('ai', request.ai_balance)
                if not ai_result['success']:
                    return {
                        "status": "error",
                        "message": ai_result.get('error', 'Fehler beim Setzen der AI Balance')
                    }
                results['ai'] = ai_result

                # Speichere in Config
                config_service.update_account_balances(ai_balance=request.ai_balance)

            # Update User Balance
            if request.user_balance is not None:
                user_result = account_service.set_balance('user', request.user_balance)
                if not user_result['success']:
                    return {
                        "status": "error",
                        "message": user_result.get('error', 'Fehler beim Setzen der User Balance')
                    }
                results['user'] = user_result

                # Speichere in Config
                config_service.update_account_balances(user_balance=request.user_balance)

            # Hole aktualisierte Account-Summaries
            summary = account_service.get_all_accounts_summary()

            return {
                "status": "success",
                "message": "Balance erfolgreich aktualisiert",
                "ai_account": summary["ai_account"],
                "user_account": summary["user_account"]
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Fehler beim Aktualisieren der Balance: {str(e)}"
            }

    # Router registrieren
    app.include_router(router)
