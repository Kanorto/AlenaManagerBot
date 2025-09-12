"""
API package containing versioned routes.

This package groups API versions under subpackages such as ``v1``.  A
version subpackage typically exposes a top‑level ``router`` which
includes all of its domain‑specific endpoints.  New versions can be
added by creating a new subpackage (e.g. ``v2``) with its own
``router``.
"""