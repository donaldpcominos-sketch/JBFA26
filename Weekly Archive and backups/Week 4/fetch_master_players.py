import json

import requests

from config import build_headers

print("--- FETCHING OFFICIAL NRL FANTASY PLAYER DATABASE ---")

URL = "https://fantasy.nrl.com/data/nrl/players.json"
HEADERS = build_headers()

try:
    print(f"Connecting to {URL}...")
    response = requests.get(URL, headers=HEADERS, timeout=10)

    if response.status_code == 200:
        players_data = response.json()

        filename = "players.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(players_data, f, indent=2)

        print(f"\n✓ SUCCESS! Downloaded master data for {len(players_data)} players.")
        print(f"Saved as '{filename}'.")
        print("This file now has the latest prices, BEs, and ownership stats for the current round.")
    else:
        print(f"\n[!] Failed to fetch data. Server returned status code: {response.status_code}")

except Exception as e:
    print(f"\n[!] An error occurred: {e}")
