"""
Routes Package - FastAPI Route Modules
Organisiert API-Endpoints in separate Router
"""

from . import debug
from . import chart
from . import static

__all__ = [
    'debug',
    'chart',
    'static'
]
