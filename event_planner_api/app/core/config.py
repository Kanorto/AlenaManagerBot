"""
Simple configuration management.

To avoid external dependencies on the ``pydantic`` or ``pydantic_settings``
packages (which may not be available in all environments), the
``Settings`` dataclass reads configuration directly from
environment variables.  Defaults are provided for all fields.  In a
production deployment you should override these via environment
variables or a dedicated configuration service.
"""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    project_name: str = os.getenv("PROJECT_NAME", "Event Planner API")
    api_version: str = os.getenv("API_VERSION", "1.0.0")
    debug: bool = os.getenv("DEBUG", "false").lower() in {"1", "true", "yes"}
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    secret_key: str = os.getenv("SECRET_KEY", "change_me")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24)))
    algorithm: str = os.getenv("ALGORITHM", "HS256")

    # Optional static token for super‑administrator API access.  If set via
    # the SUPER_ADMIN_TOKEN environment variable, requests carrying this
    # token in the Authorization header will bypass normal authentication
    # and be treated as the super administrator.  Use with care.
    super_admin_static_token: str = os.getenv("SUPER_ADMIN_TOKEN", "")

    # Comma‑separated list of tokens representing trusted bots or external
    # services that should be authenticated as a given role.  Clients
    # presenting one of these tokens in the Authorization header will
    # bypass JWT decoding and be assigned the role specified by
    # ``bot_role_id``.  Example: BOT_TOKENS="token1,token2".
    bot_tokens: str = os.getenv("BOT_TOKENS", "")

    # Role ID to assign to requests authenticated via ``BOT_TOKENS``.
    # Defaults to ``2`` (admin).  You may set this to ``3`` to restrict
    # bots to user privileges.
    bot_role_id: int = int(os.getenv("BOT_ROLE_ID", "2"))

    # Path or connection string for the SQLite database.  Can be
    # overridden via the ``DATABASE_URL`` environment variable.  If a
    # relative path is provided, it will be resolved relative to the
    # project root by the ``db`` module.
    database_url: str = os.getenv("DATABASE_URL", "event_planner.db")


# Instantiate settings once so other modules can import it without
# repeatedly reading environment variables.  Because the dataclass
# computes values at instantiation time, environment variables should
# be set before importing this module.
settings = Settings()