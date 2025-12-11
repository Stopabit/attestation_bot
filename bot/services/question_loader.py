from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..config import RoleSettings


@dataclass
class QuestionBlueprint:
    prompt: str
    topic: str
    options: List[Tuple[str, bool]]
    explanation: str
    meta: Dict[str, object] = field(default_factory=dict)


@dataclass
class RoleQuestionSet:
    slug: str
    title: str
    block_two_count: int
    questions: List[QuestionBlueprint]


@dataclass
class QuestionBank:
    common_questions: List[QuestionBlueprint]
    roles: Dict[str, RoleQuestionSet]


def _build_explanation(options: List[Tuple[str, bool]], fallback: str | None = None) -> str:
    if fallback:
        return fallback
    correct = [text for text, is_correct in options if is_correct]
    if not correct:
        return "Правильный ответ недоступен."
    return "Правильный ответ: " + "; ".join(correct)


def _normalize_prompt_with_code(prompt: str, test_code: str) -> str:
    prefix = f"[Код {test_code}] "
    if prompt.startswith(prefix):
        return prompt
    if f"{test_code}" in prompt:
        return f"{prefix}{prompt}"
    return f"{prefix}{prompt}"


def _load_common_questions(path: Path) -> List[QuestionBlueprint]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    blueprints: List[QuestionBlueprint] = []
    for test in data.get("tests", []):
        test_code = str(test.get("test_code"))
        test_name = (test.get("test_name") or "").strip()
        for raw in test.get("questions", []):
            q_type = raw.get("type")
            prompt = (raw.get("question") or "").strip()
            if not prompt:
                continue
            options: List[Tuple[str, bool]] = []
            explanation: Optional[str] = raw.get("explanation")
            if q_type == "multiple_choice":
                for option in raw.get("options", []):
                    text = (option.get("text") or "").strip()
                    if not text:
                        continue
                    options.append((text, bool(option.get("correct"))))
            elif q_type == "true_false":
                is_true = bool(raw.get("correct"))
                options = [("Да", is_true), ("Нет", not is_true)]
            else:
                # 'identification' и прочие типы не поддерживаются в ботe с кнопками.
                continue
            correct_count = sum(1 for _, is_correct in options if is_correct)
            if not options or correct_count == 0:
                continue
            explanation = _build_explanation(options, fallback=explanation)
            topic = f"Тест {test_code}: {test_name}" if test_name else f"Тест {test_code}"
            blueprints.append(
                QuestionBlueprint(
                    prompt=_normalize_prompt_with_code(prompt, test_code),
                    topic=topic,
                    options=options,
                    explanation=explanation,
                    meta={
                        "source": "common",
                        "test_code": test_code,
                        "test_name": test_name,
                    },
                )
            )
    return blueprints


def _load_role_questions(path: Path, slug: str, title: str) -> List[QuestionBlueprint]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    blueprints: List[QuestionBlueprint] = []
    questions = data.get("questions", [])
    for idx, raw in enumerate(questions, start=1):
        prompt = (raw.get("question") or "").strip()
        if not prompt:
            continue
        options: List[Tuple[str, bool]] = []
        for option in raw.get("options", []):
            text = (option.get("text") or "").strip()
            if not text:
                continue
            options.append((text, bool(option.get("correct"))))
        correct_count = sum(1 for _, is_correct in options if is_correct)
        if not options or correct_count == 0:
            continue
        explanation = _build_explanation(options, fallback=raw.get("explanation"))
        prefix = f"[{title}] Q{raw.get('id', idx)}. "
        blueprints.append(
            QuestionBlueprint(
                prompt=f"{prefix}{prompt}",
                topic=raw.get("topic") or title,
                options=options,
                explanation=explanation,
                meta={
                    "source": slug,
                    "role_title": title,
                },
            )
        )
    return blueprints


def load_question_bank(
    common_path: Path,
    role_settings: Sequence[RoleSettings],
) -> QuestionBank:
    common_questions = _load_common_questions(common_path)
    roles: Dict[str, RoleQuestionSet] = {}
    for role in role_settings:
        roles[role.slug] = RoleQuestionSet(
            slug=role.slug,
            title=role.title,
            block_two_count=role.block_two_count,
            questions=_load_role_questions(role.path, role.slug, role.title),
        )
    return QuestionBank(common_questions=common_questions, roles=roles)
