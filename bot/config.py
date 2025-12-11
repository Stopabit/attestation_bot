from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    dsn: str | None = None
    host: str | None = None
    port: int | None = None
    name: str | None = None
    user: str | None = None
    password: str | None = None
    table: str = "test_results"


@dataclass
class ResultStoreConfig:
    backend: str = "file"
    file_path: Path = Path(__file__).parent / "storage" / "results.jsonl"
    db: DatabaseConfig = field(default_factory=DatabaseConfig)


@dataclass
class RoleSettings:
    slug: str
    title: str
    block_two_count: int
    path: Path


@dataclass
class BotConfig:
    token: str
    block_one_count: int = 15
    common_questions_path: Path = Path(__file__).parent / "data" / "questions_all_tests (1).json"
    role_settings: List[RoleSettings] = field(default_factory=list)
    result_store: ResultStoreConfig = field(default_factory=ResultStoreConfig)


def load_config() -> BotConfig:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "")
    default_results = Path(__file__).parent / "storage" / "results.jsonl"
    backend = os.getenv("RESULTS_BACKEND", "file").lower()
    file_path = Path(os.getenv("RESULTS_PATH", default_results)).expanduser()
    if not file_path.is_absolute():
        file_path = default_results.parent / file_path
    db_config = DatabaseConfig(
        dsn=os.getenv("RESULT_DB_DSN") or None,
        host=os.getenv("RESULT_DB_HOST") or None,
        port=int(os.getenv("RESULT_DB_PORT")) if os.getenv("RESULT_DB_PORT") else None,
        name=os.getenv("RESULT_DB_NAME") or None,
        user=os.getenv("RESULT_DB_USER") or None,
        password=os.getenv("RESULT_DB_PASSWORD") or None,
        table=os.getenv("RESULT_DB_TABLE", "test_results"),
    )
    result_store = ResultStoreConfig(
        backend=backend,
        file_path=file_path,
        db=db_config,
    )
    data_dir = Path(__file__).parent / "data"
    roles = [
        RoleSettings(
            slug="oks_manager",
            title="Менеджер ОКС",
            block_two_count=20,
            path=data_dir / "oks_questions_cleaned.json",
        ),
        RoleSettings(
            slug="sales_manager",
            title="Менеджер ОП",
            block_two_count=20,
            path=data_dir / "otdel_prodaj.json",
        ),
        RoleSettings(
            slug="admin_mo",
            title="Администратор МО",
            block_two_count=15,
            path=data_dir / "admin_questions.json",
        ),
        RoleSettings(
            slug="nurse_mo",
            title="Медсестра МО",
            block_two_count=15,
            path=data_dir / "nurse_questions.json",
        ),
    ]
    return BotConfig(
        token=token,
        result_store=result_store,
        common_questions_path=data_dir / "questions_all_tests (1).json",
        role_settings=roles,
    )
