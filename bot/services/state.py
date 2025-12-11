from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .models import Question, QuestionResult


@dataclass
class UserProfile:
    full_name: str
    position: str


@dataclass
class Session:
    profile: UserProfile
    block_one: List[Question]
    block_two: List[Question]
    current_block: int = 1
    current_index: int = 0
    answers: List[QuestionResult] = field(default_factory=list)
    question_message_id: Optional[int] = None
    multi_choice_state: Dict[str, Set[str]] = field(default_factory=dict)
    matching_state: Dict[str, Dict[str, str]] = field(default_factory=dict)
    matching_focus: Dict[str, Optional[str]] = field(default_factory=dict)
    review_index: Optional[int] = None
    block_titles: Dict[int, str] = field(default_factory=lambda: {1: "Блок 1", 2: "Блок 2"})
    role_slug: Optional[str] = None

    @property
    def is_completed(self) -> bool:
        return self.current_block == 2 and self.current_index >= len(self.block_two)

    def total_questions(self) -> int:
        return len(self.block_one) + len(self.block_two)

    def answered_count(self) -> int:
        return len(self.answers)

    def current_list(self) -> List[Question]:
        return self.block_one if self.current_block == 1 else self.block_two

    def current_question(self) -> Question:
        return self.current_list()[self.current_index]

    def advance(self) -> str:
        """Return status: 'next', 'switch', or 'done'."""
        self.current_index += 1
        if self.current_block == 1 and self.current_index >= len(self.block_one):
            if self.block_two:
                self.current_block = 2
                self.current_index = 0
                return "switch"
            return "done"
        if self.current_block == 2 and self.current_index >= len(self.block_two):
            return "done"
        return "next"
