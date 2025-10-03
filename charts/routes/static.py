"""
Static Routes - Statische Dateien und HTML-Seiten
REFACTOR PHASE 5: Extrahiert aus chart_server.py
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Router-Instanz
router = APIRouter(tags=["static"])


def setup_static_routes(app):
    """
    Registriert Static-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
    """

    @router.get("/", response_class=HTMLResponse)
    async def serve_chart_page():
        """Serviert Haupt-Chart HTML-Seite"""
        html_path = Path("templates/chart.html")

        if not html_path.exists():
            return HTMLResponse(
                content="<h1>Chart Server</h1><p>Template nicht gefunden</p>",
                status_code=404
            )

        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return HTMLResponse(content=html_content)


    @router.get("/favicon.ico")
    async def get_favicon():
        """Serviert Favicon (verhindert 404-Fehler)"""
        favicon_path = Path("static/favicon.ico")

        if favicon_path.exists():
            return FileResponse(favicon_path)

        # Fallback: leere Antwort
        return HTMLResponse(content="", status_code=204)


    # Mount static files directory (falls vorhanden)
    static_path = Path("static")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")
        print("[PHASE 5] Static files mounted: /static")


    # Registriere Router an App
    app.include_router(router)

    print("[PHASE 5] Static-Router registriert ✅")
