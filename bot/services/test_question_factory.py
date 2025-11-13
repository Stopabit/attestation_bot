from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .models import Choice, MatchingItem, Question, QuestionType, TestInfo


def _make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _choice_id(index: int) -> str:
    return f"c{index}"


@dataclass
class TestQuestionFactory:
    tests: List[TestInfo]
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        self.random = random.Random(self.seed)
        self.biomaterial_pool: List[str] = sorted(
            {bm.strip() for test in self.tests for bm in test.biomaterials if bm.strip()}
        )
        self.categories: List[str] = sorted({test.category for test in self.tests})
        self.tests_by_prep_note = [test for test in self.tests if test.prep_note]

    def _meta(self, test: TestInfo, unique_key: str) -> Dict[str, str]:
        return {"unique_key": unique_key, "category": test.category}

    def generate(self, count: int) -> List[Question]:
        builders = [
            self._build_single_biomaterial_question,
            self._build_category_question,
            self._build_multi_biomaterial_question,
            self._build_biomaterial_count_question,
        ]
        # matching-вопросы отключены: в Telegram их неудобно проходить
        questions: List[Question] = []
        attempts = 0
        used: Set[str] = set()
        while len(questions) < count and attempts < count * 8:
            attempts += 1
            builder = self.random.choice(builders)
            question = builder()
            if not question:
                continue
            key = question.meta.get("unique_key")
            if key and key in used:
                continue
            used.add(key or question.id)
            questions.append(question)
        return questions

    def _pick_test(self, *, min_biomaterials: int = 1, max_biomaterials: Optional[int] = None) -> Optional[TestInfo]:
        pool = [
            test
            for test in self.tests
            if len(test.biomaterials) >= min_biomaterials
            and (max_biomaterials is None or len(test.biomaterials) <= max_biomaterials)
        ]
        if not pool:
            return None
        return self.random.choice(pool)

    def _build_single_biomaterial_question(self) -> Optional[Question]:
        test = self._pick_test(min_biomaterials=1)
        if not test or len(self.biomaterial_pool) < 4:
            return None
        correct_option = self.random.choice(test.biomaterials)
        distractors = [
            bm for bm in self.biomaterial_pool if bm not in test.biomaterials
        ]
        if len(distractors) < 3:
            return None
        options = self.random.sample(distractors, 3) + [correct_option]
        self.random.shuffle(options)
        choices = [
            Choice(id=_choice_id(idx), text=value, is_correct=value == correct_option)
            for idx, value in enumerate(options)
        ]
        prompt = (
            f"Исследование [{test.code}] «{test.name}». "
            "Выберите биоматериал, который точно подходит."
        )
        explanation = (
            f"Для [{test.code}] допустимы: {', '.join(test.biomaterials)}."
        )
        return Question(
            id=_make_id("bio-single"),
            block=1,
            topic=f"Тест {test.code}",
            prompt=prompt,
            explanation=explanation,
            type=QuestionType.single_choice,
            choices=choices,
            meta=self._meta(test, f"bio-single-{test.code}-{correct_option}"),
        )

    def _build_multi_biomaterial_question(self) -> Optional[Question]:
        test = self._pick_test(min_biomaterials=2, max_biomaterials=3)
        if not test:
            return None
        actual = test.biomaterials
        distractors = [
            bm for bm in self.biomaterial_pool if bm not in actual
        ]
        if len(distractors) < 2:
            return None
        options = actual + self.random.sample(distractors, 2)
        # remove duplicates while preserving some randomness
        seen = set()
        deduped = []
        for item in options:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        options = deduped
        self.random.shuffle(options)
        choices = [
            Choice(id=_choice_id(idx), text=value, is_correct=value in actual)
            for idx, value in enumerate(options)
        ]
        prompt = (
            f"Исследование [{test.code}] «{test.name}». "
            "Выберите ВСЕ допустимые биоматериалы."
        )
        explanation = (
            f"Корректные образцы: {', '.join(actual)}."
        )
        return Question(
            id=_make_id("bio-multi"),
            block=1,
            topic=f"Тест {test.code}",
            prompt=prompt,
            explanation=explanation,
            type=QuestionType.multi_choice,
            choices=choices,
            meta=self._meta(test, f"bio-multi-{test.code}"),
        )

    def _build_category_question(self) -> Optional[Question]:
        test = self._pick_test()
        if not test or len(self.categories) < 4:
            return None
        other_categories = [cat for cat in self.categories if cat != test.category]
        options = self.random.sample(other_categories, 3) + [test.category]
        self.random.shuffle(options)
        choices = [
            Choice(id=_choice_id(idx), text=value, is_correct=value == test.category)
            for idx, value in enumerate(options)
        ]
        prompt = (
            f"К какому направлению относится исследование [{test.code}] «{test.name}»?"
        )
        explanation = f"Тест [{test.code}] относится к категории «{test.category}»."
        return Question(
            id=_make_id("category"),
            block=1,
            topic=f"Категория теста {test.code}",
            prompt=prompt,
            explanation=explanation,
            type=QuestionType.single_choice,
            choices=choices,
            meta=self._meta(test, f"category-{test.code}"),
        )

    def _build_biomaterial_count_question(self) -> Optional[Question]:
        test = self._pick_test()
        if not test:
            return None
        actual = len(test.biomaterials)
        if actual <= 1:
            return None
        distractors = set()
        while len(distractors) < 3:
            delta = self.random.randint(-2, 2)
            candidate = max(1, actual + delta)
            if candidate != actual:
                distractors.add(candidate)
        options = list(distractors) + [actual]
        self.random.shuffle(options)
        choices = [
            Choice(id=_choice_id(idx), text=str(value), is_correct=value == actual)
            for idx, value in enumerate(options)
        ]
        prompt = (
            f"Сколько типов биоматериала допускает исследование [{test.code}] «{test.name}»?"
        )
        explanation = (
            f"Разрешено {actual} типов: {', '.join(test.biomaterials)}."
        )
        return Question(
            id=_make_id("bio-count"),
            block=1,
            topic=f"Тест {test.code}",
            prompt=prompt,
            explanation=explanation,
            type=QuestionType.single_choice,
            choices=choices,
            meta=self._meta(test, f"bio-count-{test.code}"),
        )

    def _build_matching_question(self) -> Optional[Question]:
        if len(self.tests) < 3:
            return None
        for _ in range(10):
            sample = self.random.sample(self.tests, 3)
            combos = []
            for test in sample:
                preview = ", ".join(test.biomaterials[:2])
                if not preview:
                    break
                combos.append(f"{preview}")
            if len(combos) != 3 or len(set(combos)) != 3:
                continue
            left_items = [
                MatchingItem(id=str(idx + 1), label=f"[{test.code}] {test.name}")
                for idx, test in enumerate(sample)
            ]
            letters = ["A", "B", "C"]
            right_data = list(zip(letters, combos))
            self.random.shuffle(right_data)
            right_items = [
                MatchingItem(id=letter, label=combo) for letter, combo in right_data
            ]
            combo_to_letter = {combo: letter for letter, combo in right_data}
            mapping: Dict[str, str] = {}
            for left, test in zip(left_items, sample):
                combo = ", ".join(test.biomaterials[:2])
                mapping[left.id] = combo_to_letter[combo]
            explanation_parts = [
                f"[{test.code}] → {', '.join(test.biomaterials[:2])}"
                for test in sample
            ]
            prompt_lines = ["Сопоставьте исследования и основные биоматериалы (первые два в списке)."]
            prompt_lines.extend(
                f"{item.id}. {item.label}" for item in left_items
            )
            prompt_lines.append("Варианты биоматериала:")
            prompt_lines.extend(f"{item.id}. {item.label}" for item in right_items)
            prompt = "\n".join(prompt_lines)
            unique_key = "match-" + "-".join(sorted(test.code for test in sample))
            return Question(
                id=_make_id("match"),
                block=1,
                topic="Сопоставление тестов и биоматериалов",
                prompt=prompt,
                explanation="; ".join(explanation_parts),
                type=QuestionType.matching,
                matching_left=left_items,
                matching_right=right_items,
                correct_mapping=mapping,
                meta={"unique_key": unique_key},
            )
        return None
