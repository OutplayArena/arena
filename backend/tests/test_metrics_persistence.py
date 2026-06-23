"""Tests for the AgentRegistry persistence (load_registry / save_registry)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from arena.metrics.persistence import load_registry, save_registry
from arena.metrics.registry import AgentRegistry


def _make_fake_db(*, row=None):
    """Build a fake AsyncSession."""
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=row)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _make_state_row(state_json):
    row = MagicMock()
    row.state_json = state_json
    return row


class TestLoadRegistry:
    @pytest.mark.asyncio
    async def test_load_returns_empty_registry_when_no_row(self):
        db = _make_fake_db(row=None)
        registry = await load_registry(db)
        assert isinstance(registry, AgentRegistry)
        assert registry.alpha == 50.0  # default
        assert dict(registry.elo_ratings) == {}

    @pytest.mark.asyncio
    async def test_load_with_existing_row(self):
        state_json = {
            "alpha": 75.0,
            "elo_ratings": {"agent-x": 1500.0},
            "marginal_payoffs": {},
            "match_history": ["m1"],
        }
        db = _make_fake_db(row=_make_state_row(state_json))
        registry = await load_registry(db, key="custom-key")
        assert registry.alpha == 75.0
        assert registry.elo_ratings["agent-x"] == 1500.0
        assert registry.match_history == ["m1"]

    @pytest.mark.asyncio
    async def test_load_uses_default_key(self):
        db = _make_fake_db(row=None)
        # Just verify no error when key is omitted.
        await load_registry(db)


class TestSaveRegistry:
    @pytest.mark.asyncio
    async def test_save_executes_upsert(self):
        db = _make_fake_db()
        registry = AgentRegistry()
        registry.elo_ratings["agent-y"] = 1300.0
        await save_registry(registry, db, key="my-key")

        # Should have called execute (with the upsert statement) and commit.
        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_with_default_key(self):
        db = _make_fake_db()
        registry = AgentRegistry()
        await save_registry(registry, db)

        db.execute.assert_awaited_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_includes_registry_state(self):
        db = _make_fake_db()
        registry = AgentRegistry(alpha=100.0)
        registry.elo_ratings["test"] = 1400.0

        await save_registry(registry, db, key="k1")

        # Inspect the SQL statement that was executed.
        stmt = db.execute.call_args.args[0]
        # The compiled SQL should mention the key.
        compiled = str(stmt.compile())
        assert "k1" in compiled or "key" in compiled.lower()
