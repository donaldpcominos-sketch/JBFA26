from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

LEAGUE_ID = 146595

DEFAULT_CURRENT_ROUND = 3
DEFAULT_ROUND_AVGS = {
    1: 926,
    2: 1034,
    3: 835,
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
)


def _read_text_file(filename: str) -> str | None:
    path = BASE_DIR / filename
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        return value or None
    return None


def _read_json_file(filename: str) -> dict | None:
    path = BASE_DIR / filename
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def get_cookie(required: bool = False) -> str | None:
    cookie = os.getenv("LOGIN_COOKIE") or _read_text_file("cookie.txt")
    if required and not cookie:
        print("ERROR: No cookie found. Paste it into run_all.py when prompted,")
        print("or create a cookie.txt file in this folder.")
        sys.exit(1)
    return cookie


def get_current_round() -> int:
    env_round = os.getenv("CURRENT_ROUND")
    if env_round:
        return int(env_round)

    file_round = _read_text_file("round.txt")
    if file_round:
        return int(file_round)

    return DEFAULT_CURRENT_ROUND


def get_round_avgs() -> dict[int, int]:
    round_avgs = DEFAULT_ROUND_AVGS.copy()

    file_data = _read_json_file("round_avgs.json")
    if isinstance(file_data, dict):
        round_avgs.update({int(k): int(v) for k, v in file_data.items()})

    env_json = os.getenv("ROUND_AVGS_JSON")
    if env_json:
        round_avgs.update({int(k): int(v) for k, v in json.loads(env_json).items()})

    current_round = get_current_round()
    current_avg = os.getenv("ROUND_AVG_CURRENT")
    if current_avg:
        round_avgs[current_round] = int(current_avg)

    return round_avgs


def get_current_round_avg(required: bool = False) -> int | None:
    current_round = get_current_round()
    round_avgs = get_round_avgs()
    value = round_avgs.get(current_round)

    if required and value is None:
        print(f"ERROR: No round average configured for round {current_round}.")
        print("Set ROUND_AVG_CURRENT, update round_avgs.json, or extend DEFAULT_ROUND_AVGS in config.py.")
        sys.exit(1)

    return value


def build_headers(*, cookie_required: bool = False, referer: str | None = None, extra: dict | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
    }

    cookie = get_cookie(required=cookie_required)
    if cookie:
        headers["Cookie"] = cookie
        headers["cookie"] = cookie

    if referer:
        headers["Referer"] = referer
        headers["referer"] = referer

    if extra:
        headers.update(extra)

    return headers
