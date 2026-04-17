"""
fetch_fantasy_coach.py
======================
Fetches the Fantasy Coach bulk player stats endpoint and merges with
players.json to produce:

  fantasy_coach_stats.json  — full merged data per player
  formula_dataset.csv       — flat CSV for formula analysis

Run:  python fetch_fantasy_coach.py

NOTE: The session cookie expires. If you get a 401/403 or empty response,
grab a fresh cookie from DevTools and update COOKIE below.
"""

import json
import csv
import requests
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────

API_URL = "https://fantasy.nrl.com/data/nrl/coach/players.json"

COOKIE = (
    "__stripe_mid=ffb1ea04-f4d5-4dfb-9c06-644d0b3d9cc44914fa; optimizelyEndUserId=oeu1773051030358r0.3784378927237164; optimizelySession=0; session=42fe81e50f58476d91b1199712814d3f516e029f; __stripe_sid=2ec1e598-838a-4738-90df-3138c36ff0fbe7d03a"
)

CURRENT_ROUND = 3   # bump each week

# ── PATHS ─────────────────────────────────────────────────────────────────────

DIR          = Path(__file__).parent
PLAYERS_JSON = DIR / "players.json"
OUTPUT_JSON  = DIR / "fantasy_coach_stats.json"
OUTPUT_CSV   = DIR / "formula_dataset.csv"

# ── HEADERS ───────────────────────────────────────────────────────────────────

HEADERS = {
    "accept":          "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-GB,en;q=0.9,en-US;q=0.8,en-AU;q=0.7",
    "referer":         "https://fantasy.nrl.com/fantasy/team",
    "user-agent":      (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
    ),
    "sec-fetch-dest":  "empty",
    "sec-fetch-mode":  "cors",
    "sec-fetch-site":  "same-origin",
    "cookie":          COOKIE,
}

# ── LOAD PLAYERS.JSON ─────────────────────────────────────────────────────────

def load_players():
    with open(PLAYERS_JSON) as f:
        raw = json.load(f)

    players = {}
    for p in raw:
        pid   = str(p["id"])
        stats = p.get("stats", {})
        scores_raw = stats.get("scores", {})
        prices_raw = stats.get("prices", {})

        scores = {int(k): int(v) for k, v in scores_raw.items()}
        prices = {int(k): int(v) for k, v in prices_raw.items()}

        sorted_score_rounds = sorted(scores.keys())
        recent_scores = [scores[r] for r in reversed(sorted_score_rounds)]

        players[pid] = {
            "id":            p["id"],
            "name":          f"{p['first_name']} {p['last_name']}",
            "cost":          p["cost"],
            "games_played":  stats.get("games_played", 0),
            "scores":        scores,
            "prices":        prices,
            "recent_scores": recent_scores,
            "start_price":   prices.get(1, p["cost"]),
        }
    return players

# ── FETCH ─────────────────────────────────────────────────────────────────────

def fetch():
    print(f"GET {API_URL}")
    r = requests.get(API_URL, headers=HEADERS, timeout=30)
    print(f"  Status: {r.status_code}")

    # 304 = Not Modified (browser cache hit) — strip cache headers and retry
    if r.status_code == 304:
        print("  Got 304 Not Modified — retrying without cache headers...")
        h2 = {k: v for k, v in HEADERS.items()
              if k not in ("if-modified-since", "if-none-match")}
        r = requests.get(API_URL, headers=h2, timeout=30)
        print(f"  Status: {r.status_code}")

    r.raise_for_status()

    data = r.json()
    print(f"  Response type: {type(data).__name__}, keys: {len(data)}")

    if isinstance(data, dict):
        sample = list(data.keys())[:5]
        print(f"  Sample top-level keys: {sample}")

        # Keys are numeric strings → already keyed by player_id
        if all(k.isdigit() for k in sample):
            return {str(k): v for k, v in data.items()}

        # Look for a wrapping key containing the player dict
        for wrap_key in ("players", "data", "stats", "coach", "result"):
            if wrap_key in data and isinstance(data[wrap_key], dict):
                inner = data[wrap_key]
                inner_sample = list(inner.keys())[:3]
                if all(k.isdigit() for k in inner_sample):
                    print(f"  Unwrapping key '{wrap_key}'")
                    return {str(k): v for k, v in inner.items()}

        # Return as-is
        return {str(k): v for k, v in data.items()}

    elif isinstance(data, list):
        result = {}
        for item in data:
            pid = str(
                item.get("id") or
                item.get("player_id") or
                item.get("playerId", "")
            )
            if pid:
                result[pid] = item
        return result

    raise ValueError(f"Unexpected response type: {type(data)}")

# ── EXTRACT FIELDS ────────────────────────────────────────────────────────────

def extract(fc):
    return {
        "proj_prices":      fc.get("proj_prices", {}),
        "break_evens":      fc.get("break_evens", {}),
        "be_pct":           fc.get("be_pct", {}),
        "proj_scores":      fc.get("proj_scores", {}),
        "transfers":        fc.get("transfers", {}),
        "break_even":       fc.get("break_even"),
        "proj_score":       fc.get("proj_score"),
        "consistency":      fc.get("consistency"),
        "last_3_tog_avg":   fc.get("last_3_tog_avg"),
        "last_5_tog_avg":   fc.get("last_5_tog_avg"),
        "last_3_proj_avg":  fc.get("last_3_proj_avg"),
    }

# ── MERGE & SAVE ──────────────────────────────────────────────────────────────

def merge_and_save(players, fc_stats):
    merged  = {}
    matched = 0
    fc_only = 0

    for pid, fc in fc_stats.items():
        fields = extract(fc)
        if pid in players:
            merged[pid] = {**players[pid], **fields}
            matched += 1
        else:
            merged[pid] = {
                "id": pid, "name": f"Unknown_{pid}",
                "cost": None, "games_played": None,
                "scores": {}, "prices": {}, "recent_scores": [],
                "start_price": None,
                **fields,
            }
            fc_only += 1

    print(f"\n  Matched with players.json : {matched}")
    print(f"  FC-only (unknown player)  : {fc_only}")
    print(f"  players.json-only (no FC) : {len(players) - matched}")

    with open(OUTPUT_JSON, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"\nSaved: {OUTPUT_JSON}")

    write_csv(merged)
    return merged

# ── WRITE CSV ─────────────────────────────────────────────────────────────────

def _i(d, *keys):
    """Safe int lookup — tries both str and int keys."""
    for k in keys:
        v = (d or {}).get(str(k))
        if v is None:
            v = (d or {}).get(int(k) if isinstance(k, str) and k.isdigit() else k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                return v
    return None

def write_csv(merged):
    rows = []
    for pid, p in merged.items():
        pp = p.get("proj_prices", {})
        be = p.get("break_evens", {})
        bp = p.get("be_pct", {})
        ps = p.get("proj_scores", {})
        sc = p.get("scores", {})
        pr = p.get("prices", {})
        rs = p.get("recent_scores", [])

        p3 = _i(pp, 3);  p4 = _i(pp, 4);  p5 = _i(pp, 5);  p6 = _i(pp, 6)
        be3 = _i(be, 3); be4 = _i(be, 4); be5 = _i(be, 5)
        ps3 = _i(ps, 3); ps4 = _i(ps, 4); ps5 = _i(ps, 5)
        bp3 = _i(bp, 3); bp4 = _i(bp, 4); bp5 = _i(bp, 5)

        row = {
            "player_id":      pid,
            "name":           p.get("name", ""),
            "games_played":   p.get("games_played"),
            "start_price":    p.get("start_price"),
            "current_price":  p.get("cost"),

            # ── Exact unrounded prices (the crown jewel) ──────────────────
            # proj_prices[3] = true current price (app rounds to nearest $1k for display)
            # proj_prices[4] = price after scoring proj_scores[3]
            # proj_prices[5] = price after scoring proj_scores[4]
            # proj_prices[6] = price after scoring proj_scores[5]
            "exact_price_r3": p3,
            "proj_price_r4":  p4,
            "proj_price_r5":  p5,
            "proj_price_r6":  p6,

            # ── Break-evens ───────────────────────────────────────────────
            "be_r3": be3, "be_r4": be4, "be_r5": be5,

            # ── BE percentiles ────────────────────────────────────────────
            "be_pct_r3": bp3, "be_pct_r4": bp4, "be_pct_r5": bp5,

            # ── Platform projected scores ─────────────────────────────────
            "proj_score_r3": ps3, "proj_score_r4": ps4, "proj_score_r5": ps5,

            # ── Known scores (from players.json) ──────────────────────────
            "score_r1": sc.get(1),
            "score_r2": sc.get(2),

            # ── Known rounded prices (from players.json) ──────────────────
            "price_r1": pr.get(1),
            "price_r2": pr.get(2),
            "price_r3": pr.get(3),

            # ── Derived: exact price deltas ───────────────────────────────
            "delta_r3_to_r4": (p4 - p3) if (p4 and p3) else None,
            "delta_r4_to_r5": (p5 - p4) if (p5 and p4) else None,
            "delta_r5_to_r6": (p6 - p5) if (p6 and p5) else None,

            # ── vs BE (signed: + = beat BE, - = missed BE) ────────────────
            "score_vs_be_r3": (ps3 - be3) if (ps3 is not None and be3 is not None) else None,

            # ── Implied PPP = delta / vs_be ───────────────────────────────
            # If this is consistent across players, the formula is:
            #   delta = (score - BE) * PPP
            "implied_ppp_r3": (
                round((p4 - p3) / (ps3 - be3), 2)
                if (p4 and p3 and ps3 is not None and be3 is not None and (ps3 - be3) != 0)
                else None
            ),

            # ── Recent scores newest-first (for BE regression) ───────────
            "recent_s1": rs[0] if len(rs) > 0 else None,
            "recent_s2": rs[1] if len(rs) > 1 else None,
            "recent_s3": rs[2] if len(rs) > 2 else None,

            # ── Extra FC fields ───────────────────────────────────────────
            "consistency":    p.get("consistency"),
            "last_3_tog_avg": p.get("last_3_tog_avg"),
            "proj_score_fc":  p.get("proj_score"),
            "break_even_fc":  p.get("break_even"),
        }
        rows.append(row)

    rows.sort(key=lambda r: (
        -(r.get("games_played") or 0),
        -(r.get("current_price") or 0)
    ))

    if not rows:
        print("WARNING: No rows to write")
        return

    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    two_game = sum(1 for r in rows if r.get("games_played") == 2 and r.get("exact_price_r3"))
    with_ppp  = sum(1 for r in rows if r.get("implied_ppp_r3") is not None)
    print(f"Saved: {OUTPUT_CSV}")
    print(f"  {len(rows)} total players")
    print(f"  {two_game} with 2 games + exact prices  ← used for formula analysis")
    print(f"  {with_ppp} with computable implied PPP")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Fantasy Coach Stats Fetcher")
    print("=" * 60)

    print("\nLoading players.json...")
    players = load_players()
    gp = {g: sum(1 for p in players.values() if p["games_played"] == g) for g in [0,1,2]}
    print(f"  {len(players)} players  |  games: {gp}")

    print()
    fc_stats = fetch()

    if not fc_stats:
        print("\nERROR: Empty response.")
        print("The session cookie has likely expired.")
        print("Grab a fresh one from DevTools → Network → copy the Cookie header.")
        return

    # Sanity check on our known player
    if "505460" in fc_stats:
        fc = fc_stats["505460"]
        print(f"\n  Sanity check — 505460 (Reed Mahoney):")
        print(f"    proj_prices : {fc.get('proj_prices')}")
        print(f"    break_evens : {fc.get('break_evens')}")
        print(f"    be_pct      : {fc.get('be_pct')}")
        print(f"    proj_scores : {fc.get('proj_scores')}")
    else:
        # Show sample to diagnose key structure
        sample_key = list(fc_stats.keys())[0]
        sample_val = fc_stats[sample_key]
        print(f"\n  NOTE: 505460 not found. Sample key={sample_key}")
        print(f"  Sample fields: {list(sample_val.keys())[:12]}")

    print("\nMerging and saving...")
    merge_and_save(players, fc_stats)

    print("\n" + "=" * 60)
    print("DONE — send formula_dataset.csv back to Claude for analysis")
    print("=" * 60)


if __name__ == "__main__":
    main()
