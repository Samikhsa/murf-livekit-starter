"""
analytics_api.py -- Call Analytics HTTP API for ShopMitra (Day 8)

Registers routes on the shared aiohttp app (port 8765) alongside the
existing escalation_api routes:

  GET  /api/calls/stats           -> {total, successful, failed, pending, success_rate}
  GET  /api/calls                 -> list of recent call records (no PII)
  POST /api/calls                 -> record a new call start
  PATCH /api/calls/<call_id>      -> update call outcome on session end

Privacy: call records contain NO caller names, phone numbers, or transcripts.
"""

import json
import logging

try:
    from . import database
except ImportError:
    import database  # type: ignore[no-redef]

logger = logging.getLogger("agent.analytics_api")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _json_response(data, status: int = 200):
    from aiohttp.web import Response
    return Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status,
        headers=CORS_HEADERS,
    )


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def handle_get_stats(request):
    """GET /api/calls/stats -- aggregate dashboard numbers."""
    stats = database.get_call_stats()
    return _json_response(stats)


async def handle_list_calls(request):
    """GET /api/calls -- recent call records (no PII)."""
    try:
        limit = int(request.rel_url.query.get("limit", "20"))
        limit = max(1, min(limit, 100))
    except ValueError:
        limit = 20
    calls = database.list_recent_calls(limit=limit)
    return _json_response({"calls": calls, "total": len(calls)})


async def handle_create_call(request):
    """POST /api/calls -- called by agent on session start."""
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "invalid_json"}, status=400)

    call_id   = body.get("call_id", "").strip()
    room_name = body.get("room_name", "").strip()
    channel   = body.get("channel", "browser").strip()

    if not call_id or not room_name:
        return _json_response({"error": "call_id and room_name are required"}, status=400)

    if channel not in ("browser", "sip"):
        channel = "browser"

    record = database.record_call_start(call_id, room_name, channel)
    return _json_response(record, status=201)


async def handle_update_call(request):
    """PATCH /api/calls/<call_id> -- called by agent on session end."""
    call_id = request.match_info["call_id"]
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "invalid_json"}, status=400)

    outcome          = body.get("outcome", "").strip()
    failure_type     = body.get("failure_type") or None
    duration_seconds = int(body.get("duration_seconds", 0))

    if outcome not in ("success", "failed", "pending"):
        return _json_response({"error": "outcome must be success | failed | pending"}, status=400)

    record = database.record_call_end(
        call_id,
        outcome=outcome,
        failure_type=failure_type,
        duration_seconds=duration_seconds,
    )
    if record is None:
        return _json_response({"error": "call_id not found", "call_id": call_id}, status=404)
    return _json_response(record)


async def handle_options_calls(request):
    from aiohttp.web import Response
    return Response(status=204, headers=CORS_HEADERS)


# ---------------------------------------------------------------------------
# Registration helper -- called from escalation_api.start_api_server()
# ---------------------------------------------------------------------------

def register_routes(app) -> None:
    """Register all analytics routes on the shared aiohttp app."""
    app.router.add_get(  "/api/calls/stats",         handle_get_stats)
    app.router.add_get(  "/api/calls",                handle_list_calls)
    app.router.add_post( "/api/calls",                handle_create_call)
    app.router.add_route("PATCH", "/api/calls/{call_id}", handle_update_call)
    app.router.add_route("OPTIONS", "/api/calls",         handle_options_calls)
    app.router.add_route("OPTIONS", "/api/calls/{call_id}", handle_options_calls)
    logger.info("Analytics API routes registered: /api/calls and /api/calls/stats")
