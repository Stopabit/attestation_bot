from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Protocol

from ..config import DatabaseConfig, ResultStoreConfig
from .models import QuestionResult, QuestionType
from .state import UserProfile

logger = logging.getLogger(__name__)

def _build_payload(
    user_id: int,
    profile: UserProfile,
    result: QuestionResult,
    session_id: str,
) -> Dict[str, Any]:
    if result.question.type == QuestionType.matching:
        correct_answer = result.question.correct_mapping
    else:
        correct_answer = [
            choice.text for choice in result.question.choices if choice.is_correct
        ]
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "user_id": user_id,
        "profile": asdict(profile),
        "question": {
            "id": result.question.id,
            "type": result.question.type.value,
            "prompt": result.question.prompt,
            "block": result.question.block,
            "topic": result.question.topic,
            "meta": result.question.meta,
        },
        "correct_answer": correct_answer,
        "user_answer": result.user_answer,
        "is_correct": result.is_correct,
    }


class ResultStore(Protocol):
    def append(
        self,
        user_id: int,
        profile: UserProfile,
        result: QuestionResult,
        session_id: str,
    ) -> None: ...


class FileResultStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def append(
        self,
        user_id: int,
        profile: UserProfile,
        result: QuestionResult,
        session_id: str,
    ) -> None:
        payload = _build_payload(user_id, profile, result, session_id)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


class DatabaseResultStore:
    """Blank adapter for будущие интеграции с БД.

    Пока подключения нет, результаты складываются в fallback-файл.
    """

    def __init__(self, config: DatabaseConfig, fallback_path: Path):
        self.config = config
        self._fallback = FileResultStore(fallback_path)
        self._warned = False

    def append(
        self,
        user_id: int,
        profile: UserProfile,
        result: QuestionResult,
        session_id: str,
    ) -> None:
        if not self._warned:
            logger.warning(
                "DatabaseResultStore fallback in use — results are written to %s. "
                "Replace append() with DB integration when ready.",
                self._fallback.path,
            )
            self._warned = True
        self._fallback.append(user_id, profile, result, session_id)


def build_result_store(config: ResultStoreConfig) -> ResultStore:
    if config.backend == "db":
        return DatabaseResultStore(config.db, config.file_path)
    return FileResultStore(config.file_path)
