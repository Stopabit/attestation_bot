from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class BotConfig:
    token: str
    block_one_count: int = 25
    block_two_count: int = 15
    data_path: Path = Path(__file__).parent / "data" / "tests_raw.json"
    results_path: Path = Path(__file__).parent / "storage" / "results.jsonl"


def load_config() -> BotConfig:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "")
    return BotConfig(token=token)
