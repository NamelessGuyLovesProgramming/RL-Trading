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


@router.get("/", response_class=HTMLResponse)
async def serve_chart_page():
    """
    Serviert Haupt-Chart HTML-Seite

    Phase 9: Svelte Frontend Integration
    - Versucht zuerst Svelte-Build zu laden (static/index.html)
    - Fallback: Legacy Template (templates/chart.html)
    """
    # Phase 9: Versuche Svelte-Build zu servieren
    svelte_path = Path("static/index.html")
    if svelte_path.exists():
        print("[PHASE 9] Serving Svelte Frontend ✨")
        with open(svelte_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())

    # Fallback: Legacy Template
    legacy_path = Path("templates/chart.html")
    if legacy_path.exists():
        print("[LEGACY] Serving Legacy HTML Template")
        with open(legacy_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())

    # No frontend available
    return HTMLResponse(
        content="""
        <h1>Chart Server 2.0</h1>
        <p>No frontend available</p>
        <p>Run: <code>cd frontend && npm run build</code></p>
        """,
        status_code=404
    )


@router.get("/favicon.ico")
async def get_favicon():
    """Serviert Favicon (verhindert 404-Fehler)"""
    favicon_path = Path("static/favicon.ico")

    if favicon_path.exists():
        return FileResponse(favicon_path)

    # Fallback: leere Antwort
    return HTMLResponse(content="", status_code=204)


def setup_static_routes(app):
    """
    Registriert Static-Routes am FastAPI App

    Args:
        app: FastAPI App-Instanz
    """
    # Mount static files directory (falls vorhanden)
    static_path = Path("static")
    if static_path.exists():
        app.mount("/static", StaticFiles(directory="static"), name="static")
        print("[PHASE 5] Static files mounted: /static")

    # Registriere Router an App
    app.include_router(router)

    print("[PHASE 5] Static-Router registriert ✅")
