from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from getpass import getpass
from pathlib import Path

import pandas as pd

from config import BASE_DIR, get_current_round

SCRIPTS = [
    ("Fetch Rosters", "fetch_rosters.py"),
    ("Fetch Master Players", "fetch_master_players.py"),
    ("Fetch Fantasy Coach", "fetch_fantasy_coach.py"),
    # ❌ REMOVED: ("Fetch Player Stats", "fetch_player_stats.py"),
    ("Generate Data", "generate_data.py"),
]

ROUND_AVGS_FILE = BASE_DIR / "round_avgs.json"
MASTER_FILE = BASE_DIR / "MASTER.xlsx"


def prompt_with_default(label: str, default: str | int | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    return "" if default is None else str(default)


def run_step(step_name: str, script_name: str, env: dict[str, str]) -> None:
    script_path = BASE_DIR / script_name

    print(f"\n{'=' * 68}")
    print(f"▶ Running: {step_name}")
    print(f"   File: {script_name}")
    print(f"{'=' * 68}")

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_path}")

    step_start = time.time()
    result = subprocess.run([sys.executable, str(script_path)], cwd=BASE_DIR, env=env)
    duration = round(time.time() - step_start, 2)

    if result.returncode != 0:
        raise RuntimeError(f"{step_name} failed after {duration}s")

    print(f"✅ Completed: {step_name} ({duration}s)")


def load_round_avgs() -> dict[str, int]:
    if ROUND_AVGS_FILE.exists():
        with open(ROUND_AVGS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
        return {str(k): int(v) for k, v in raw.items()}
    return {}


def save_round_avgs(round_avgs: dict[str, int]) -> None:
    ordered = dict(sorted(((str(k), int(v)) for k, v in round_avgs.items()), key=lambda x: int(x[0])))
    with open(ROUND_AVGS_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, indent=2)


def calculate_and_store_round_avg(round_num: int) -> int:
    print(f"\n{'-' * 68}")
    print(f"📊 Calculating round {round_num} average from MASTER.xlsx + scrape CSV")
    print(f"{'-' * 68}")

    scrape_file = BASE_DIR / f"JBFA_R{round_num}_Master_Scrape.csv"
    if not MASTER_FILE.exists():
        raise FileNotFoundError(f"Missing required file: {MASTER_FILE.name}")
    if not scrape_file.exists():
        raise FileNotFoundError(f"Missing required file: {scrape_file.name}")

    master = pd.read_excel(MASTER_FILE)
    master.columns = [str(c).strip() for c in master.columns]
    if "Team ID" not in master.columns:
        raise KeyError("MASTER.xlsx must contain a 'Team ID' column")

    valid_team_ids = (
        pd.to_numeric(master["Team ID"], errors="coerce")
        .dropna()
        .astype(int)
    )
    valid_team_ids = set(valid_team_ids.tolist())

    if not valid_team_ids:
        raise ValueError("No valid Team ID values found in MASTER.xlsx")

    scrape = pd.read_csv(scrape_file)
    scrape.columns = [str(c).strip() for c in scrape.columns]

    required_cols = {"team_id", "round_score"}
    missing = required_cols - set(scrape.columns)
    if missing:
        raise KeyError(f"{scrape_file.name} missing required columns: {sorted(missing)}")

    scrape["team_id"] = pd.to_numeric(scrape["team_id"], errors="coerce")
    scrape["round_score"] = pd.to_numeric(scrape["round_score"], errors="coerce")

    filtered = scrape[scrape["team_id"].notna() & scrape["round_score"].notna()].copy()
    filtered["team_id"] = filtered["team_id"].astype(int)

    filtered = filtered.drop_duplicates(subset=["team_id"], keep="first")
    filtered = filtered[filtered["team_id"].isin(valid_team_ids)]

    if filtered.empty:
        raise ValueError("No matching JBFA teams found when calculating the round average")

    matched_count = len(filtered)
    expected_count = len(valid_team_ids)
    if matched_count < max(10, expected_count * 0.5):
        print(
            f"⚠️ Warning: only matched {matched_count} of {expected_count} Team IDs "
            "from MASTER.xlsx"
        )

    round_avg = int(round(filtered["round_score"].mean(), 0))

    round_avgs = load_round_avgs()
    round_avgs[str(round_num)] = round_avg
    save_round_avgs(round_avgs)

    print(f"✅ Round {round_num} average = {round_avg}")
    print(f"✅ round_avgs.json updated for R{round_num}")
    return round_avg


def main() -> None:
    total_start = time.time()

    default_round = get_current_round()

    print("JBFA pipeline runner")
    print("-" * 68)
    print("Paste a fresh cookie once and the runner will pass it to every script.")
    print("Leave cookie blank only if you already maintain a cookie.txt file.")
    print("The round average is now calculated automatically after fetch_rosters.py.")
    print("-" * 68)

    cookie = input("Paste cookie: ").strip()
    round_value = prompt_with_default("Current round", default_round)

    env = os.environ.copy()
    env["CURRENT_ROUND"] = round_value

    if cookie:
        env["LOGIN_COOKIE"] = cookie

    try:
        current_round_int = int(round_value)
    except ValueError as exc:
        raise SystemExit(f"Invalid round value: {round_value}") from exc

    try:
        run_step("Fetch Rosters", "fetch_rosters.py", env)

        round_avg = calculate_and_store_round_avg(current_round_int)
        env["ROUND_AVG_CURRENT"] = str(round_avg)
        env["ROUND_AVGS_JSON"] = json.dumps(load_round_avgs())

        for step_name, script_name in SCRIPTS[1:]:
            run_step(step_name, script_name, env)
    except Exception as exc:
        total_duration = round(time.time() - total_start, 2)
        print(f"\n❌ Pipeline stopped: {exc}")
        print(f"Total runtime before failure: {total_duration}s")
        sys.exit(1)

    total_duration = round(time.time() - total_start, 2)
    print(f"\n🎉 All scripts completed successfully")
    print(f"Total runtime: {total_duration}s")


if __name__ == "__main__":
    main()