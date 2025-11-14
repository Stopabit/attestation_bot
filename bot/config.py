from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

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
class BotConfig:
    token: str
    block_one_count: int = 25
    block_two_count: int = 15
    data_path: Path = Path(__file__).parent / "data" / "tests_raw.json"
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
    return BotConfig(token=token, result_store=result_store)
