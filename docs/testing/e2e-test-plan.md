# E2E Test Plan: Concurrency Queue, Admin Dashboard, Matchmaking

Manual checklist for testing PRs #117, #116, #96 against the local eval cluster.

## Prerequisites

```bash
# 1. Restart port-forwards (stale container IDs cause connection refused)
./scripts/dev-tunnel.sh restart

# 2. Verify backend is reachable
curl -s http://localhost:30090/api/health
# Expected: {"status":"ok"}

# 3. Set up environment variables
export BACKEND_URL="http://localhost:30090/api"
export ADMIN_USER_ID="9bc2c84d-df0e-4ff5-b586-c7ad636da952"
export NS="arena"

# 4. Mint an admin JWT (admin via ADMIN_USER_IDS env allowlist)
ADMIN_TOKEN=$(kubectl -n $NS exec deployment/arena-backend -- python3 -c \
  "from arena.auth.jwt import create_access_token; print(create_access_token('$ADMIN_USER_ID'))")
export AUTH="Authorization: Bearer $ADMIN_TOKEN"

# 5. Create a second test user for matchmaking
USER_B_OUT=$(kubectl -n $NS exec deployment/arena-backend -- python3 -c "
import asyncio, uuid
from arena.db import async_session
from arena.models.user import User
from arena.auth.jwt import create_access_token
async def main():
    uid = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=uid, email='e2e-manual@test.local', name='E2E', provider='e2e', provider_user_id=uid))
        await db.commit()
    print(uid + '|' + create_access_token(uid))
asyncio.run(main())
")
USER_B_ID=$(echo $USER_B_OUT | cut -d'|' -f1)
USER_B_TOKEN=$(echo $USER_B_OUT | cut -d'|' -f2)
export AUTH_B="Authorization: Bearer $USER_B_TOKEN"
```

## Track A: Concurrency Queue (#117)

### A1. Session admitted under limit

```bash
# Set high limits
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"max_concurrent_sessions":"100","max_concurrent_sessions_per_user":"100"}'

# Create a session
curl -s -X POST "$BACKEND_URL/experiment" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}'
# Expected: 200, status="ready", no queue_position field
```

### A2. Session queued at limit

```bash
# Get current active session count
ACTIVE=$(kubectl -n $NS exec deployment/arena-backend -- python3 -c "
import asyncio
from arena.db import async_session
from sqlalchemy import select, func
from arena.models.session import SessionModel
async def main():
    async with async_session() as db:
        c = (await db.execute(select(func.count()).select_from(SessionModel).where(SessionModel.status.in_(['ready','running'])))).scalar_one()
        print(c)
asyncio.run(main())
")

# Set global limit to current active count
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"max_concurrent_sessions\":\"$ACTIVE\",\"max_concurrent_sessions_per_user\":\"100\"}"

# Create a session — should be queued
curl -s -X POST "$BACKEND_URL/experiment" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}'
# Expected: 202, status="queued", queue_position>=1
```

### A3. Queue status polling

```bash
# Use session_id from A2
SESSION_ID="<queued_session_id>"
curl -s "$BACKEND_URL/session/$SESSION_ID/status" -H "$AUTH"
# Expected: {"status":"queued","queue_position":1}
```

### A4. Action rejected while queued

```bash
curl -s -X POST "$BACKEND_URL/session/$SESSION_ID/action" \
  -H "Authorization: Bearer <player_token_A>" \
  -H "Content-Type: application/json" \
  -d '{"allocation":[20,20,20,20,20]}'
# Expected: 409, detail contains "queued"
```

### A5. Drainer promotes queued session

```bash
# Set limit to active+1
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"max_concurrent_sessions\":\"$((ACTIVE+1))\",\"max_concurrent_sessions_per_user\":\"100\"}"

# Create session 1 (admitted)
R1=$(curl -s -X POST "$BACKEND_URL/experiment" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}')
SID1=$(echo $R1 | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
TOK1=$(echo $R1 | python3 -c "import sys,json;print(json.load(sys.stdin)['player_tokens']['A'])")

# Create session 2 (queued)
R2=$(curl -s -X POST "$BACKEND_URL/experiment" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}')
SID2=$(echo $R2 | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

# Verify queued
curl -s "$BACKEND_URL/session/$SID2/status" -H "$AUTH"
# Expected: {"status":"queued",...}

# Fail session 1 to free a slot
curl -s -X POST "$BACKEND_URL/session/$SID1/fail" \
  -H "Authorization: Bearer $TOK1" \
  -H "Content-Type: application/json" \
  -d '{"error":"e2e test"}'

# Wait ~2-4s, then check session 2 status
sleep 4
curl -s "$BACKEND_URL/session/$SID2/status" -H "$AUTH"
# Expected: {"status":"ready","queue_position":0}
```

### A6. Per-user concurrency limit

```bash
# Set per-user limit to 1, global limit high
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"max_concurrent_sessions":"100","max_concurrent_sessions_per_user":"1"}'

# User B creates session 1 (admitted — 0 active < 1)
curl -s -X POST "$BACKEND_URL/experiment" \
  -H "$AUTH_B" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}'
# Expected: 200

# User B creates session 2 (queued — 1 active >= 1)
curl -s -X POST "$BACKEND_URL/experiment" \
  -H "$AUTH_B" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}'
# Expected: 202, status="queued"
```

### Cleanup

```bash
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"max_concurrent_sessions":"50","max_concurrent_sessions_per_user":"5","login_enabled":"true"}'
```

## Track B: Admin Dashboard (#116)

### B1. Site config exposes admin flag

```bash
curl -s "$BACKEND_URL/site-config" | python3 -m json.tool
# Expected: "admin_dashboard_enabled": true
```

### B2. User info shows is_admin via env

```bash
curl -s "$BACKEND_URL/auth/me" -H "$AUTH" | python3 -m json.tool
# Expected: "is_admin": true (even though DB is_admin=false)
```

### B3. Unauthenticated request rejected

```bash
curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/admin/users"
# Expected: 401
```

### B4. Non-admin request rejected

```bash
curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/admin/users" -H "$AUTH_B"
# Expected: 403
```

### B5. List users with email masking

```bash
curl -s "$BACKEND_URL/admin/users" -H "$AUTH" | python3 -m json.tool
# Expected: 200, "users" array, each with "email_masked" (not raw email)
```

### B6. List sessions with pagination

```bash
curl -s "$BACKEND_URL/admin/sessions?limit=10&offset=0" -H "$AUTH" | python3 -m json.tool
# Expected: 200, "total" count + "sessions" array
```

### B7. Platform stats

```bash
curl -s "$BACKEND_URL/admin/stats" -H "$AUTH" | python3 -m json.tool
# Expected: sessions_running, sessions_ready, sessions_queued, sessions_failed,
#           sessions_completed, wandb_users, login_enabled, db_size_bytes, backup.status
```

### B8. Get settings

```bash
curl -s "$BACKEND_URL/admin/settings" -H "$AUTH" | python3 -m json.tool
# Expected: max_concurrent_sessions, max_concurrent_sessions_per_user, login_enabled
```

### B9. Update settings

```bash
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"max_concurrent_sessions":"99"}'
# Expected: 200, {"max_concurrent_sessions":"99"}

curl -s "$BACKEND_URL/admin/settings" -H "$AUTH" | python3 -m json.tool
# Verify: max_concurrent_sessions = 99
```

### B10. Error log

```bash
curl -s "$BACKEND_URL/admin/errors?limit=5" -H "$AUTH" | python3 -m json.tool
# Expected: 200, "errors" array
```

### B11. Login disabled blocks OAuth

```bash
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"login_enabled":"false"}'

curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/auth/github/login"
# Expected: 403

curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/auth/google/login"
# Expected: 403

# Restore
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"login_enabled":"true"}'
```

## Track C: Matchmaking / Lobby (#96)

### C1. Create open match

```bash
curl -s -X POST "$BACKEND_URL/lobby/matches" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}' \
  | python3 -m json.tool
# Expected: 200, match_id, status="waiting", host_token="nks_...", host_slot="A",
#           total_slots=2, filled_slots=1, invite_code, expires_at
```

### C2. List open matches

```bash
curl -s "$BACKEND_URL/lobby/matches" -H "$AUTH" | python3 -m json.tool
# Expected: 200, "matches" array containing the match from C1
```

### C3. Get match detail

```bash
MATCH_ID="<match_id_from_C1>"
curl -s "$BACKEND_URL/lobby/matches/$MATCH_ID" -H "$AUTH" | python3 -m json.tool
# Expected: 200, detail with participants=[{slot:"A",...}], session_id=null
```

### C4. Join match fills and creates session

```bash
curl -s -X POST "$BACKEND_URL/lobby/matches/$MATCH_ID/join" \
  -H "$AUTH_B" -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
# Expected: 200, slot="B", player_token="nks_...", status="running",
#           filled_slots=2, session_id present

# Verify session in DB has match_id set
kubectl -n $NS exec deployment/arena-backend -- python3 -c "
import asyncio
from arena.db import async_session
from arena.models.session import SessionModel
from sqlalchemy import select
async def main():
    async with async_session() as db:
        row = (await db.execute(select(SessionModel).where(SessionModel.id=='<session_id>'))).scalar_one_or_none()
        print(f'match_id={row.match_id}' if row else 'NOT FOUND')
asyncio.run(main())
"
# Expected: match_id=<match_id>
```

### C5. Host token validity after fill (potential bug)

```bash
# After C4, try to use the host_token from C1 to submit an action
curl -s -X POST "$BACKEND_URL/session/<session_id>/action" \
  -H "Authorization: Bearer <host_token_from_C1>" \
  -H "Content-Type: application/json" \
  -d '{"allocation":[20,20,20,20,20]}'
# If 401: Bug confirmed — host token derived from pre_session_id, not the real session_id.
# If 200: Bug fixed — host token is valid against the session.
```

### C6. Double-join rejected

```bash
# Create a new match, then host tries to join again
curl -s -X POST "$BACKEND_URL/lobby/matches/$NEW_MATCH_ID/join" \
  -H "$AUTH" -H "Content-Type: application/json" -d '{}'
# Expected: 409 (uq_match_user constraint)
```

### C7. Cancel match — host only

```bash
# Non-host tries to cancel
curl -s -X DELETE "$BACKEND_URL/lobby/matches/$MATCH_ID" -H "$AUTH_B"
# Expected: 403

# Host cancels
curl -s -X DELETE "$BACKEND_URL/lobby/matches/$MATCH_ID" -H "$AUTH"
# Expected: 200, {"cancelled":true}
```

### C8. SSE stream

```bash
# Terminal 1: Start SSE stream
curl -N "$BACKEND_URL/lobby/matches/$MATCH_ID/stream" -H "$AUTH"

# Terminal 2: Join the match
curl -s -X POST "$BACKEND_URL/lobby/matches/$MATCH_ID/join" \
  -H "$AUTH_B" -H "Content-Type: application/json" -d '{}'

# Terminal 1: Should receive match_filled event, then stream closes
```

### C9. Match expiry

```bash
# Create a match, then manually expire it
MATCH_ID=$(curl -s -X POST "$BACKEND_URL/lobby/matches" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"game":"colonelblotto","players":2,"n_fields":5,"total":100,"rounds":1,"seed":42}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['match_id'])")

# Set expires_at to 5 minutes ago
kubectl -n $NS exec deployment/arena-backend -- python3 -c "
import asyncio
from arena.db import async_session
from arena.models.match import Match
from datetime import datetime, timezone, timedelta
from sqlalchemy import update
async def main():
    async with async_session() as db:
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        await db.execute(update(Match).where(Match.id=='$MATCH_ID').values(expires_at=past))
        await db.commit()
asyncio.run(main())
"

# Trigger the sweeper directly (avoids waiting up to 1 hour)
kubectl -n $NS exec deployment/arena-backend -- python3 -c "
import asyncio
from arena.db import async_session
from arena.matchmaking import expire_stale_matches
from arena.messaging import RedisBroker
async def main():
    broker = RedisBroker()
    async with async_session() as db:
        count = await expire_stale_matches(db, broker)
        print(f'expired {count} matches')
asyncio.run(main())
"

# Verify match is expired
curl -s "$BACKEND_URL/lobby/matches/$MATCH_ID" -H "$AUTH" | python3 -m json.tool
# Expected: status="expired"
```

### C10. Race safety — concurrent join

```bash
# Requires two non-host users (B and C). See the Python E2E script for the
# asyncio.gather implementation. Manual testing with curl is unreliable for
# true concurrency — use the automated test instead:
#
#   pytest backend/tests/test_e2e_features.py::TestMatchmakingE2E::test_race_safety_concurrent_join -m e2e -v
```

## Running the Automated E2E Suite

```bash
# Run all E2E tests
uv run pytest backend/tests/test_e2e_features.py -m e2e -v

# Run a single track
uv run pytest backend/tests/test_e2e_features.py::TestConcurrencyQueueE2E -m e2e -v
uv run pytest backend/tests/test_e2e_features.py::TestAdminDashboardE2E -m e2e -v
uv run pytest backend/tests/test_e2e_features.py::TestMatchmakingE2E -m e2e -v

# Run a single test
uv run pytest backend/tests/test_e2e_features.py::TestMatchmakingE2E::test_host_token_validity_after_fill -m e2e -v
```

## Post-Test Cleanup

```bash
# Restore default platform settings
curl -s -X PUT "$BACKEND_URL/admin/settings" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"max_concurrent_sessions":"50","max_concurrent_sessions_per_user":"5","login_enabled":"true"}'

# Delete test user B
kubectl -n $NS exec deployment/arena-backend -- python3 -c "
import asyncio
from arena.db import async_session
from arena.models.user import User
from sqlalchemy import delete
async def main():
    async with async_session() as db:
        await db.execute(delete(User).where(User.id == '$USER_B_ID'))
        await db.commit()
asyncio.run(main())
"
```
