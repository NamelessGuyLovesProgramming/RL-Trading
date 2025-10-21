"""
Account Routes - API Endpoints für Account Management
Verwaltet AI & User Account Status und Trades
"""

from fastapi import APIRouter
from typing import Dict, Any

# Router-Instanz
router = APIRouter(prefix="/api/account", tags=["account"])


def setup_account_routes(app, account_service):
    """
    Registriert Account-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
        account_service: AccountService-Instanz
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

    # Router registrieren
    app.include_router(router)
