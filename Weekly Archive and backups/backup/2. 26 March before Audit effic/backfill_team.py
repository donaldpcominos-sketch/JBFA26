import requests
import json
import time
import csv
import os
import shutil

# ============================================================
# CONFIG — edit these before each backfill run
# ============================================================
COOKIE = "__stripe_mid=ffb1ea04-f4d5-4dfb-9c06-644d0b3d9cc44914fa; optimizelyEndUserId=oeu1773051030358r0.3784378927237164; optimizelySession=0; session=37994d55e11c5b84ea57de51d0fe8bfc76b10bfd; __stripe_sid=84673491-ed11-4e9e-b6ab-c3ba2d9edea44e1014"
LEAGUE_ID    = 125972
TEAM_IDS     = [123456]     # ← list of team IDs to backfill (can be multiple)
ROUND_START  = 1            # ← first round to backfill
ROUND_END    = 2            # ← last round to backfill (inclusive)

HEADERS = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"https://fantasy.nrl.com/fantasy/league/{LEAGUE_ID}/ladder"
}

# ============================================================
# LOAD PLAYERS.JSON
# ============================================================
try:
    with open("players.json", encoding="utf-8") as f:
        PLAYERS = {p["id"]: p for p in json.load(f)}
except FileNotFoundError:
    print("ERROR: players.json not found. Run fetch_master_players.py first.")
    exit()

# ============================================================
# HELPERS
# ============================================================

def fetch_team_meta(team_id, round_num):
    """Fetch team metadata (score, rank, wealth) for a given round."""
    url = (
        f"https://fantasy.nrl.com/nrl_classic/api/leagues_classic/show_overall_points"
        f"?league_id={LEAGUE_ID}&offset=0&limit=50&round={round_num}"
    )
    # We can't filter by team directly on the ladder endpoint, so page through
    offset = 0
    while True:
        url = (
            f"https://fantasy.nrl.com/nrl_classic/api/leagues_classic/show_overall_points"
            f"?league_id={LEAGUE_ID}&offset={offset}&limit=50&round={round_num}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        result = resp.json().get("result", [])
        if not result:
            break
        for team in result:
            if team["id"] == team_id:
                scoreflow   = team.get("scoreflow", {})
                rank_history = team.get("rank_history", {})
                return {
                    "team_id":          team_id,
                    "user_id":          team.get("user_id"),
                    "rank":             team.get("rank"),
                    "team_name":        team.get("name"),
                    "coach":            f"{team.get('firstname', '')} {team.get('lastname', '')}",
                    "round_score":      scoreflow.get(str(round_num), 0),
                    "total_wealth":     team.get("value", 0),
                    "cumulative_points":team.get("points", 0),
                    "prev_round_rank":  rank_history.get(str(round_num - 1), 0),
                }
        if len(result) < 50:
            break
        offset += 50
        time.sleep(0.3)
    return None


def fetch_team_roster(team_id, round_num, meta):
    """Fetch roster for a team in a given round, returns list of row dicts."""
    url = f"https://fantasy.nrl.com/nrl_classic/api/teams_classic/show?id={team_id}&round={round_num}"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    t_data = resp.json().get("result", {})
    lineup = t_data.get("lineup", {})

    player_ids = []
    for key in ["1", "2", "3", "4", "5", "6", "bench"]:
        val = lineup.get(key, [])
        if isinstance(val, list):
            player_ids.extend(val)
        elif val:
            player_ids.append(val)

    rows = []
    actual_squad_value = 0
    for pid in player_ids:
        p    = PLAYERS.get(pid, {})
        cost = p.get("cost", 0)
        actual_squad_value += cost
        row  = meta.copy()
        row.update({
            "cash_in_bank":    meta["total_wealth"] - actual_squad_value,
            "team_value_only": actual_squad_value,
            "player_id":       pid,
            "player_name":     f"{p.get('first_name', '')} {p.get('last_name', '')}",
            "player_cost":     cost,
        })
        rows.append(row)
    return rows


def merge_into_csv(filepath, new_rows):
    """
    Read existing CSV, remove any rows for the target team_ids (to avoid dupes),
    append new rows, sort by team_id, write atomically via temp file.
    """
    target_ids = {r["team_id"] for r in new_rows}

    existing_rows = []
    if os.path.exists(filepath):
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if int(row["team_id"]) not in target_ids:
                    existing_rows.append(row)

    # Normalise new_rows to strings (DictWriter needs consistent types)
    combined = existing_rows + [{k: str(v) for k, v in r.items()} for r in new_rows]
    combined.sort(key=lambda r: int(r["team_id"]))

    # Determine fieldnames from existing file or new rows
    if existing_rows:
        fieldnames = list(existing_rows[0].keys())
    else:
        fieldnames = list(new_rows[0].keys())

    tmp = filepath + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(combined)

    shutil.move(tmp, filepath)
    return len(combined)


# ============================================================
# MAIN
# ============================================================
print(f"Backfilling team(s) {TEAM_IDS} for rounds {ROUND_START}–{ROUND_END}")
print("=" * 55)

for round_num in range(ROUND_START, ROUND_END + 1):
    csv_path = f"JBFA_R{round_num}_Master_Scrape.csv"
    round_rows = []

    for team_id in TEAM_IDS:
        print(f"  R{round_num} | Team {team_id} — fetching metadata...")
        meta = fetch_team_meta(team_id, round_num)
        if meta is None:
            print(f"  ⚠️  Team {team_id} not found in league ladder for R{round_num} — skipping")
            continue

        time.sleep(0.3)
        print(f"  R{round_num} | Team {team_id} — fetching roster...")
        rows = fetch_team_roster(team_id, round_num, meta)
        if not rows:
            print(f"  ⚠️  No roster rows returned for team {team_id} R{round_num}")
            continue

        round_rows.extend(rows)
        print(f"  ✓  Team {team_id} R{round_num}: {len(rows)} player rows fetched")
        time.sleep(0.3)

    if round_rows:
        total = merge_into_csv(csv_path, round_rows)
        print(f"  → Merged into {csv_path} ({total} total rows)\n")
    else:
        print(f"  → Nothing to merge for R{round_num}\n")

print("Done. Now re-run generate_data.py to rebuild data.json.")
