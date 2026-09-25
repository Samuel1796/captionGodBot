"""Caption remover handlers.

Send any media (photo, video, GIF, document, audio, voice, album...) and the
bot sends the same media straight back with the caption stripped off.

Nothing is downloaded or re-encoded: the file never leaves Telegram's servers,
so the returned media is identical to what was sent and it is instant even for
large videos. There is no file size limit, because nothing is ever uploaded.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InputMediaAnimation,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from bot.core import call_with_retry, setup_logging

log = setup_logging("caption-remover")
router = Router()

# Telegram delivers an album as several separate updates. Wait this long after
# the last piece arrives before assuming the album is complete.
ALBUM_DEBOUNCE_SECONDS = 1.0

AlbumKey = tuple[int, str]
_albums: dict[AlbumKey, list[Message]] = defaultdict(list)
_album_flushers: dict[AlbumKey, asyncio.Task] = {}

HAS_MEDIA = (
    F.photo
    | F.video
    | F.animation
    | F.document
    | F.audio
    | F.voice
    | F.video_note
    | F.sticker
)

HELP_TEXT = (
    "<b>Caption Remover</b>\n\n"
    "Send me any media and I'll send it right back with the caption removed.\n\n"
    "Works with:\n"
    "• photos, videos, GIFs and documents\n"
    "• audio files and voice notes\n"
    "• whole albums - send them together and you get a clean album back\n"
    "• forwarded media\n\n"
    "The file is never re-uploaded or re-compressed, so quality is untouched "
    "and there is no size limit."
)


@router.message(CommandStart())
@router.message(Command("help"))
async def on_start(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(HAS_MEDIA)
async def on_media(message: Message, bot: Bot) -> None:
    if message.media_group_id:
        _buffer_album_item(message, bot)
        return
    await _send_without_caption(bot, [message])


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message) -> None:
    await message.answer(
        "That's a text message - there's no caption to remove.\n"
        "Send me a photo, video, GIF, document or album instead."
    )


def _buffer_album_item(message: Message, bot: Bot) -> None:
    """Collect album pieces and (re)arm a timer to flush them as one batch."""
    key: AlbumKey = (message.chat.id, message.media_group_id or "")
    _albums[key].append(message)

    pending = _album_flushers.get(key)
    if pending:
        pending.cancel()
    _album_flushers[key] = asyncio.create_task(_flush_album(bot, key))


async def _flush_album(bot: Bot, key: AlbumKey) -> None:
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return  # another piece arrived; a fresh timer has taken over
    batch = sorted(_albums.pop(key, []), key=lambda m: m.message_id)
    _album_flushers.pop(key, None)
    if batch:
        await _send_without_caption(bot, batch)


async def _send_without_caption(bot: Bot, batch: list[Message]) -> None:
    """Preferred path: ask Telegram to copy the messages minus their captions."""
    chat_id = batch[0].chat.id
    try:
        await call_with_retry(
            lambda: bot.copy_messages(
                chat_id=chat_id,
                from_chat_id=chat_id,
                message_ids=[m.message_id for m in batch],
                remove_caption=True,
            )
        )
        return
    except TelegramAPIError as exc:
        # e.g. the source chat has content protection enabled, or the media
        # type is not copyable. Re-send by file_id instead.
        log.warning("copy_messages failed (%s); falling back to file_id resend", exc)

    try:
        await _resend_by_file_id(bot, batch)
    except TelegramAPIError as exc:
        log.error("fallback resend failed: %s", exc)
        await bot.send_message(
            chat_id, "Sorry, I couldn't process that media. Please try again."
        )


async def _resend_by_file_id(bot: Bot, batch: list[Message]) -> None:
    chat_id = batch[0].chat.id
    if len(batch) > 1:
        media = [item for m in batch if (item := _as_input_media(m)) is not None]
        if media:
            await call_with_retry(lambda: bot.send_media_group(chat_id, media=media))
            return
    for message in batch:
        await _resend_single(bot, message)


def _as_input_media(message: Message):
    """Map a received album item to its InputMedia equivalent, caption dropped."""
    spoiler = bool(message.has_media_spoiler)
    if message.photo:
        return InputMediaPhoto(media=message.photo[-1].file_id, has_spoiler=spoiler)
    if message.video:
        return InputMediaVideo(media=message.video.file_id, has_spoiler=spoiler)
    if message.animation:
        return InputMediaAnimation(media=message.animation.file_id, has_spoiler=spoiler)
    if message.audio:
        return InputMediaAudio(media=message.audio.file_id)
    if message.document:
        return InputMediaDocument(media=message.document.file_id)
    return None


async def _resend_single(bot: Bot, message: Message) -> None:
    chat_id = message.chat.id
    spoiler = bool(message.has_media_spoiler)
    if message.photo:
        await bot.send_photo(chat_id, message.photo[-1].file_id, has_spoiler=spoiler)
    elif message.video:
        await bot.send_video(chat_id, message.video.file_id, has_spoiler=spoiler)
    elif message.animation:
        await bot.send_animation(chat_id, message.animation.file_id, has_spoiler=spoiler)
    elif message.audio:
        await bot.send_audio(chat_id, message.audio.file_id)
    elif message.voice:
        await bot.send_voice(chat_id, message.voice.file_id)
    elif message.video_note:
        await bot.send_video_note(chat_id, message.video_note.file_id)
    elif message.sticker:
        await bot.send_sticker(chat_id, message.sticker.file_id)
    elif message.document:
        await bot.send_document(chat_id, message.document.file_id)
