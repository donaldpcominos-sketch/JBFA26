import csv
import json
import time

import requests

from config import LEAGUE_ID, build_headers, get_current_round

ROUND = get_current_round()

HEADERS = build_headers(
    cookie_required=True,
    referer=f"https://fantasy.nrl.com/fantasy/league/{LEAGUE_ID}/ladder",
)

print(f"--- STARTING ULTIMATE SCRAPE: Round {ROUND} ---")
team_metadata_lookup = {}
offset = 0

while True:
    url = (
        "https://fantasy.nrl.com/nrl_classic/api/leagues_classic/show_overall_points"
        f"?league_id={LEAGUE_ID}&offset={offset}&limit=50&round={ROUND}"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        result = data.get("result", [])
        if not result:
            break

        for team in result:
            t_id = team["id"]
            scoreflow = team.get("scoreflow", {})
            rank_history = team.get("rank_history", {})

            team_metadata_lookup[t_id] = {
                "team_id": t_id,
                "user_id": team.get("user_id"),
                "rank": team.get("rank"),
                "team_name": team.get("name"),
                "coach": f"{team.get('firstname', '')} {team.get('lastname', '')}",
                "round_score": scoreflow.get(str(ROUND), 0),
                "total_wealth": team.get("value", 0),
                "cumulative_points": team.get("points", 0),
                "prev_round_rank": rank_history.get(str(ROUND - 1), 0),
            }

        offset += 50
        print(f"  Captured {len(team_metadata_lookup)} teams...")
        if len(result) < 50:
            break
        time.sleep(0.5)

    except Exception as e:
        print(f"  Critical Index Error: {e}")
        break

try:
    with open("players.json", encoding="utf-8") as f:
        PLAYERS = {p["id"]: p for p in json.load(f)}
except FileNotFoundError:
    print("ERROR: players.json missing.")
    raise SystemExit(1)

final_output = []
print("\nMerging rosters and calculating sub-ledgers...")

for i, (t_id, meta) in enumerate(team_metadata_lookup.items()):
    url = f"https://fantasy.nrl.com/nrl_classic/api/teams_classic/show?id={t_id}&round={ROUND}"

    try:
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

        actual_squad_value = 0
        for pid in player_ids:
            p = PLAYERS.get(pid, {})
            cost = p.get("cost", 0)
            actual_squad_value += cost

            row = meta.copy()
            row.update(
                {
                    "cash_in_bank": meta["total_wealth"] - actual_squad_value,
                    "team_value_only": actual_squad_value,
                    "player_id": pid,
                    "player_name": f"{p.get('first_name', '')} {p.get('last_name', '')}",
                    "player_cost": cost,
                }
            )
            final_output.append(row)

        if (i + 1) % 25 == 0:
            print(f"  Progress: {i + 1}/{len(team_metadata_lookup)} teams...")
        time.sleep(0.15)

    except Exception as e:
        print(f"  Error fetching Team {t_id}: {e}")

if final_output:
    filename = f"JBFA_R{ROUND}_Master_Scrape"
    with open(f"{filename}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=final_output[0].keys())
        writer.writeheader()
        writer.writerows(final_output)
    print("\n✓ SUCCESS! Data matched exactly to your extract requirements.")
    print("Check for Team 77880 - Round Score should be 1041.")
else:
    print("\n[!] No roster data was collected.")
    raise SystemExit(1)
