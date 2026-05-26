"""Extract a clean dataset of every player's price, score, and break-even
for each round from 3 to 11, from data.json's priceHistory arrays."""
import json
import csv
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "data.json"
OUT = ROOT / "player_price_score_be_r3_r11.csv"

START_ROUND = 3
END_ROUND = 11

with open(SRC, "r", encoding="utf-8") as f:
    data = json.load(f)

players = data.get("players", {})
rows = []
for pid, p in players.items():
    name = p.get("name", "")
    positions = p.get("positions", [])
    pos_str = "/".join(str(x) for x in positions) if positions else ""
    history = {entry.get("round"): entry for entry in p.get("priceHistory", []) or []}

    for rnd in range(START_ROUND, END_ROUND + 1):
        entry = history.get(rnd)
        if not entry:
            continue
        rows.append({
            "round": rnd,
            "player_id": pid,
            "name": name,
            "positions": pos_str,
            "price": entry.get("price"),
            "score": entry.get("score"),
            "break_even": entry.get("breakEven"),
        })

rows.sort(key=lambda r: (r["round"], r["name"]))

with open(OUT, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["round", "player_id", "name", "positions", "price", "score", "break_even"])
    writer.writeheader()
    writer.writerows(rows)

distinct_players = len({r["player_id"] for r in rows})
by_round = {}
for r in rows:
    by_round.setdefault(r["round"], 0)
    by_round[r["round"]] += 1

print(f"Wrote {len(rows):,} rows for {distinct_players:,} distinct players to {OUT.name}")
print("Rows per round:")
for rnd in sorted(by_round):
    print(f"  R{rnd}: {by_round[rnd]:,}")
