"""A tiny HTTP endpoint so the bot can run as a Render web service.

Render only offers a free tier for *web* services, and a web service must bind
to $PORT or the deploy is marked failed. A polling bot has no inbound traffic
of its own, so this server exists to satisfy that requirement - and doubles as
the health check target and the thing an uptime pinger hits to stop a free
service from idling out after 15 minutes.
"""

from __future__ import annotations

import logging
import time

from aiohttp import web

log = logging.getLogger("health")

_started_at = time.time()


def _build_app(details: dict[str, object]) -> web.Application:
    async def handler(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "uptime_seconds": round(time.time() - _started_at),
                **details,
            }
        )

    app = web.Application()
    app.router.add_get("/", handler)
    app.router.add_get("/healthz", handler)
    return app


async def start_health_server(port: int, **details: object) -> web.AppRunner:
    """Start the endpoint and return its runner so callers can shut it down."""
    runner = web.AppRunner(_build_app(details), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("health endpoint listening on port %d", port)
    return runner
