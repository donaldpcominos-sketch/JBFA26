import json
import time

import requests

from config import build_headers, get_current_round

ROUND = get_current_round()

HEADERS = build_headers(cookie_required=True)

print(f"--- STARTING PLAYER STATS SCRAPE FOR ROUND {ROUND} ---")

try:
    with open("players.json", "r", encoding="utf-8") as f:
        players_raw = json.load(f)
    print(f"Loaded {len(players_raw)} players from players.json.")
except FileNotFoundError:
    print("ERROR: players.json missing. Ensure it is in the same folder.")
    raise SystemExit(1)

all_stats = []
print("Fetching detailed stats from the API...\n")

for i, player in enumerate(players_raw):
    pid = player.get("id")
    name = f"{player.get('first_name', '')} {player.get('last_name', '')}"

    url = f"https://fantasy.nrl.com/data/nrl/stats/players/{pid}.json"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)

        if resp.status_code == 200:
            player_data = resp.json()
            player_data["jbfa_player_id"] = pid
            player_data["jbfa_player_name"] = name
            all_stats.append(player_data)
        else:
            print(f"  [!] Missing data for {name} (ID: {pid}) - Status: {resp.status_code}")

        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(players_raw)} players scraped...")

        time.sleep(0.3)

    except Exception as e:
        print(f"  Error fetching {name}: {e}")

if all_stats:
    filename = f"all_player_stats_r{ROUND}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\n✓ SUCCESS! Saved detailed stats for {len(all_stats)} players.")
    print(f"Check {filename} in this folder.")
else:
    print("\n[!] No stats were collected. Double check your internet connection and cookie.")
    raise SystemExit(1)
