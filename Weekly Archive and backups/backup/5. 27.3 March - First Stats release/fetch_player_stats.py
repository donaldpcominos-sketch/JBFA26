import requests
import json
import time

# ============================================================
# 1. CONFIGURATION
# ============================================================
ROUND = 3  # Update this each week
COOKIE = "__stripe_mid=ffb1ea04-f4d5-4dfb-9c06-644d0b3d9cc44914fa; optimizelyEndUserId=oeu1773051030358r0.3784378927237164; optimizelySession=0; session=42fe81e50f58476d91b1199712814d3f516e029f; __stripe_sid=696ff2a2-5f86-4d58-8bd4-91d40a293e2894a787"

HEADERS = {
    "Cookie": COOKIE,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

print(f"--- STARTING PLAYER STATS SCRAPE FOR ROUND {ROUND} ---")

# ============================================================
# 2. LOAD THE MASTER PLAYER LIST
# ============================================================
try:
    with open("players.json", "r", encoding="utf-8") as f:
        players_raw = json.load(f)
    print(f"Loaded {len(players_raw)} players from players.json.")
except FileNotFoundError:
    print("ERROR: players.json missing. Ensure it is in the same folder.")
    exit()

# ============================================================
# 3. LOOP THROUGH EVERY URL
# ============================================================
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
            # Append master ID and Name to the top of their stats 
            player_data["jbfa_player_id"] = pid
            player_data["jbfa_player_name"] = name 
            all_stats.append(player_data)
        else:
            print(f"  [!] Missing data for {name} (ID: {pid}) - Status: {resp.status_code}")

        # Progress tracker
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i+1}/{len(players_raw)} players scraped...")

        # 0.3 second delay to prevent the server from blocking your connection
        time.sleep(0.3) 

    except Exception as e:
        print(f"  Error fetching {name}: {e}")

# ============================================================
# 4. SAVE THE WEEKLY SNAPSHOT
# ============================================================
if all_stats:
    filename = f"all_player_stats_r{ROUND}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\n✓ SUCCESS! Saved detailed stats for {len(all_stats)} players.")
    print(f"Check {filename} on your desktop.")
else:
    print("\n[!] No stats were collected. Double check your internet connection and cookie.")