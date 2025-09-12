"""
Endpoint subpackage for API v1.

Each module in this package defines an APIRouter for a specific
domain (e.g. events, users, payments).  The routers are aggregated in
``router.py`` at the package level and then included in the main
application.
"""