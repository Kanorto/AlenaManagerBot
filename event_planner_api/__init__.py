"""
Top‑level package for the Event Planner API.

This file makes ``event_planner_api`` a Python package so that
modules within ``app`` can be imported using fully qualified names
like ``event_planner_api.app.main``.  Without this marker file,
Python would treat the directory as a plain folder and import
resolution for ``event_planner_api`` would fail when running tests
outside of the package root.

The package provides no public exports; all functionality lives in
submodules under ``app``.
"""

__all__ = []