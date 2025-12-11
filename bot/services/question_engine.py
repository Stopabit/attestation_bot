from __future__ import annotations

import random
import uuid
from typing import Any, List, Optional, Tuple

from .models import Choice, Question, QuestionResult, QuestionType
from .question_loader import QuestionBank, QuestionBlueprint, RoleQuestionSet


def _make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class QuestionEngine:
    def __init__(
        self,
        bank: QuestionBank,
        block_one_count: int,
        seed: Optional[int] = None,
    ):
        self.bank = bank
        self.block_one_count = block_one_count
        self.random = random.Random(seed)

    def list_roles(self) -> List[RoleQuestionSet]:
        return list(self.bank.roles.values())

    def get_role(self, slug: str) -> Optional[RoleQuestionSet]:
        return self.bank.roles.get(slug)

    def build_blocks(self, role_slug: str) -> Tuple[List[Question], List[Question]]:
        block_one = self._build_block(
            pool=self.bank.common_questions,
            count=self.block_one_count,
            block_number=1,
        )
        role = self.get_role(role_slug)
        if not role:
            raise ValueError(f"Unknown role: {role_slug}")
        block_two = self._build_block(
            pool=role.questions,
            count=role.block_two_count,
            block_number=2,
        )
        return block_one, block_two

    def _build_block(
        self,
        pool: List[QuestionBlueprint],
        count: int,
        block_number: int,
    ) -> List[Question]:
        if not pool:
            return []
        sample_size = min(count, len(pool))
        selected = self.random.sample(pool, sample_size)
        return [self._materialize(q, block_number) for q in selected]

    def _materialize(self, blueprint: QuestionBlueprint, block_number: int) -> Question:
        options = list(blueprint.options)
        self.random.shuffle(options)
        correct_count = sum(1 for _, is_correct in options if is_correct)
        qtype = QuestionType.multi_choice if correct_count > 1 else QuestionType.single_choice
        choices = [
            Choice(id=f"c{idx + 1}", text=text, is_correct=is_correct)
            for idx, (text, is_correct) in enumerate(options)
        ]
        return Question(
            id=_make_id(f"b{block_number}"),
            block=block_number,
            topic=blueprint.topic,
            prompt=blueprint.prompt,
            explanation=blueprint.explanation,
            type=qtype,
            choices=choices,
            meta=dict(blueprint.meta),
        )

    def evaluate(self, question: Question, user_answer: Any) -> QuestionResult:
        if question.type == QuestionType.single_choice:
            correct_ids = {choice.id for choice in question.choices if choice.is_correct}
            is_correct = user_answer in correct_ids
        elif question.type == QuestionType.multi_choice:
            correct_ids = {choice.id for choice in question.choices if choice.is_correct}
            user_ids = set(user_answer or [])
            is_correct = user_ids == correct_ids and bool(user_ids)
        elif question.type == QuestionType.matching:
            user_mapping = dict(user_answer or {})
            is_correct = user_mapping == question.correct_mapping
        else:
            is_correct = False
        return QuestionResult(
            question=question,
            is_correct=is_correct,
            user_answer=user_answer,
        )
