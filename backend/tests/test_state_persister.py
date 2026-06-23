"""Tests for the StatePersister (state:persist queue → DB)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from arena.messaging.state_persister import StatePersister


class _FakeRow:
    def __init__(self):
        self.state_json = None
        self.status = None
        self.error_message = None
        self.locked = None
        self.player_tokens_json = None


def _make_session_factory(row=None):
    """Build a fake async_sessionmaker that returns a context-managed session."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    factory = MagicMock(spec=async_sessionmaker)
    factory.return_value = session
    return factory, session


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        broker = MagicMock()
        broker.dequeue = AsyncMock(return_value=None)
        factory, _ = _make_session_factory()
        sp = StatePersister(broker, factory)
        await sp.start()
        try:
            assert sp._task is not None
        finally:
            await sp.stop()
        assert sp._task is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(self):
        broker = MagicMock()
        factory, _ = _make_session_factory()
        sp = StatePersister(broker, factory)
        # Should not raise even though _task is None.
        await sp.stop()


class TestWriteToDb:
    @pytest.mark.asyncio
    async def test_writes_state_fields(self):
        row = _FakeRow()
        factory, session = _make_session_factory(row=row)
        broker = MagicMock()
        sp = StatePersister(broker, factory)

        await sp._write_to_db({
            "session_id": "s1",
            "state": {"round": 1},
            "status": "playing",
            "error_message": None,
            "locked": True,
            "player_tokens": {"A": "tok1"},
        })

        assert row.state_json == {"round": 1}
        assert row.status == "playing"
        assert row.locked is True
        assert row.player_tokens_json == {"A": "tok1"}
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_session_id(self):
        factory, session = _make_session_factory()
        broker = MagicMock()
        sp = StatePersister(broker, factory)

        await sp._write_to_db({"state": {"round": 1}})
        # No DB call should have been made.
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_session_not_found(self):
        factory, session = _make_session_factory(row=None)
        broker = MagicMock()
        sp = StatePersister(broker, factory)

        await sp._write_to_db({
            "session_id": "missing",
            "state": {"round": 1},
        })
        # Session was queried but not committed.
        session.execute.assert_awaited_once()
        session.commit.assert_not_called()


class TestRunLoop:
    @pytest.mark.asyncio
    async def test_run_processes_message_then_cancellation_exits(self):
        """_run should process a message, then exit when dequeue raises CancelledError."""
        row = _FakeRow()
        factory, session = _make_session_factory(row=row)

        call_count = 0

        async def dequeue_with_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"session_id": "s1", "state": {"x": 1}}
            raise asyncio.CancelledError()

        broker = MagicMock()
        broker.dequeue = dequeue_with_cancel
        sp = StatePersister(broker, factory)

        # CancelledError is caught and breaks the loop (function returns normally).
        await sp._run()

        assert row.state_json == {"x": 1}
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_continues_on_generic_error(self):
        """_run should catch and log generic errors, then keep looping."""
        factory, _ = _make_session_factory()
        call_count = 0

        async def dequeue_with_cancel(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("transient")
            raise asyncio.CancelledError()

        broker = MagicMock()
        broker.dequeue = dequeue_with_cancel
        sp = StatePersister(broker, factory)

        await sp._run()
        assert call_count == 3


