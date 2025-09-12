"""
Pydantic schema definitions for API payloads.

Each domain (users, events, payments, etc.) defines its own Pydantic
models for request and response bodies.  Schemas are separated from
database models to decouple API representation from persistence.
"""