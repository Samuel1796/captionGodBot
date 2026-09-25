"""Entry point: serves the HTTP endpoint and receives Telegram updates.

Two modes, chosen automatically with no configuration:

* **Deployed** (RENDER_EXTERNAL_URL is set) - webhook. Telegram POSTs each
  update to this service. That inbound request is the only thing that can wake
  a sleeping free instance, so a message sent while asleep both wakes the bot
  and gets handled. Polling could never do that: it is outbound traffic, so a
  sleeping polling bot stays asleep no matter how many messages arrive.
* **Local** - long polling, so no public URL is needed.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.core import (
    PORT,
    WEBHOOK_BASE_URL,
    IsAllowed,
    require_token,
    setup_logging,
    use_webhook,
    webhook_path_and_secret,
)
from bot.handlers import router
from bot.health import build_app, serve

log = setup_logging("caption-remover")


async def main() -> None:
    token = require_token("CAPTION_REMOVER_TOKEN")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp = Dispatcher()
    dp.message.filter(IsAllowed())
    dp.include_router(router)

    me = await bot.get_me()
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="How to use this bot"),
            BotCommand(command="help", description="Show help"),
        ]
    )

    if use_webhook():
        await _run_webhook(bot, dp, token, me.username)
    else:
        await _run_polling(bot, dp, me.username)


async def _run_webhook(bot: Bot, dp: Dispatcher, token: str, username: str) -> None:
    path, secret = webhook_path_and_secret(token)

    app = build_app(bot=username, mode="webhook")
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(
        app, path=path
    )
    setup_application(app, dp, bot=bot)
    runner = await serve(app, PORT)

    # drop_pending_updates stays False on purpose: media sent while the
    # instance was asleep is queued by Telegram, and we want it delivered on
    # wake rather than silently discarded.
    await bot.set_webhook(
        f"{WEBHOOK_BASE_URL}{path}",
        secret_token=secret,
        drop_pending_updates=False,
    )
    log.info("Caption remover running as @%s (webhook)", username)

    try:
        await asyncio.Event().wait()  # serve until the platform stops us
    finally:
        await runner.cleanup()
        await bot.session.close()


async def _run_polling(bot: Bot, dp: Dispatcher, username: str) -> None:
    app = build_app(bot=username, mode="polling")
    runner = await serve(app, PORT)

    await bot.delete_webhook(drop_pending_updates=False)
    log.info("Caption remover running as @%s (polling)", username)

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
