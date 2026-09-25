"""HTTP surface for the bot: a health endpoint, and the webhook when deployed.

Render only offers a free tier for *web* services, and a web service must bind
to $PORT or the deploy is marked failed. A polling bot has no inbound traffic
of its own, so this server exists to satisfy that - and doubles as the health
check target and the thing an uptime pinger hits.

When deployed it also hosts Telegram's webhook, which is what lets an incoming
message wake a sleeping instance at all.
"""

from __future__ import annotations

import logging
import time

from aiohttp import web

log = logging.getLogger("health")

_started_at = time.time()


def build_app(**details: object) -> web.Application:
    """An aiohttp app serving / and /healthz. Callers may add more routes."""

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


async def serve(app: web.Application, port: int) -> web.AppRunner:
    """Start the app and return its runner so callers can shut it down."""
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("http server listening on port %d", port)
    return runner
