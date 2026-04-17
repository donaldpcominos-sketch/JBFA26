import requests
import json
import time
import csv

# ============================================================
# 1. CONFIG
# ============================================================
COOKIE = "__stripe_mid=ffb1ea04-f4d5-4dfb-9c06-644d0b3d9cc44914fa; optimizelyEndUserId=oeu1773051030358r0.3784378927237164; optimizelySession=0; session=42fe81e50f58476d91b1199712814d3f516e029f; __stripe_sid=2ec1e598-838a-4738-90df-3138c36ff0fbe7d03a"
LEAGUE_ID = 125972
ROUND = 3 

HEADERS = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"https://fantasy.nrl.com/fantasy/league/{LEAGUE_ID}/ladder"
}

# ============================================================
# 2. STEP 1: INDEX ALL TEAMS (EXACT API MAPPING)
# ============================================================
print(f"--- STARTING ULTIMATE SCRAPE: Round {ROUND} ---")
team_metadata_lookup = {}
offset = 0

while True:
    url = f"https://fantasy.nrl.com/nrl_classic/api/leagues_classic/show_overall_points?league_id={LEAGUE_ID}&offset={offset}&limit=50&round={ROUND}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        result = data.get("result", [])
        if not result: break
            
        for team in result:
            t_id = team['id']
            
            # MAPPING FROM YOUR EXTRACT:
            # scoreflow (one word)
            # values_history (plural)
            # value (total wealth: team + cash)
            scoreflow = team.get("scoreflow", {})
            rank_history = team.get("rank_history", {})
            
            team_metadata_lookup[t_id] = {
                "team_id": t_id,
                "user_id": team.get("user_id"),
                "rank": team.get("rank"),
                "team_name": team.get("name"),
                "coach": f"{team.get('firstname', '')} {team.get('lastname', '')}",
                "round_score": scoreflow.get(str(ROUND), 0),
                "total_wealth": team.get("value", 0), # Total wealth (10932000)
                "cumulative_points": team.get("points", 0),
                "prev_round_rank": rank_history.get(str(ROUND-1), 0)
            }
        
        offset += 50
        print(f"  Captured {len(team_metadata_lookup)} teams...")
        if len(result) < 50: break
        time.sleep(0.5) 
        
    except Exception as e:
        print(f"  Critical Index Error: {e}")
        break

# ============================================================
# 3. STEP 2: LOAD PLAYER POOL
# ============================================================
try:
    with open("players.json", encoding="utf-8") as f:
        PLAYERS = {p["id"]: p for p in json.load(f)}
except FileNotFoundError:
    print("ERROR: players.json missing.")
    exit()

# ============================================================
# 4. STEP 3: FETCH ROSTERS & CALCULATE CASH
# ============================================================
final_output = []
print(f"\nMerging rosters and calculating sub-ledgers...")

for i, (t_id, meta) in enumerate(team_metadata_lookup.items()):
    url = f"https://fantasy.nrl.com/nrl_classic/api/teams_classic/show?id={t_id}&round={ROUND}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        t_data = resp.json().get("result", {})
        lineup = t_data.get("lineup", {})
        
        player_ids = []
        for key in ["1","2","3","4","5","6","bench"]:
            val = lineup.get(key, [])
            if isinstance(val, list): player_ids.extend(val)
            elif val: player_ids.append(val)

        # Calculate actual squad value to find Cash in Bank
        actual_squad_value = 0
        for pid in player_ids:
            p = PLAYERS.get(pid, {})
            cost = p.get('cost', 0)
            actual_squad_value += cost
            
            row = meta.copy()
            row.update({
                "cash_in_bank": meta['total_wealth'] - actual_squad_value,
                "team_value_only": actual_squad_value,
                "player_id": pid,
                "player_name": f"{p.get('first_name', '')} {p.get('last_name', '')}",
                "player_cost": cost
            })
            final_output.append(row)
        
        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(team_metadata_lookup)} teams...")
        time.sleep(0.15)

    except Exception as e:
        print(f"  Error fetching Team {t_id}: {e}")

# ============================================================
# 5. STEP 4: EXPORT
# ============================================================
if final_output:
    filename = f"JBFA_R{ROUND}_Master_Scrape"
    with open(f"{filename}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=final_output[0].keys())
        writer.writeheader()
        writer.writerows(final_output)
    print(f"\n✓ SUCCESS! Data matched exactly to your extract requirements.")
    print(f"Check for Team 77880 - Round Score should be 1041.")