"""Tests for the MessageLogger (message:log queue → DB)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from arena.messaging.message_logger import MessageLogger
from arena.models.message_log import MessageLog


def _make_session_factory():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.add = MagicMock()
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
        ml = MessageLogger(broker, factory)
        await ml.start()
        try:
            assert ml._task is not None
        finally:
            await ml.stop()
        assert ml._task is None

    @pytest.mark.asyncio
    async def test_stop_without_start_is_noop(self):
        broker = MagicMock()
        factory, _ = _make_session_factory()
        ml = MessageLogger(broker, factory)
        await ml.stop()  # Should not raise.


class TestWriteToDb:
    @pytest.mark.asyncio
    async def test_inserts_row_with_all_fields(self):
        factory, session = _make_session_factory()
        broker = MagicMock()
        ml = MessageLogger(broker, factory)

        await ml._write_to_db({
            "session_id": "s1",
            "player": "A",
            "round_number": 3,
            "agent_id": "agent-x",
            "payload": {"action": "cooperate"},
        })

        session.add.assert_called_once()
        row = session.add.call_args.args[0]
        assert isinstance(row, MessageLog)
        assert row.session_id == "s1"
        assert row.player == "A"
        assert row.round_number == 3
        assert row.agent_id == "agent-x"
        assert row.payload == {"action": "cooperate"}
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_session_id(self):
        factory, session = _make_session_factory()
        broker = MagicMock()
        ml = MessageLogger(broker, factory)

        await ml._write_to_db({"player": "A", "payload": {}})
        session.add.assert_not_called()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_defaults_for_missing_fields(self):
        factory, session = _make_session_factory()
        broker = MagicMock()
        ml = MessageLogger(broker, factory)

        await ml._write_to_db({"session_id": "s1"})

        row = session.add.call_args.args[0]
        assert row.session_id == "s1"
        assert row.player == ""
        assert row.round_number == 0
        assert row.agent_id is None
        assert row.payload is None


class TestRunLoop:
    @pytest.mark.asyncio
    async def test_run_processes_then_cancels(self):
        factory, session = _make_session_factory()

        call_count = 0

        async def dequeue(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"session_id": "s1", "player": "A"}
            raise asyncio.CancelledError()

        broker = MagicMock()
        broker.dequeue = dequeue
        ml = MessageLogger(broker, factory)

        await ml._run()
        assert session.add.call_count == 1
        assert session.commit.call_count == 1
