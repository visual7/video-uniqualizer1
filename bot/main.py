"""
Entry point. Run: python -m bot.main
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BOT_TOKEN, LOG_LEVEL, LOCAL_API_URL
from bot.handlers import start, video, settings, presets
from bot.queue_worker.worker import queue


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in .env — cannot start!")
        return

    logger.info("Starting Video Uniqueluzer bot…")

    session = None
    if LOCAL_API_URL:
        logger.info(f"Using LOCAL Bot API server: {LOCAL_API_URL}")
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(LOCAL_API_URL)
        )

    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(presets.router)
    dp.include_router(settings.router)
    dp.include_router(video.router)    # video last — catches unhandled messages

    # Start queue
    await queue.start(bot=bot)

    # Health check
    from bot.utils.ffmpeg import ffmpeg_available, ffprobe_available
    if not ffmpeg_available():
        logger.error("FFmpeg not found! Video processing will fail.")
    if not ffprobe_available():
        logger.error("FFprobe not found! Video analysis will fail.")

    # Drop pending updates & clear webhook (prevents duplicates after restart)
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Bot is polling…")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
