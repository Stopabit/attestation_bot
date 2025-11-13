from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QuestionType(str, Enum):
    single_choice = "single_choice"
    multi_choice = "multi_choice"
    matching = "matching"


@dataclass
class Choice:
    id: str
    text: str
    is_correct: bool = False


@dataclass
class MatchingItem:
    id: str
    label: str


@dataclass
class Question:
    id: str
    block: int
    topic: str
    prompt: str
    explanation: str
    type: QuestionType
    choices: List[Choice] = field(default_factory=list)
    matching_left: List[MatchingItem] = field(default_factory=list)
    matching_right: List[MatchingItem] = field(default_factory=list)
    correct_mapping: Dict[str, str] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestInfo:
    code: str
    name: str
    biomaterials: List[str]
    preparation: str
    description: str
    category: str
    prep_note: Optional[str] = None


@dataclass
class QuestionResult:
    question: Question
    is_correct: bool
    user_answer: Any
