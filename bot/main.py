from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import load_config
from .handlers import register_handlers
from .services.question_engine import QuestionEngine
from .services.question_loader import parse_tests
from .services.result_store import build_result_store


async def main() -> None:
    config = load_config()
    if not config.token:
        raise RuntimeError("BOT_TOKEN не найден. Добавьте его в .env.")
    tests = parse_tests(config.data_path)
    question_engine = QuestionEngine(tests=tests)
    result_store = build_result_store(config.result_store)
    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(
        dp=dp,
        question_engine=question_engine,
        result_store=result_store,
        block_one_count=config.block_one_count,
        block_two_count=config.block_two_count,
    )
    bot = Bot(
        token=config.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
