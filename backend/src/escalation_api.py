"""
escalation_api.py -- Lightweight HTTP API for ShopMitra escalation tickets (Day 7)

Runs a simple aiohttp web server on port 8765 exposing:
  GET  /api/escalations            -> list all tickets (newest first)
  GET  /api/escalations?status=open -> filtered by status
  GET  /api/escalations/<ref_id>   -> single ticket
  POST /api/escalations/<ref_id>/resolve -> mark resolved
  POST /api/escalations/<ref_id>/inprogress -> mark in_progress

Start standalone:  python -m src.escalation_api
Or import:         from src.escalation_api import start_api_server
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env.local", override=False)

# Allow running as script from the backend/ directory
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from . import database
    from . import analytics_api
except ImportError:
    import database  # type: ignore[no-redef]
    import analytics_api  # type: ignore[no-redef]

logger = logging.getLogger("agent.escalation_api")

API_PORT = int(os.getenv("ESCALATION_API_PORT", "8765"))
API_HOST = os.getenv("ESCALATION_API_HOST", "0.0.0.0")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _json_response(data, status: int = 200):
    try:
        from aiohttp.web import Response
    except ImportError:
        raise
    return Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status,
        headers=CORS_HEADERS,
    )


async def handle_list_escalations(request):
    status_filter = request.rel_url.query.get("status")
    tickets = database.list_escalations(status=status_filter or None, limit=100)
    return _json_response({"escalations": tickets, "total": len(tickets)})


async def handle_get_escalation(request):
    ref_id = request.match_info["ref_id"]
    ticket = database.get_escalation(ref_id)
    if not ticket:
        return _json_response({"error": "not_found", "ref_id": ref_id}, status=404)
    return _json_response(ticket)


async def handle_update_status(request):
    ref_id = request.match_info["ref_id"]
    new_status = request.match_info["status"]
    if new_status not in ("resolve", "inprogress"):
        return _json_response({"error": "invalid_status"}, status=400)
    db_status = "resolved" if new_status == "resolve" else "in_progress"
    ticket = database.update_escalation_status(ref_id, db_status)
    if not ticket:
        return _json_response({"error": "not_found", "ref_id": ref_id}, status=404)
    return _json_response(ticket)


async def handle_options(request):
    from aiohttp.web import Response
    return Response(status=204, headers=CORS_HEADERS)


async def start_api_server():
    """Start the aiohttp API server. Runs until cancelled."""
    try:
        from aiohttp import web
    except ImportError:
        logger.error("aiohttp not installed -- cannot start escalation API server.")
        return

    app = web.Application()
    app.router.add_get( "/api/escalations",                     handle_list_escalations)
    app.router.add_get( "/api/escalations/{ref_id}",            handle_get_escalation)
    app.router.add_post("/api/escalations/{ref_id}/{status}",   handle_update_status)
    app.router.add_route("OPTIONS", "/api/escalations",         handle_options)
    app.router.add_route("OPTIONS", "/api/escalations/{ref_id}", handle_options)

    # Day 8 -- register call analytics routes on the same app
    analytics_api.register_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, API_HOST, API_PORT)
    await site.start()
    logger.info("Escalation API running at http://%s:%d/api/escalations", API_HOST, API_PORT)
    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_api_server())
