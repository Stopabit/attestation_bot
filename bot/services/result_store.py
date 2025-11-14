from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Protocol

from ..config import DatabaseConfig, ResultStoreConfig
from .models import QuestionResult, QuestionType
from .state import UserProfile


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
    """Blank adapter for будущие интеграции с БД."""

    def __init__(self, config: DatabaseConfig):
        self.config = config

    def append(
        self,
        user_id: int,
        profile: UserProfile,
        result: QuestionResult,
        session_id: str,
    ) -> None:
        payload = _build_payload(user_id, profile, result, session_id)
        raise NotImplementedError(
            "DatabaseResultStore is a placeholder. "
            "Use `payload` together with `self.config` to persist data into the DB."
        )


def build_result_store(config: ResultStoreConfig) -> ResultStore:
    if config.backend == "db":
        return DatabaseResultStore(config.db)
    return FileResultStore(config.file_path)
