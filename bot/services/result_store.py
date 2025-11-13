from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .models import QuestionResult, QuestionType
from .state import UserProfile


class ResultStore:
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
        if result.question.type == QuestionType.matching:
            correct_answer = result.question.correct_mapping
        else:
            correct_answer = [
                choice.text for choice in result.question.choices if choice.is_correct
            ]
        payload: Dict[str, Any] = {
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
            },
            "correct_answer": correct_answer,
            "user_answer": result.user_answer,
            "is_correct": result.is_correct,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
