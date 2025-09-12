"""
Application package initializer.

This package contains the main entrypoint for the API and all of its
submodules.  The project is organised into logical pieces to avoid
creating a single monolithic codebase.  Each domain (events, users,
payments, etc.) lives in its own subpackage and exposes a router
defined in ``api/v1/endpoints``.  Versioning is handled by grouping
routers under the ``api/<version>/`` hierarchy.

The application is designed for extensibility; additional versions or
new domains can be added without breaking existing functionality.
"""

from .main import app  # noqa: F401