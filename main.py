"""Entry point: starts the health endpoint and the Telegram poller together."""

from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.core import PORT, IsAllowed, require_token, setup_logging
from bot.handlers import router
from bot.health import start_health_server

log = setup_logging("caption-remover")


async def main() -> None:
    bot = Bot(
        token=require_token("CAPTION_REMOVER_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.filter(IsAllowed())
    dp.include_router(router)

    me = await bot.get_me()
    log.info("Caption remover running as @%s", me.username)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="How to use this bot"),
            BotCommand(command="help", description="Show help"),
        ]
    )
    await bot.delete_webhook(drop_pending_updates=True)

    runner = await start_health_server(PORT, bot=me.username)
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
