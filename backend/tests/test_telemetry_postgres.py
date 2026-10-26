"""Transactional checks against an opt-in, isolated PostgreSQL schema.

Set TELEMETRY_TEST_DATABASE_URL to an asyncpg test database URL. Each test
creates and drops only its own randomly named schema, never existing tables.
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from arena.models import Base, SessionModel, TelemetryEvent
from arena.session import GameSession
from games.core.colonelblotto.config import (
    BattlefieldConfig,
    ColonelBlottoExperimentConfig,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_URL = os.environ.get("TELEMETRY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="opt-in PostgreSQL telemetry tests"
)


@pytest_asyncio.fixture
async def database():
    schema = "telemetry_test_" + uuid4().hex
    admin = create_async_engine(TEST_URL)
    async with admin.begin() as connection:
        await connection.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_async_engine(
        TEST_URL,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        await admin.dispose()


def config():
    return ColonelBlottoExperimentConfig(
        game="colonelblotto",
        variant="classic",
        players=2,
        rounds=1,
        seed=42,
        budget=[10, 10],
        battlefields=[
            BattlefieldConfig(id=name, value=1.0) for name in ("x", "y", "z")
        ],
    )


async def new_run(database, owner):
    session = GameSession.create(
        config(), agents={"A": "research-a", "B": "research-b"}
    )
    async with database() as db:
        await session.save_new(db, user_id=owner, agents=session.agents)
    return session


@pytest_asyncio.fixture
async def api(database, monkeypatch):
    import arena.telemetry.api as telemetry_api
    from arena import main
    from arena.auth.dependencies import require_user
    from arena.db import get_db

    owner = uuid4()

    async def db_dependency():
        async with database() as db:
            yield db

    async def user_dependency():
        return SimpleNamespace(id=owner)

    monkeypatch.setenv("ENABLE_AGENT_REST_API", "true")
    monkeypatch.setitem(main.app.dependency_overrides, get_db, db_dependency)
    monkeypatch.setitem(main.app.dependency_overrides, require_user, user_dependency)
    monkeypatch.setitem(
        main.app.dependency_overrides, main.get_broker, lambda: AsyncMock()
    )
    monkeypatch.setattr(telemetry_api, "async_session", database)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app),
        base_url="http://arena",
    ) as client:
        yield client, owner, main.API_PREFIX


@pytest.mark.asyncio
async def test_concurrent_submissions_commit_state_and_complete_trace(database, api):
    client, owner, prefix = api
    session = await new_run(database, owner)

    async def submit(player, allocation):
        return await client.post(
            f"{prefix}/session/{session.session_id}/action",
            json={"allocation": allocation},
            headers={"Authorization": f"Bearer {session.player_tokens[player]}"},
        )

    responses = await asyncio.gather(submit("A", [10, 0, 0]), submit("B", [0, 5, 5]))
    assert [response.status_code for response in responses] == [200, 200]
    async with database() as db:
        row = await db.get(SessionModel, session.session_id)
        events = (
            (await db.execute(select(TelemetryEvent).order_by(TelemetryEvent.id)))
            .scalars()
            .all()
        )
    assert row.status == "completed"
    assert [event.event_type for event in events] == [
        "session.created",
        "action.accepted",
        "action.accepted",
        "round.completed",
        "session.completed",
    ]
    report = (
        await client.get(f"{prefix}/session/{session.session_id}/telemetry")
    ).json()
    assert report["coverage"]["complete"] is True
    assert report["summary"]["action_count"] == 2
    assert report["summary"]["rounds_completed"] == 1
    exported = await client.get(
        f"{prefix}/session/{session.session_id}/telemetry/export?format=jsonl"
    )
    assert exported.status_code == 200
    records = [json.loads(line) for line in exported.text.splitlines()]
    assert records[0]["record_type"] == "manifest"
    assert len(records) == 6
    assert "player_tokens" not in exported.text


@pytest.mark.asyncio
async def test_rejected_action_commits_event_without_changing_state(database, api):
    client, owner, prefix = api
    session = await new_run(database, owner)
    response = await client.post(
        f"{prefix}/session/{session.session_id}/action",
        json={"allocation": [9, 0, 0]},
        headers={"Authorization": f"Bearer {session.player_tokens['A']}"},
    )
    assert response.status_code == 400
    async with database() as db:
        row = await db.get(SessionModel, session.session_id)
        events = (
            (await db.execute(select(TelemetryEvent).order_by(TelemetryEvent.id)))
            .scalars()
            .all()
        )
    assert row.state_json["pending_actions"] == {}
    assert [event.event_type for event in events] == [
        "session.created",
        "action.rejected",
    ]
    assert events[-1].player_id == "A"
    assert "action" not in events[-1].payload_json


@pytest.mark.asyncio
async def test_state_and_event_rollback_together(database):
    session = await new_run(database, uuid4())
    async with database() as db:
        row = await db.get(SessionModel, session.session_id)
        loaded = GameSession.from_db_row(row)
        loaded.submit_action("A", [10, 0, 0])
        from arena.session import _serialize_state

        row.state_json = _serialize_state(loaded.state)
        await loaded.flush_telemetry(db)
        assert (
            await db.execute(select(func.count()).select_from(TelemetryEvent))
        ).scalar_one() == 2
        await db.rollback()
    async with database() as db:
        row = await db.get(SessionModel, session.session_id)
        assert row.state_json["pending_actions"] == {}
        assert (
            await db.execute(select(func.count()).select_from(TelemetryEvent))
        ).scalar_one() == 1


@pytest.mark.asyncio
async def test_deleting_session_cascades_private_events(database):
    session = await new_run(database, uuid4())
    async with database() as db:
        await db.delete(await db.get(SessionModel, session.session_id))
        await db.commit()
        assert (
            await db.execute(select(func.count()).select_from(TelemetryEvent))
        ).scalar_one() == 0


@pytest.mark.asyncio
async def test_interactive_path_and_explicit_failure_are_durable(database, api):
    client, owner, prefix = api
    session = await new_run(database, owner)
    response = await client.post(
        f"{prefix}/session/{session.session_id}/interactive/action?player=A",
        json={"action": [10, 0, 0]},
        headers={"Authorization": f"Bearer {session.player_tokens['A']}"},
    )
    assert response.status_code == 200
    response = await client.post(
        f"{prefix}/session/{session.session_id}/fail",
        json={"error": "provider error with sk-never-export-this"},
        headers={"Authorization": f"Bearer {session.player_tokens['B']}"},
    )
    assert response.status_code == 200
    report = await client.get(f"{prefix}/session/{session.session_id}/telemetry")
    assert report.status_code == 200
    assert report.json()["status"] == "failed"
    exported = await client.get(
        f"{prefix}/session/{session.session_id}/telemetry/export?format=jsonl"
    )
    assert "sk-never-export-this" not in exported.text
    assert "action.accepted" in exported.text
    assert "session.failed" in exported.text


@pytest.mark.asyncio
async def test_completed_interactive_session_cannot_be_failed_by_malformed_input(
    database, api
):
    client, owner, prefix = api
    session = await new_run(database, owner)
    for player, action in (("A", [10, 0, 0]), ("B", [0, 5, 5])):
        response = await client.post(
            f"{prefix}/session/{session.session_id}/action",
            json={"allocation": action},
            headers={"Authorization": f"Bearer {session.player_tokens[player]}"},
        )
        assert response.status_code == 200
    response = await client.post(
        f"{prefix}/session/{session.session_id}/interactive/action?player=A",
        json={"action": {"action": 123}},
        headers={"Authorization": f"Bearer {session.player_tokens['A']}"},
    )
    assert response.status_code == 409
    async with database() as db:
        row = await db.get(SessionModel, session.session_id)
        kinds = (
            (
                await db.execute(
                    select(TelemetryEvent.event_type).order_by(TelemetryEvent.id)
                )
            )
            .scalars()
            .all()
        )
    assert row.status == "completed"
    assert row.state_json["phase"] == "complete"
    assert kinds[-1] == "action.rejected"
    assert kinds.count("session.completed") == 1
    assert "session.failed" not in kinds


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,token_player,expected",
    [
        ("/action", None, 401),
        ("/interactive/action?player=A", None, 401),
        ("/interactive/action?player=B", "A", 403),
    ],
)
async def test_auth_failures_do_not_pollute_behavioral_events(
    database,
    api,
    path,
    token_player,
    expected,
):
    client, owner, prefix = api
    session = await new_run(database, owner)
    token = session.player_tokens[token_player] if token_player else "invalid-token"
    response = await client.post(
        f"{prefix}/session/{session.session_id}" + path,
        json={"action": [10, 0, 0], "allocation": [10, 0, 0]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == expected
    async with database() as db:
        kinds = (
            (
                await db.execute(
                    select(TelemetryEvent.event_type).order_by(TelemetryEvent.id)
                )
            )
            .scalars()
            .all()
        )
        row = await db.get(SessionModel, session.session_id)
    assert kinds == ["session.created"]
    assert row.status == "ready"


@pytest.mark.asyncio
async def test_failure_is_idempotent_and_rejects_later_actions(database, api):
    client, owner, prefix = api
    session = await new_run(database, owner)
    headers = {"Authorization": f"Bearer {session.player_tokens['A']}"}
    for error in ("original failure", "later failure"):
        response = await client.post(
            f"{prefix}/session/{session.session_id}/fail",
            json={"error": error},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["error_message"] == "original failure"
    response = await client.post(
        f"{prefix}/session/{session.session_id}/action",
        json={"allocation": [10, 0, 0]},
        headers=headers,
    )
    assert response.status_code == 409
    async with database() as db:
        kinds = (
            (
                await db.execute(
                    select(TelemetryEvent.event_type).order_by(TelemetryEvent.id)
                )
            )
            .scalars()
            .all()
        )
        row = await db.get(SessionModel, session.session_id)
    assert kinds.count("session.failed") == 1
    assert "action.accepted" not in kinds
    assert row.state_json["pending_actions"] == {}
