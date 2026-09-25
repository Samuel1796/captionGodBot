"""Configuration, logging, access control and retry helpers."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message, TelegramObject
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

T = TypeVar("T")


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def require_token(var_name: str) -> str:
    """Return a BotFather token, or exit with a message the user can act on."""
    token = os.getenv(var_name, "").strip()
    if not token:
        raise SystemExit(
            f"\n{var_name} is not set.\n"
            f"  Locally : copy .env.example to .env and paste your token in.\n"
            f"  On Render: add it under the service's Environment settings.\n"
        )
    return token


def get_int(var_name: str, default: int) -> int:
    raw = os.getenv(var_name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def allowed_user_ids() -> set[int]:
    """Empty set means no allowlist, i.e. the bot is open to everyone."""
    raw = os.getenv("ALLOWED_USER_IDS", "").strip()
    if not raw:
        return set()
    return {
        int(chunk.strip())
        for chunk in raw.replace(";", ",").split(",")
        if chunk.strip().isdigit()
    }


# Render assigns the port its router forwards to; 10000 is its usual default.
PORT = get_int("PORT", 10000)


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
def setup_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # aiogram logs every update at INFO, which drowns out our own messages.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    return logging.getLogger(name)


log = logging.getLogger("core")


# --------------------------------------------------------------------------
# Access control
# --------------------------------------------------------------------------
class IsAllowed(Filter):
    """Passes everything when ALLOWED_USER_IDS is empty."""

    def __init__(self) -> None:
        self.allowed = allowed_user_ids()

    async def __call__(self, event: TelegramObject) -> bool:
        if not self.allowed:
            return True
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            return event.from_user.id in self.allowed
        return False


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------
# Telegram throttles bursts - an album of 10 items is easy to trip. When it
# does, it tells us exactly how long to wait, so waiting is the correct fix.
MAX_RETRY_WAIT_SECONDS = 60


async def call_with_retry(factory: Callable[[], Awaitable[T]], attempts: int = 4) -> T:
    """Run a Telegram call, honouring 'retry after N seconds' responses.

    `factory` must build a fresh coroutine each time - a coroutine object can
    only be awaited once, so passing one directly would break on retry.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await factory()
        except TelegramRetryAfter as exc:
            if attempt == attempts or exc.retry_after > MAX_RETRY_WAIT_SECONDS:
                raise
            log.info(
                "rate limited, waiting %ss (attempt %d/%d)",
                exc.retry_after,
                attempt,
                attempts,
            )
            await asyncio.sleep(exc.retry_after)
    raise RuntimeError("unreachable")
