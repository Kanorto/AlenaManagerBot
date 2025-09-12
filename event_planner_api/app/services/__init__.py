"""
Service layer abstraction.

Each service encapsulates business logic for a domain.  By isolating
logic here you can swap out the in‑memory data structures used in
this MVP for database queries without changing API handlers.
"""