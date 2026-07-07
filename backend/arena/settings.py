"""Centralized runtime settings for the Arena backend.

Historically every env var was read inline via ``os.environ.get`` at the
call site (33+ sites). This module is the single source of truth for the
*new* feature flags and tunables introduced by the concurrency-queue
(#117), admin-dashboard (#116), and matchmaking (#96) tracks, while
leaving the legacy inline reads untouched (incremental migration).

Resolution order for the concurrency limits:

1. **DB** — ``platform_settings`` table (editable at runtime via the
   admin dashboard, #116). ``get_platform_setting`` reads this first.
2. **Env var** — pydantic-settings ``Settings`` instance, read once at
   startup. Used to seed the DB on first migration and as a fallback.
3. **Hardcoded default** — the ``Settings`` field default.

The ``Settings`` instance is created lazily via ``get_settings()`` with
an LRU cache so tests that mutate ``os.environ`` and reload ``arena.main``
can clear the cache to pick up new values.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Feature flags and tunables, sourced from environment variables.

    All keys default to safe values so a fresh install boots without any
    extra configuration. Env vars are read once at instantiation; the
    ``platform_settings`` DB table (added in the same migration that
    ships this module) overrides the concurrency knobs at runtime.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Admin dashboard (#116) ──────────────────────────────────────────
    enable_admin_dashboard: bool = False
    # Comma-separated UUIDs allowed to access /admin even before any
    # is_admin DB row can be flipped. Bootstrap mechanism only.
    admin_user_ids: str = ""

    # ── Game concurrency queue (#117) ──────────────────────────────────
    max_concurrent_sessions: int = 50
    max_concurrent_sessions_per_user: int = 5

    # ── Matchmaking (#96) ──────────────────────────────────────────────
    matchmaking_ttl_hours: int = 24
    matchmaking_sweeper_interval_seconds: int = 3600
    # Matchmaking is intrinsically multi-user; disabled in local mode
    # (no OAuth providers) regardless of this flag. Kept as an explicit
    # kill switch for operators who want the endpoints off even with
    # OAuth configured.
    enable_matchmaking: bool = True

    @property
    def admin_user_id_set(self) -> set[str]:
        """Parse ``ADMIN_USER_IDS`` env var into a set of lowercased UUID strings."""
        return {
            token.strip().lower()
            for token in self.admin_user_ids.split(",")
            if token.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance.

    Tests that change env vars should call ``get_settings.cache_clear()``
    (and then re-import or reload the consumer module) before relying on
    the new values.
    """
    return Settings()


def _env_default(key: str, default: Any) -> Any:
    """Read an env var with the same semantics as the legacy inline reads.

    Used by the migration seeder so the seeded ``platform_settings`` row
    matches what the env var would have produced on first boot.
    """
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw


__all__ = ["Settings", "get_settings"]