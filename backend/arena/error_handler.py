"""Global exception handler — UUID-tagged 500s with a GitHub issue link.

Whenever an unhandled exception bubbles up to FastAPI, this handler:

1. Generates a public UUID4.
2. Captures the full traceback via :func:`traceback.format_exception`.
3. Persists one row in the ``error_logs`` table with the UUID, the
   request method/path, the exception class, the message, the
   traceback, and a handful of request fields (client IP via
   ``X-Forwarded-For`` first then ``request.client.host``, User-Agent,
   query string).
4. Logs the error via the standard ``logging`` module at ``ERROR``
   level so the operator still gets the traceback in container logs.
5. Returns a minimal response with the UUID:
   - JSON for API requests (``application/json`` or path under
     ``/api/...``) so the React app's :class:`ErrorBoundary` can show
     the UUID and link out to a GitHub issue.
   - HTML for everything else, with a styled error page that has the
     UUID prominent and a "Report this on GitHub" link that prefills
     the issue title and body with the UUID.

The traceback never leaves the server. The response is intentionally
minimal (status + UUID + a hint about reporting) so we don't leak
paths, secrets, or internal state to the wire.
"""
from __future__ import annotations

import logging
import traceback
import uuid
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from arena.models.error_log import ErrorLog

logger = logging.getLogger("arena.error_handler")

# Public repo where users report issues. The error page embeds this in
# an "open an issue" link with the UUID prefilled so the maintainer
# can look up the full traceback in the error_logs table.
GITHUB_REPO_URL = "https://github.com/OutplayArena/arena"
GITHUB_NEW_ISSUE_URL = f"{GITHUB_REPO_URL}/issues/new"


def _client_ip(request: Request) -> str | None:
    """Return the best-effort client IP for the request.

    Honors ``X-Forwarded-For`` (the first hop) so the value is the
    original client when running behind Traefik/nginx; falls back to
    ``request.client.host``. Returns ``None`` if neither is set (e.g.
    ASGI scope without a transport).
    """
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # X-Forwarded-For is a comma-separated list; the first entry is
        # the original client. Strip any port suffix.
        first = fwd.split(",", 1)[0].strip()
        # IPv4:port or [IPv6]:port — keep just the address.
        if first.startswith("[") and "]" in first:
            first = first[1 : first.index("]")]
        elif ":" in first and first.count(":") == 1:
            first = first.rsplit(":", 1)[0]
        return first
    if request.client and request.client.host:
        return request.client.host
    return None


def _github_issue_link(error_id: uuid.UUID, method: str, path: str) -> str:
    """Build a prefilled GitHub 'new issue' URL for the given error.

    Title and body are URL-encoded. The user lands in the new-issue
    editor with the UUID pre-filled so the maintainer can grep the
    ``error_logs`` table for the traceback.
    """
    title = f"Server error: {error_id}"
    body = (
        f"Error ID: **{error_id}**\n\n"
        f"Request: `{method} {path}`\n\n"
        f"Steps to reproduce (if known):\n\n"
        f"\n"
    )
    return f"{GITHUB_NEW_ISSUE_URL}?title={quote(title)}&body={quote(body)}"


def _html_error_page(error_id: uuid.UUID, method: str, path: str) -> str:
    """Render the user-facing HTML 500 page.

    Plain HTML (no external assets) so it works even when the SPA's
    static dir is missing or a CDN is down. The page is intentionally
    self-contained: a single inline-styled card with the UUID prominent
    and a button to open a GitHub issue.
    """
    issue_url = _github_issue_link(error_id, method, path)
    # Escape any HTML in the path so it can't inject markup into the
    # error page itself (defence in depth; path is normally URL-safe).
    safe_path = (
        path.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Server error &middot; OutplayArena</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #fafafa;
      --card: #ffffff;
      --ink: #0f172a;
      --muted: #475569;
      --line: rgba(0,0,0,0.08);
      --accent: #2dd4bf;
      --accent-ink: #0f766e;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0b1020;
        --card: #131a2c;
        --ink: #e2e8f0;
        --muted: #94a3b8;
        --line: rgba(255,255,255,0.08);
        --accent: #2dd4bf;
        --accent-ink: #5eead4;
      }}
    }}
    html, body {{
      margin: 0; padding: 0; height: 100%;
      background: var(--bg);
      color: var(--ink);
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI",
        Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    .wrap {{
      min-height: 100%; display: flex; align-items: center; justify-content: center;
      padding: 24px;
    }}
    .card {{
      max-width: 560px; width: 100%;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 32px 28px;
      box-shadow: 0 1px 0 rgba(0,0,0,0.04);
    }}
    h1 {{ font-size: 20px; margin: 0 0 8px; letter-spacing: -0.01em; }}
    p {{ color: var(--muted); line-height: 1.5; margin: 0 0 16px; }}
    .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 4px; }}
    .id {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 14px;
      background: var(--bg);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      word-break: break-all;
      user-select: all;
    }}
    .path {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 12px;
      color: var(--muted);
      margin-top: 4px;
      word-break: break-all;
    }}
    .actions {{
      display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px;
    }}
    .btn {{
      display: inline-flex; align-items: center; gap: 6px;
      padding: 8px 14px; border-radius: 8px;
      font-size: 14px; font-weight: 600; text-decoration: none;
      border: 1px solid var(--line);
    }}
    .btn-primary {{
      background: var(--accent); color: #00241f; border-color: transparent;
    }}
    .btn-primary:hover {{ filter: brightness(0.95); }}
    .btn-secondary {{ color: var(--ink); background: transparent; }}
    .btn-secondary:hover {{ background: var(--bg); }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Something went wrong on our end</h1>
      <p>
        The server hit an unexpected error. The full traceback has
        been recorded; quote the error ID below when reporting it
        and we can look it up immediately.
      </p>
      <div class="label">Error ID</div>
      <div class="id">{error_id}</div>
      <div class="path">{method} {safe_path}</div>
      <div class="actions">
        <a class="btn btn-primary" href="{issue_url}" target="_blank" rel="noopener noreferrer">
          Report this on GitHub
        </a>
        <a class="btn btn-secondary" href="/">Back to home</a>
      </div>
    </div>
  </div>
</body>
</html>
"""


async def _persist_error_log(
    request: Request,
    error_id: uuid.UUID,
    exc: BaseException,
) -> None:
    """Write the error row to ``error_logs``.

    Uses the global async session factory from :mod:`arena.db`; we
    don't take a per-request session here because the error handler
    fires *after* the request's dependency-injected session has been
    closed (or never opened, for non-API exceptions).
    """
    # Imported lazily to avoid a circular import at module load time
    # (arena.db is imported by arena.models).
    from arena.db import async_session

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    row = ErrorLog(
        id=error_id,
        method=request.method,
        path=str(request.url.path)[:2048],
        exception_type=type(exc).__name__,
        message=str(exc)[:8192],
        traceback=tb[:65536],  # cap so a single row stays reasonable
        client_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent", "")[:512] or None,
        query_string=str(request.url.query)[:2048] or None,
        extra=None,
    )
    try:
        async with async_session() as session:
            session.add(row)
            await session.commit()
    except Exception as persist_exc:  # noqa: BLE001
        # If the DB write itself fails (e.g. error_logs table is
        # missing because migrations never ran), fall back to a log
        # line. The user still gets a UUID, but we lose the
        # queryable traceback.
        logger.error(
            "Failed to persist error log for id=%s: %s",
            error_id,
            persist_exc,
        )


def _wants_json(request: Request) -> bool:
    """Decide whether the client wants JSON back.

    Detection is path-based: anything under ``/api/...`` is an API
    request and always returns JSON (matches the production routing
    contract — the rest of the app uses ``/api/...`` for backend
    routes, ``/mcp/...`` for the MCP transport, and everything else
    is the SPA). For non-API paths we look at the ``Accept`` header:
    explicit ``application/json`` without a ``text/html`` qualifier
    gets JSON; everything else (browsers, ``text/html``, ``*/*``)
    gets the styled HTML error page.

    The empty-string ``API_PREFIX=""`` that the test suite uses to
    register routes at the root is ignored here — we still treat
    anything under ``/api/...`` as API-shaped, which keeps the test
    suite's "``/api/boom`` is an API route" contract intact.
    """
    path = request.url.path
    if path == "/api" or path.startswith("/api/"):
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


def _json_error_response(
    error_id: uuid.UUID, method: str, path: str
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "error_id": str(error_id),
            "message": "The server hit an unexpected error.",
            "request": {"method": method, "path": path},
            "report_url": _github_issue_link(error_id, method, path),
        },
    )


def _html_error_response(
    error_id: uuid.UUID, method: str, path: str
) -> HTMLResponse:
    return HTMLResponse(
        status_code=500,
        content=_html_error_page(error_id, method, path),
    )


async def unhandled_exception_handler(
    request: Request, exc: BaseException
) -> Response:
    """Catch-all handler for unhandled exceptions.

    The handler is registered for ``Exception`` (broadest type) and
    is the last line of defence: route-specific handlers and FastAPI's
    own ``HTTPException`` path are not affected.
    """
    # Starlette's ``ServerErrorMiddleware`` logs the exception once
    # already; we add a structured log line keyed by the UUID so the
    # operator can correlate the in-DB row with the container logs.
    error_id = uuid.uuid4()
    logger.exception(
        "Unhandled exception id=%s %s %s",
        error_id,
        request.method,
        request.url.path,
        exc_info=exc,
    )
    await _persist_error_log(request, error_id, exc)

    if _wants_json(request):
        return _json_error_response(error_id, request.method, str(request.url.path))
    return _html_error_response(error_id, request.method, str(request.url.path))


def register_error_handlers(app: FastAPI) -> None:
    """Attach the global exception handler to ``app``.

    Call once during app construction (after CORS, sessions, etc. are
    in place so the handler is the outermost layer the request sees).
    """
    app.add_exception_handler(Exception, unhandled_exception_handler)
    # Touch the Starlette HTTPException so re-exported types keep
    # working in type checkers; not strictly needed at runtime.
    _ = StarletteHTTPException
