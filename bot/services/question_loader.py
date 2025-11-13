from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import TestInfo
from .text_utils import html_to_text


def extract_prep_note(raw: str | None) -> str | None:
    text = (raw or "").lower()
    if not text:
        return None
    if "натощ" in text:
        return "Натощак, без еды"
    if "не требуется" in text or "нет" in text:
        return "Специальной подготовки нет"
    if "за 24" in text or "исключить" in text:
        return "Есть ограничения, уточните подготовку"
    return None


def derive_category(name: str) -> str:
    lower = name.lower()
    if "нипт" in lower:
        return "НИПТ / пренатальная диагностика"
    if "онко" in lower or "опухол" in lower:
        return "Онкогенетика"
    if "скрининг" in lower:
        return "Скрининги"
    if "фармакоген" in lower or "фармако" in lower:
        return "Фармакогенетика"
    if "кардио" in lower or "тромбо" in lower:
        return "Кардиогенетика"
    if "профиль" in lower or "панель" in lower:
        return "Генетические панели"
    return "Другие исследования"


def parse_tests(path: Path) -> List[TestInfo]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    # JSON вложен внутрь SQL-запроса => берём первый ключ.
    records = next(iter(data.values()))
    tests: List[TestInfo] = []
    for record in records:
        biomaterials_raw = record.get("Объекты исследования") or ""
        biomaterials = [
            part.strip()
            for part in biomaterials_raw.split(",")
            if part.strip()
        ]
        tests.append(
            TestInfo(
                code=str(record.get("Код")),
                name=record.get("Название", "").strip(),
                biomaterials=biomaterials,
                preparation=html_to_text(record.get("Как пройти исследование?", "")),
                description=html_to_text(record.get("Информация об исследовании", "")),
                category=derive_category(record.get("Название", "")),
                prep_note=extract_prep_note(record.get("Как пройти исследование?", "")),
            )
        )
    return tests
