from __future__ import annotations

from aiogram import Dispatcher

from ..services.question_engine import QuestionEngine
from ..services.result_store import ResultStore
from . import testing


def register_handlers(
    dp: Dispatcher,
    question_engine: QuestionEngine,
    result_store: ResultStore,
) -> None:
    testing.setup_dependencies(
        question_engine=question_engine,
        result_store=result_store,
    )
    dp.include_router(testing.router)
