from __future__ import annotations

from typing import Any, List, Optional, Tuple

from .models import Question, QuestionResult, QuestionType, TestInfo
from .process_question_factory import ProcessQuestionFactory
from .test_question_factory import TestQuestionFactory


class QuestionEngine:
    def __init__(self, tests: List[TestInfo], seed: Optional[int] = None):
        self.test_factory = TestQuestionFactory(tests=tests, seed=seed)
        self.process_factory = ProcessQuestionFactory(seed=seed)

    def build_blocks(self, block_one_count: int, block_two_count: int) -> Tuple[List[Question], List[Question]]:
        block_one = self.test_factory.generate(block_one_count)
        block_two = self.process_factory.generate(block_two_count)
        return block_one, block_two

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
