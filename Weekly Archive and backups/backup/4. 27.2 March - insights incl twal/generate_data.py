import pandas as pd
import json
import os
from datetime import date

# ════════════════════════════════════════════════════════════════
#  UPDATE THESE TWO THINGS EACH WEEK
# ════════════════════════════════════════════════════════════════
CURRENT_ROUND = 3          # ← bump to 3 when R3 data is ready
ROUND_AVGS    = {1: 926, 2: 1034, 3: 835}   # ← add 3: XXXX when R3 is complete
# ════════════════════════════════════════════════════════════════

# ── STATIC CONFIG (never needs changing) ──────────────────────
TRADES_BASE     = 36
TRADES_GIFTED   = 8
TRADES_CAPACITY = TRADES_BASE + TRADES_GIFTED  # 44 total

TRADES_STATE_FILE = "trades_state.json"

DROP_SCHEDULE = [
    {"r":1,"d":0},{"r":2,"d":20},{"r":3,"d":20},{"r":4,"d":20},
    {"r":5,"d":20},{"r":6,"d":20},{"r":7,"d":18},{"r":8,"d":16},
    {"r":9,"d":16},{"r":10,"d":16},{"r":11,"d":16},{"r":12,"d":15},
    {"r":13,"d":15},{"r":14,"d":13},{"r":15,"d":11},{"r":16,"d":10},
    {"r":17,"d":10},{"r":18,"d":8},{"r":19,"d":7},{"r":20,"d":6},
    {"r":21,"d":5},{"r":22,"d":4},{"r":23,"d":4},{"r":24,"d":3},
    {"r":25,"d":2},{"r":26,"d":2},{"r":27,"d":1},
]

SPECIAL_TAGS = {
    "Don Cominos":      {"label": "Commissioner", "icon": "⚙️"},
    "Andrew Phillipps": {"label": "2025 Winner", "icon": "✦", "badgeClass": "bchamp"},
    "Jake Venn":        {"label": "2025 Runner-Up", "icon": "✦", "badgeClass": "bru"},
    "Sam C":            {"label": "Top 10 · 2025", "icon": None, "badgeClass": "btop10"},
    "Tyson Coles":      {"label": "Top 10 · 2025", "icon": None, "badgeClass": "btop10"},
    "Jamie Brown":      {"label": "JBFA Podcaster", "icon": "🎙️", "isAdmin": True},
    "Mitch Deguara":    {"label": "JBFA Podcaster", "icon": "🎙️"},
    "Nikki Mcintosh":   {"label": "JBFA Podcaster", "icon": "🎙️"},
    "Matt Thompson":    {"label": "JBFA Podcaster", "icon": "🎙️"},
    "Chris Cook":       {"label": "STAMP YA FEET", "icon": "🐇"},
}


# ════════════════════════════════════════════════════════════════
#  BREAK-EVEN & PRICE MODEL  —  Validated 5-Game Rolling Window
#
#  Empirically confirmed against NRL Fantasy Coach API data across
#  28 players × 3 rounds using Score_50 and Additional datasets.
#
#  ── CORE FORMULA ─────────────────────────────────────────────
#
#  NRL Fantasy uses a 5-game rolling window with K = 13,000.
#
#  BE for the UPCOMING round:
#    W = min(games_played + 1, 5)          # window size for next game
#    BE = round(W × price / K) − sum(last (W−1) known scores)
#
#  Examples:
#    0 games played:  BE = round(1 × price / 13000)
#    1 game played:   BE = round(2 × price / 13000) − s1
#    2 games played:  BE = round(3 × price / 13000) − s1 − s2
#    3 games played:  BE = round(4 × price / 13000) − s1 − s2 − s3
#    4 games played:  BE = round(5 × price / 13000) − s1 − s2 − s3 − s4
#    5+ games played: BE = round(5 × price / 13000) − s2 − s3 − s4 − s5
#                         (window slides — oldest score drops out)
#
#  IMPORTANT: The current-round BE is taken DIRECTLY from the FC API
#  (break_evens[CURRENT_ROUND + 1]) — this is exact and authoritative.
#  CURRENT_ROUND = rounds completed. The FC API always publishes BEs
#  keyed by the UPCOMING round (CURRENT_ROUND + 1). No formula needed.
#  The formula above is used only for chaining FUTURE round projections.
#
#  ── PRICE CHANGE FORMULA ─────────────────────────────────────
#  delta      = PPP × (score − BE)
#  next_price = round((current_price + delta) / 1000) × 1000
#
#  PPP = 1,000  (dollars per point above/below BE)
#
#  ── ACCURACY (validated) ─────────────────────────────────────
#  Round N+1 (1 ahead):  ≤$3k error for ~85% of players
#  Round N+2 (2 ahead):  ~$5k average error
#  Round N+3 (3 ahead):  ~$10k average error (compounding)
#
#  ── KEY DESIGN PRINCIPLE ─────────────────────────────────────
#  The current BE is ALWAYS sourced from the API (break_evens[ROUND]).
#  This means each week when formula_dataset.csv is regenerated with
#  the new round's data, the BE automatically reflects the correct
#  current round — no manual updates required.
# ════════════════════════════════════════════════════════════════

K_MAGIC: float = 13000.0   # NRL Fantasy rolling window constant
PPP:     float = 1000.0    # Price change per point above/below BE ($)


def compute_break_even(current_price: float, games_played: int,
                       recent_scores: list[float]) -> int | None:
    """
    Compute the next-round break-even using the 5-game rolling window formula.

    NOTE: For the *current* round, always prefer the API-sourced BE from
    break_evens[CURRENT_ROUND] in fantasy_coach_stats.json — it is exact.
    This function is used for chaining future-round projections only.

    Parameters
    ----------
    current_price : float
        Player's current display price (rounded to $1k).
    games_played : int
        Total NRL Fantasy games played so far this season.
    recent_scores : list[float]
        Scores oldest-first: [s1, s2, s3, ...] (chronological order).
        Only the last (W-1) scores are used, where W = min(gp+1, 5).

    Returns
    -------
    int | None
        Rounded break-even score.
    """
    if games_played < 0:
        return None
    W = min(games_played + 1, 5)
    n_prev = W - 1  # number of previous scores to subtract
    prev_sum = sum(recent_scores[-n_prev:]) if n_prev > 0 and recent_scores else 0
    return round(W * current_price / K_MAGIC) - int(prev_sum)


def compute_price_next(current_price: float, score: float,
                       be: int) -> int:
    """
    Project the next display price given a score and break-even.

    Parameters
    ----------
    current_price : float
        Player's current price (display, rounded to $1k).
    score : float
        The projected score for this round.
    be : int
        The break-even for this round (from API or compute_break_even).

    Returns
    -------
    int
        Projected next-round display price (rounded to nearest $1,000).
    """
    delta = PPP * (score - be)
    return round((current_price + delta) / 1000) * 1000


# ════════════════════════════════════════════════════════════════
#  LOAD FANTASY COACH STATS
#
#  fantasy_coach_stats.json (produced by fetch_fantasy_coach.py)
#  provides per-player:
#    - break_evens[CURRENT_ROUND + 1]  ← BE for the UPCOMING round
#    - proj_prices[CURRENT_ROUND + 1]  ← exact internal price entering next round
#
#  KEY: CURRENT_ROUND = rounds of scores COMPLETED.
#  The FC API always publishes BEs and prices looking FORWARD.
#  So when CURRENT_ROUND=2 (2 rounds done), the upcoming round
#  is 3, and the API has break_evens['3'] and proj_prices['3'].
#
#  The BE for the upcoming round comes DIRECTLY from the API.
#  No formula needed — it's already there.
# ════════════════════════════════════════════════════════════════

BE_ROUND = CURRENT_ROUND + 1   # The round we're predicting BE for

fc_stats_data: dict = {}   # pid → full FC stats dict
fc_exact_prices: dict = {} # pid → exact_price (float)

FC_STATS_FILE = "fantasy_coach_stats.json"
if os.path.exists(FC_STATS_FILE):
    with open(FC_STATS_FILE) as f:
        fc_data = json.load(f)
    for pid, fc in fc_data.items():
        fc_stats_data[pid] = fc
        pp = fc.get("proj_prices", {})
        # proj_prices[BE_ROUND] = exact internal price entering the upcoming round
        exact = pp.get(str(BE_ROUND)) or pp.get(BE_ROUND)
        if exact:
            fc_exact_prices[pid] = float(exact)
    print(f"Loaded {len(fc_stats_data)} FC stats from {FC_STATS_FILE} "
          f"({len(fc_exact_prices)} with exact prices for R{BE_ROUND})")
else:
    print(f"NOTE: {FC_STATS_FILE} not found — BE will be estimated from formula")
    print("      Run fetch_fantasy_coach.py to get API break-evens.")


# ════════════════════════════════════════════════════════════════
#  LOAD PLAYER STATS — per-round raw stat breakdowns
#
#  Primary source: all_player_stats_r{N}.json files
#    Produced by fetch_player_stats.py (one file per round).
#    Each file is a list of player stat objects:
#      - jbfa_player_id: int
#      - jbfa_player_name: str
#      - "<round>": { TCK, TB, MT, OFH, OFG, ER, MG, KM, G, T, TA, LB, LBA,
#                     FDO, TOG, FG, FTF, KD, PC, SB, SO, TS, TO, SAI, EFIG }
#      - "all": aggregate totals (not used for per-round historicalStats)
#
#  Fallback: YTD_Player_Stats.json (legacy merged snapshot)
#
#  All Point_Matrix stat fields plus TOG (minutes) are exported.
# ════════════════════════════════════════════════════════════════

STAT_FIELDS = [
    "T", "TS", "G", "FG", "TA", "LB", "LBA",
    "TCK", "TB", "MT", "OFH", "OFG", "ER", "FTF",
    "MG", "KM", "KD", "PC", "SB", "SO", "TOG",
    "FDO", "TO", "SAI", "EFIG",
]

ytd_stats_by_pid = {}   # pid_str → { "1": {stat: val, ...}, "2": {...}, ... }


def _load_stats_file(filepath, target_dict):
    """Load an all_player_stats_rN.json or YTD_Player_Stats.json into target_dict.
    Per-round keys (digit strings) are merged in; existing rounds are not overwritten."""
    with open(filepath) as f:
        raw = json.load(f)
    loaded = 0
    for entry in raw:
        pid = str(entry.get("jbfa_player_id", ""))
        if not pid:
            continue
        if pid not in target_dict:
            target_dict[pid] = {}
        for key, val in entry.items():
            if key in ("jbfa_player_id", "jbfa_player_name", "all"):
                continue
            if key.isdigit() and isinstance(val, dict):
                # Only add this round if not already present (earlier file takes precedence)
                if key not in target_dict[pid]:
                    target_dict[pid][key] = {f: val.get(f, 0) for f in STAT_FIELDS}
        loaded += 1
    return loaded


# --- Primary: scan for all_player_stats_r*.json files (one per round) ---
import glob as _glob
rn_files = sorted(_glob.glob("all_player_stats_r*.json"))
if rn_files:
    total_loaded = 0
    for fp in rn_files:
        n = _load_stats_file(fp, ytd_stats_by_pid)
        total_loaded += n
        print(f"Loaded per-round stats from {fp} ({n} players)")
    print(f"historicalStats populated for {len(ytd_stats_by_pid)} players across {len(rn_files)} round file(s)")
else:
    # --- Fallback: legacy YTD_Player_Stats.json ---
    YTD_STATS_FILE = "YTD_Player_Stats.json"
    if os.path.exists(YTD_STATS_FILE):
        n = _load_stats_file(YTD_STATS_FILE, ytd_stats_by_pid)
        print(f"Loaded YTD stats for {n} players from {YTD_STATS_FILE} (fallback)")
    else:
        print("NOTE: No all_player_stats_r*.json files and no YTD_Player_Stats.json found — historicalStats will be empty")


# ════════════════════════════════════════════════════════════════
#  LOAD PLAYERS.JSON — source of prices & scores per round
# ════════════════════════════════════════════════════════════════

player_be_data = {}   # pid → {breakEven, priceHistory, scores, startPrice, ...}
positions_map  = {}   # pid → [list of position ints]

if os.path.exists("players.json"):
    with open("players.json") as f:
        raw_players = json.load(f)

    for p in raw_players:
        positions_map[str(p["id"])] = p.get("positions", [])

    for p in raw_players:
        pid = str(p["id"])
        stats = p.get("stats", {})
        prices_by_round = stats.get("prices", {})   # {"1": 950000, "2": 931000, ...}
        scores_by_round = stats.get("scores", {})   # {"1": 56, "2": 75}

        # Season-start price = Round 1 price
        start_price = prices_by_round.get("1") or p.get("cost", 0)
        if not start_price:
            continue

        games_played  = stats.get("games_played", 0)
        display_price = float(p.get("cost", start_price))

        # Build chronological score list for the rolling window
        sorted_rounds  = sorted(scores_by_round.keys(), key=int)
        ordered_scores = [float(scores_by_round[r]) for r in sorted_rounds]  # oldest first

        # ── Current BE: sourced directly from FC API (authoritative) ──────
        # The FC API publishes break_evens keyed by the UPCOMING round number.
        # When CURRENT_ROUND=2, the upcoming round is 3, so we look up ['3'].
        # This is BE_ROUND = CURRENT_ROUND + 1, set above.
        # Falls back to rolling-window formula if FC stats unavailable.
        fc = fc_stats_data.get(pid, {})
        fc_bes = fc.get("break_evens", {})
        api_be = fc_bes.get(str(BE_ROUND)) or fc_bes.get(BE_ROUND)

        if api_be is not None:
            be = int(api_be)
        else:
            # Fallback: compute from rolling window formula
            be = compute_break_even(display_price, games_played, ordered_scores)

        # ── Price history with per-round BEs ──────────────────────────────
        price_history: list[dict] = []
        cumulative_scores: list[float] = []

        for r in sorted(prices_by_round.keys(), key=int):
            r_int       = int(r)
            score       = scores_by_round.get(r)
            round_price = float(prices_by_round[r])

            # Historical BE: use API if available, else rolling-window formula
            hist_api_be = fc_bes.get(str(r_int)) or fc_bes.get(r_int)
            if hist_api_be is not None:
                hist_be = int(hist_api_be)
            elif cumulative_scores:
                hist_be = compute_break_even(round_price, len(cumulative_scores),
                                             cumulative_scores)
            else:
                hist_be = None

            price_history.append({
                "round":     r_int,
                "price":     int(round_price),
                "score":     int(score) if score is not None else None,
                "breakEven": hist_be,
            })

            if score is not None:
                cumulative_scores.append(float(score))

        player_be_data[pid] = {
            "breakEven":    be,           # current-round BE (API-sourced where possible)
            "startPrice":   int(start_price),
            "priceHistory": price_history,
            "scores":       {k: int(v) for k, v in scores_by_round.items()},
            "currentPrice": int(display_price),
            "gamesPlayed":  games_played,
            # Chronological scores oldest-first — JS uses these for the rolling window chain
            "orderedScores": [int(s) for s in ordered_scores],
        }

    print(f"Loaded BE data for {len(player_be_data)} players "
          f"(API BE for {sum(1 for p in player_be_data.values() if p['breakEven'] is not None)} players)")
else:
    print("WARNING: players.json not found — break-even data will be empty")


# ── LOAD MASTER + SCRAPES ─────────────────────────────────────
master = pd.read_excel("MASTER.xlsx")
master.columns = [c.strip() for c in master.columns]
master_ids = set(master["Team ID"].astype(int).tolist())

scrapes_full  = {}
scrapes_dedup = {}
for r in range(1, CURRENT_ROUND + 1):
    df = pd.read_csv(f"JBFA_R{r}_Master_Scrape.csv")
    scrapes_full[r]  = df[df["team_id"].isin(master_ids)]
    scrapes_dedup[r] = scrapes_full[r].drop_duplicates("team_id", keep="first")

# R1 platform rank fix
# R1 platform rank fix
# The round-2 scrape contains the previous-round rank for round 1.
# Guard this so the script does not break if round 2 data is not present yet.
r2_prev_rank = {}
if 2 in scrapes_dedup and "prev_round_rank" in scrapes_dedup[2].columns:
    r2_prev_rank = scrapes_dedup[2].set_index("team_id")["prev_round_rank"].to_dict()


# ── CUMULATIVE TRADES STATE ───────────────────────────────────
if os.path.exists(TRADES_STATE_FILE):
    with open(TRADES_STATE_FILE) as f:
        trades_state = json.load(f)
    print(f"Loaded trades state — last recorded round: R{trades_state['lastRound']}")
else:
    trades_state = {"lastRound": 0, "byTeam": {}}
    print("No trades state file found — starting fresh from R1")

already_counted_up_to = trades_state["lastRound"]
rounds_to_process = range(max(2, already_counted_up_to + 1), CURRENT_ROUND + 1)

for r in rounds_to_process:
    if r - 1 not in scrapes_full or r not in scrapes_full:
        print(f"  WARNING: Missing scrape data for R{r-1} or R{r} — skipping trade count for R{r}")
        continue

    sets_prev = scrapes_full[r - 1].groupby("team_id")["player_id"].apply(set).to_dict()
    sets_curr = scrapes_full[r].groupby("team_id")["player_id"].apply(set).to_dict()
    rkey = f"r{r}"
    trades_this_round = 0

    for tid in master_ids:
        if tid not in sets_prev or tid not in sets_curr:
            continue
        dropped = len(sets_prev[tid] - sets_curr[tid])
        if dropped > 0:
            tid_str = str(tid)
            if tid_str not in trades_state["byTeam"]:
                trades_state["byTeam"][tid_str] = {}
            trades_state["byTeam"][tid_str][rkey] = dropped
            trades_this_round += dropped

    print(f"  R{r}: {trades_this_round} total player drops across all teams")

trades_state["lastRound"] = CURRENT_ROUND

with open(TRADES_STATE_FILE, "w") as f:
    json.dump(trades_state, f, indent=2)
print(f"trades_state.json updated through R{CURRENT_ROUND}")

team_trades_used = {}
for tid_str, rounds in trades_state["byTeam"].items():
    team_trades_used[int(tid_str)] = sum(rounds.values())


# ── BUILD COACH RECORDS ───────────────────────────────────────
coaches = []
for _, row in master.iterrows():
    tid        = int(row["Team ID"])
    coach_name = str(row["Coach Name"]).strip()
    is_vip     = str(row.get("VIP Tag",      "")).strip().upper() == "VIP"
    is_admin   = str(row.get("Admin Tag",    "")).strip().upper() == "ADMIN"
    is_pod     = str(row.get("Podcaster Tag","")).strip().upper() == "PODCASTER"
    vip_entry  = str(row.get("VIP Team Entry","")).strip().upper() == "VIP ENTRY"
    surv_elig  = str(row.get("Survivor Eligible", "NO")).strip().upper() == "YES"
    scores, wealth, platform_ranks = {}, {}, {}
    team_name  = str(row.get("League Team", coach_name)).strip()

    for r_num, df in scrapes_dedup.items():
        match = df[df["team_id"].astype(int) == tid]
        if len(match) == 0:
            continue
        m = match.iloc[0]
        scores[f"r{r_num}"]         = int(m["round_score"])
        platform_ranks[f"r{r_num}"] = int(m["rank"])
        if r_num >= 2:
            wealth[f"r{r_num}"] = int(m["total_wealth"])
        team_name = str(m["team_name"]).strip()

    if tid in r2_prev_rank and int(r2_prev_rank[tid]) > 0:
        platform_ranks["r1"] = int(r2_prev_rank[tid])

    used = team_trades_used.get(tid, 0)

    coaches.append({
        "teamId":           tid,
        "coach":            coach_name,
        "team":             team_name,
        "isVip":            is_vip or is_admin,
        "isAdmin":          is_admin,
        "isPodcaster":      is_pod,
        "vipEntry":         vip_entry,
        "survivorEligible": surv_elig,
        "scores":           scores,
        "total":            sum(scores.values()),
        "wealth":           wealth,
        "platformRanks":    platform_ranks,
        "survivorStatus":   "alive" if surv_elig else "ineligible",
        "eliminatedRound":  None,
        "vipRank":          None,
        "rank":             0,
        "rankHistory":      {},
        "cashInBank":       0,
        "wealthPct":        50,
        "players":          [],
        "tradesUsed":       used,
        "tradesRemaining":  TRADES_BASE - used,
        "tradesCapacity":   TRADES_CAPACITY,
    })


# ── RANKINGS ─────────────────────────────────────────────────
coaches.sort(key=lambda c: c["total"], reverse=True)
for i, c in enumerate(coaches):
    c["rank"] = i + 1

for r in range(1, CURRENT_ROUND + 1):
    sorted_r = sorted(
        coaches,
        key=lambda c: sum(c["scores"].get(f"r{x}", 0) for x in range(1, r + 1)),
        reverse=True,
    )
    for i, c in enumerate(sorted_r):
        c["rankHistory"][f"r{r}"] = i + 1

vip_entries = sorted(
    [c for c in coaches if c["vipEntry"]],
    key=lambda c: c["total"], reverse=True,
)
for i, c in enumerate(vip_entries):
    c["vipRank"] = i + 1


# ── SURVIVOR ─────────────────────────────────────────────────
eliminated_by_round = {}
alive_set = set(c["teamId"] for c in coaches if c["survivorEligible"])

for drop in DROP_SCHEDULE:
    r, d = drop["r"], drop["d"]
    if d == 0 or r > CURRENT_ROUND:
        continue
    rkey      = f"r{r}"
    prev_rkey = f"r{r-1}"
    still_alive = [c for c in coaches if c["teamId"] in alive_set]
    still_alive.sort(key=lambda c: (c["scores"].get(rkey, 0), c["scores"].get(prev_rkey, 0)))
    cut = still_alive[:d]
    eliminated_by_round[str(r)] = [
        {"coach": c["coach"], "team": c["team"], "score": c["scores"].get(rkey, 0)}
        for c in cut
    ]
    for c in cut:
        c["survivorStatus"]  = "eliminated"
        c["eliminatedRound"] = r
        alive_set.discard(c["teamId"])


# ── PLAYER DATA ───────────────────────────────────────────────
cur_full  = scrapes_full[CURRENT_ROUND]
prev_full = scrapes_full.get(CURRENT_ROUND - 1)
total_teams = len(master_ids)

ownership_cur = cur_full.groupby("player_id")["team_id"].count()
ownership_pct = (ownership_cur / total_teams * 100).round(1)

curr_sets = cur_full.groupby("team_id")["player_id"].apply(set).to_dict()

if prev_full is not None:
    ownership_prev = prev_full.groupby("player_id")["team_id"].count()
    prev_sets = prev_full.groupby("team_id")["player_id"].apply(set).to_dict()
else:
    # round 1 / season reset safe defaults
    ownership_prev = pd.Series(dtype=int)
    prev_sets = {}
curr_sets = cur_full.groupby("team_id")["player_id"].apply(set).to_dict()
traded_in_count, traded_out_count = {}, {}
for tid in master_ids:
    if tid not in prev_sets or tid not in curr_sets:
        continue
    for p in curr_sets[tid] - prev_sets[tid]:
        traded_in_count[p]  = traded_in_count.get(p, 0)  + 1
    for p in prev_sets[tid] - curr_sets[tid]:
        traded_out_count[p] = traded_out_count.get(p, 0) + 1

pname_map = {}
for r in range(1, CURRENT_ROUND + 1):
    for _, row in (
        scrapes_full[r][["player_id", "player_name", "player_cost"]]
        .drop_duplicates("player_id").iterrows()
    ):
        pname_map[int(row["player_id"])] = {
            "name": str(row["player_name"]),
            "cost": int(row["player_cost"]),
        }

# ── PLAYER UNIVERSE ───────────────────────────────────────────
# Scrape-seen IDs (numeric) — ownership/trade maps are keyed by these
scrape_pids_int = set()
for r in range(1, CURRENT_ROUND + 1):
    scrape_pids_int |= set(int(p) for p in scrapes_full[r]["player_id"].unique())

# Full universe (string-keyed for output) — union of all sources
all_pids_str = set(str(p) for p in scrape_pids_int)
if os.path.exists("players.json"):
    all_pids_str |= set(str(p["id"]) for p in raw_players)
all_pids_str |= set(fc_stats_data.keys())
all_pids_str |= set(ytd_stats_by_pid.keys())

players_global = {}
for pid_str in all_pids_str:
    # ── Inclusion gate: must be owned OR have played at least 1 game ──────
    _be = player_be_data.get(pid_str, {})
    _games_played = _be.get("gamesPlayed", 0)
    _is_owned = int(pid_str) in scrape_pids_int and int(ownership_cur.get(int(pid_str), 0)) > 0
    if not _is_owned and _games_played < 1:
        continue
    
    pid_int = int(pid_str)

    # ── Scrape-derived fields: always use pid_int (maps are numeric-keyed) ──
    in_scrapes   = pid_int in scrape_pids_int
    ti           = traded_in_count.get(pid_int, 0)
    to_          = traded_out_count.get(pid_int, 0)
    prev_own     = int(ownership_prev.get(pid_int, 0))
    cur_own      = int(ownership_cur.get(pid_int, 0))

    if in_scrapes:
        elig_in      = total_teams - prev_own
        elig_out     = prev_own
        elig_in_pct  = round(ti  / elig_in  * 100, 1) if elig_in  > 0 and ti  > 0 else 0.0
        elig_out_pct = round(to_ / elig_out * 100, 1) if elig_out > 0 and to_ > 0 else 0.0
    else:
        # Player not seen in any scrape — zero out all ownership fields
        ti, to_, prev_own, cur_own = 0, 0, 0, 0
        elig_in_pct, elig_out_pct  = 0.0, 0.0

    # ── Name/cost: prefer scrape data, fall back to players.json ──
    info = pname_map.get(pid_int)
    if info is None:
        be_fallback = player_be_data.get(pid_str, {})
        raw_name = next(
            (
                (str(p.get("first_name", "")) + " " + str(p.get("last_name", ""))).strip()
                for p in raw_players
                if str(p["id"]) == pid_str
            ),
            pid_str,
        )
        info = {"name": raw_name or pid_str, "cost": be_fallback.get("currentPrice", 0)}
    # Merge break-even data from players.json
    be_info = player_be_data.get(pid_str, {})

    players_global[pid_str] = {
        "name":         info["name"],
        "cost":         info["cost"],
        "owned":        cur_own,
        "ownedPct":     float(ownership_pct.get(pid_int, 0.0)),
        "tradedIn":     ti,
        "tradedOut":    to_,
        "tradedInPct":  round(ti  / total_teams * 100, 1) if ti  > 0 else 0.0,
        "tradedOutPct": round(to_ / total_teams * 100, 1) if to_ > 0 else 0.0,
        "eligInPct":    elig_in_pct,
        "eligOutPct":   elig_out_pct,
        # Break-even & price predictor fields
        "breakEven":     be_info.get("breakEven"),       # API-sourced current-round BE
        "startPrice":    be_info.get("startPrice"),
        "currentPrice":  be_info.get("currentPrice"),
        "gamesPlayed":   be_info.get("gamesPlayed", 0),
        "scores":        be_info.get("scores", {}),
        "priceHistory":  be_info.get("priceHistory", []),
        # Chronological scores oldest-first — used by JS 5-game rolling window
        "orderedScores": be_info.get("orderedScores", []),
        # Per-round raw stat breakdowns from YTD_Player_Stats.json
        "historicalStats": ytd_stats_by_pid.get(pid_str, {}),
        # Player positions from players.json (NRL Fantasy position IDs)
        "positions": positions_map.get(pid_str, []),
    }

def _trade_item(pid, cnt, is_in):
    pid_int   = int(pid)
    info      = pname_map.get(pid_int, {"name": "?", "cost": 0})
    prev_own  = int(ownership_prev.get(pid, 0))
    total_pct = round(cnt / total_teams * 100, 1)
    elig      = (total_teams - prev_own) if is_in else prev_own
    elig_pct  = round(cnt / elig * 100, 1) if elig > 0 else 0.0
    return {"id": str(pid_int), "name": info["name"], "count": cnt,
            "totalPct": total_pct, "eligPct": elig_pct}

trade_summary = {
    "in":  [_trade_item(p, c, True)  for p, c in sorted(traded_in_count.items(),  key=lambda x: -x[1])[:8]],
    "out": [_trade_item(p, c, False) for p, c in sorted(traded_out_count.items(), key=lambda x: -x[1])[:8]],
}

all_wealths  = sorted([int(w) for w in cur_full.drop_duplicates("team_id")["total_wealth"]])
coach_by_tid = {c["teamId"]: c for c in coaches}

for tid in master_ids:
    team_rows = cur_full[cur_full["team_id"] == tid].reset_index(drop=True)
    if len(team_rows) == 0:
        continue
    plist = [str(int(row["player_id"])) for _, row in team_rows.iterrows()]
    cash  = int(team_rows.iloc[-1]["cash_in_bank"])
    tw    = int(team_rows.iloc[0]["total_wealth"])
    pct   = round(sum(1 for w in all_wealths if w <= tw) / len(all_wealths) * 100)
    if tid in coach_by_tid:
        coach_by_tid[tid]["players"]    = plist
        coach_by_tid[tid]["cashInBank"] = cash
        coach_by_tid[tid]["wealthPct"]  = pct


# ── BREAK-EVEN SUMMARY STATS (for meta) ──────────────────────
be_values = [v["breakEven"] for v in players_global.values() if v["breakEven"] is not None]
be_summary = {
    "playersWithBE":  len(be_values),
    "avgBE":          round(sum(be_values) / len(be_values), 1) if be_values else None,
}

# ── ASSEMBLE OUTPUT ───────────────────────────────────────────
alive_count   = len(alive_set)
elig_count    = sum(1 for c in coaches if c["survivorEligible"])
inelig_count  = len(coaches) - elig_count
cut_score     = max(
    (e["score"] for e in eliminated_by_round.get(str(CURRENT_ROUND), [])),
    default=0,
)
cur_rkey  = f"r{CURRENT_ROUND}"
top_coach = max(coaches, key=lambda c: c["scores"].get(cur_rkey, 0))

output = {
    "meta": {
        "currentRound":          CURRENT_ROUND,
        "roundAvg":              ROUND_AVGS[CURRENT_ROUND],
        "roundAvgs":             ROUND_AVGS,
        "totalCoaches":          len(coaches),
        "survivorEligibleCount": elig_count,
        "survivorIneligCount":   inelig_count,
        "aliveAfterLastRound":   alive_count,
        "cutScore":              cut_score,
        "topScoreThisRound":     top_coach["scores"].get(cur_rkey, 0),
        "topCoachThisRound":     top_coach["coach"],
        "lastUpdated":           str(date.today()),
        "tradeSummary":          trade_summary,
        "tradesBase":            TRADES_BASE,
        "tradesCapacity":        TRADES_CAPACITY,
        "breakEvenSummary":      be_summary,
    },
    "dropSchedule":      DROP_SCHEDULE,
    "coaches":           coaches,
    "eliminatedByRound": eliminated_by_round,
    "specialTags":       SPECIAL_TAGS,
    "players":           players_global,
    # Expose the validated BE model constants for the JS price predictor.
    # The JS uses these for chaining future-round projections.
    # The current-round BE is always sourced from the API (player.breakEven).
    "beModel": {
        "kMagic":    K_MAGIC,   # 13000 — rolling window constant
        "ppp":       PPP,       # 1000  — dollars per point above/below BE
        "window":    5,         # 5-game rolling window
        "currentRound": CURRENT_ROUND,
    },
}

compact = json.dumps(output, separators=(",", ":"))
with open("data.json", "w") as f:
    f.write(compact)

print(
    f"R{CURRENT_ROUND} | {len(coaches)} coaches | {alive_count} alive | "
    f"cut: {cut_score} | top: {top_coach['scores'].get(cur_rkey, 0)} ({top_coach['coach']})"
)
print(f"Players: {len(players_global)} | BEs calculated: {len(be_values)} | "
      f"JSON: {len(compact):,} chars ({len(compact)//1024} KB)")
