import pytest

from nash_arena.mcp_key_manager import (
    create_mcp_key,
    revoke_mcp_key,
    disable_mcp_key,
    enable_mcp_key,
    list_mcp_keys,
)
from nash_arena.models.mcp_auth_key import McpAuthKey


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else []


class FakeDb:
    def __init__(self):
        self._store: dict[str, McpAuthKey] = {}
        self._last_query = ""

    async def execute(self, stmt):
        self._last_query = str(stmt)
        if "mcp_auth_keys" in self._last_query:
            if "WHERE" in self._last_query and self._store:
                return FakeResult(list(self._store.values())[0])
            return FakeResult(list(self._store.values()))
        return FakeResult(None)

    def add(self, obj):
        if isinstance(obj, McpAuthKey):
            self._store[str(obj.id)] = obj

    async def delete(self, obj):
        self._store.pop(str(obj.id), None)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture(name="db")
def db_fixture():
    return FakeDb()


@pytest.mark.asyncio
async def test_create_mcp_key(db):
    full_key, row = await create_mcp_key(db, name="test-server")

    assert full_key.startswith("nmk_")
    assert row.name == "test-server"
    assert row.is_active is True
    assert row.key_prefix.startswith("nmk_")


@pytest.mark.asyncio
async def test_create_mcp_key_without_name(db):
    full_key, row = await create_mcp_key(db)

    assert full_key.startswith("nmk_")
    assert row.name is None
    assert row.is_active is True


@pytest.mark.asyncio
async def test_revoke_mcp_key(db):
    full_key, row = await create_mcp_key(db, name="test-server")

    result = await revoke_mcp_key(db, str(row.id))

    assert result is True
    assert str(row.id) not in db._store


@pytest.mark.asyncio
async def test_revoke_mcp_key_not_found(db):
    result = await revoke_mcp_key(db, "nonexistent-id")

    assert result is False


@pytest.mark.asyncio
async def test_disable_mcp_key(db):
    full_key, row = await create_mcp_key(db, name="test-server")

    result = await disable_mcp_key(db, str(row.id))

    assert result is True
    assert row.is_active is False


@pytest.mark.asyncio
async def test_disable_mcp_key_not_found(db):
    result = await disable_mcp_key(db, "nonexistent-id")

    assert result is False


@pytest.mark.asyncio
async def test_enable_mcp_key(db):
    full_key, row = await create_mcp_key(db, name="test-server")
    await disable_mcp_key(db, str(row.id))

    result = await enable_mcp_key(db, str(row.id))

    assert result is True
    assert row.is_active is True


@pytest.mark.asyncio
async def test_enable_mcp_key_not_found(db):
    result = await enable_mcp_key(db, "nonexistent-id")

    assert result is False


@pytest.mark.asyncio
async def test_list_mcp_keys(db):
    await create_mcp_key(db, name="server-1")
    await create_mcp_key(db, name="server-2")

    keys = await list_mcp_keys(db)

    assert len(keys) == 2
    names = {k.name for k in keys}
    assert names == {"server-1", "server-2"}
