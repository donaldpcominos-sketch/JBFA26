import json
import csv
import math
import statistics

print("Starting the Ultimate YTD Enriched Process with Algorithmic BEs...")

# ============================================================
# 1. LOAD BE PARAMETERS & WEIGHTS
# ============================================================
try:
    with open("nrl_break_even_parameters_2026.json", "r", encoding="utf-8") as f:
        be_params = json.load(f)
        w0 = be_params["weights"]["score_current"]
        w1 = be_params["weights"]["score_previous1"]
        w2 = be_params["weights"]["score_previous2"]
        w_avg = be_params["weights"]["season_average"]
        base_mn = be_params["initial_magic_number"]
    print(f"Loaded BE Weights: Current({w0}), Prev1({w1}), Prev2({w2}), Avg({w_avg})")
except FileNotFoundError:
    print("Error: Could not find nrl_break_even_parameters_2026.json.")
    exit()

# ============================================================
# 2. LOAD DATA SOURCES & CALCULATE MARKET MEDIAN
# ============================================================
try:
    with open("YTD_Player_Stats.json", "r", encoding="utf-8") as f:
        player_stats_data = json.load(f)
except FileNotFoundError:
    print("Error: Could not find YTD_Player_Stats.json.")
    exit()

pricing_master = {}
implied_mn_list = []

try:
    with open("players.json", "r", encoding="utf-8") as f:
        players_raw = json.load(f)
        for p in players_raw:
            pid = str(p.get("id"))
            current_price = p.get("cost", 0)
            stats = p.get("stats", {})
            gp = stats.get("games_played", 0)
            avg = stats.get("avg_points", 0)
            c_avg = stats.get("career_avg", 0)
            
            pricing_master[pid] = {
                "current_price": current_price,
                "season_avg": avg,
                "career_avg": c_avg,
                "games_played": gp,
                "total_points": stats.get("total_points", 0),
                "last_3_avg": stats.get("last_3_avg", 0),
                "scores": stats.get("scores", {}),
                "prices": stats.get("prices", {})
            }
            
            # THE DYNAMIC CALIBRATOR: Use the Weighted Average to find the true MN
            if current_price > 400000 and gp >= 2:
                scores_dict = stats.get("scores", {})
                rounds = sorted([int(k) for k in scores_dict.keys()], reverse=True)
                s0 = scores_dict.get(str(rounds[0]), c_avg) if len(rounds) > 0 else c_avg
                s1 = scores_dict.get(str(rounds[1]), c_avg) if len(rounds) > 1 else c_avg
                s2 = scores_dict.get(str(rounds[2]), c_avg) if len(rounds) > 2 else c_avg
                
                current_wa = (w0 * s0) + (w1 * s1) + (w2 * s2) + (w_avg * avg)
                if current_wa > 0:
                    implied_mn_list.append(current_price / current_wa)

except FileNotFoundError:
    print("Error: Could not find players.json.")
    exit()

if implied_mn_list:
    DYNAMIC_MAGIC_NUMBER = round(statistics.median(implied_mn_list))
    print(f"Calculated True Market Magic Number: {DYNAMIC_MAGIC_NUMBER}")
else:
    DYNAMIC_MAGIC_NUMBER = base_mn
    print(f"Using default Magic Number: {DYNAMIC_MAGIC_NUMBER}")

scoring_matrix = {}
try:
    with open("Point Matrix.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            header = row.get("Header", "").strip()
            multiplier = row.get("Pt Multipler")
            if header and multiplier and multiplier.strip() != "":
                scoring_matrix[header] = float(multiplier)
except FileNotFoundError:
    print("Error: Could not find 'Point Matrix.csv'.")
    exit()

# ============================================================
# 3. FLATTEN, SCORE, AND PRICE (WITH ALGEBRAIC BE)
# ============================================================
csv_rows = []
all_stat_columns = set()
all_point_columns = set()

print("Processing stats and solving per‑round Break Evens...")

for player in player_stats_data:
    # Extract identifiers and meta from pricing_master
    pid = str(player.get("jbfa_player_id"))
    pname = player.get("jbfa_player_name")
    p_info = pricing_master.get(pid, {})
    current_price = p_info.get("current_price", 0)
    c_avg = p_info.get("career_avg", 0)
    last_3_avg = p_info.get("last_3_avg", 0)
    scores_dict = p_info.get("scores", {})
    prices_dict = p_info.get("prices", {})
    magic_value = round(current_price / last_3_avg) if last_3_avg > 0 else 0

    # Gather per‑round stats from player object
    stats_block = player.get("stats", {})
    stats_iterable = stats_block.items() if stats_block else [
        (k, v) for k, v in player.items() if isinstance(v, dict) and k in ["1", "2", "3", "all"]
    ]
    # sort by round number so history builds chronologically
    def sort_key(item):
        lbl = item[0]
        return int(lbl) if str(lbl).isdigit() else 999
    sorted_rounds = sorted(stats_iterable, key=sort_key)

    # Running totals for BE calculations
    prior_scores = []
    total_points = 0.0
    games_played = 0

    for round_label, round_stats in sorted_rounds:
        if not isinstance(round_stats, dict):
            continue
        # Determine start and end price for this round
        if str(round_label).isdigit():
            r_int = int(round_label)
            round_start_price = prices_dict.get(str(r_int), current_price)
            round_end_price = prices_dict.get(str(r_int + 1), current_price)
        elif round_label == "all":
            round_start_price = prices_dict.get("1", current_price)
            round_end_price = current_price
        else:
            round_start_price = 0
            round_end_price = 0

        # Base row
        row = {
            "Player ID": pid,
            "Player Name": pname,
            "Round": round_label,
            "Round Start Price": round_start_price,
            "Round End Price": round_end_price,
            "Current Price": current_price,
            "Magic Value": magic_value
        }

        # Compute fantasy points for this round
        total_fantasy_points = 0
        for stat_name, stat_value in round_stats.items():
            row[stat_name] = stat_value
            all_stat_columns.add(stat_name)
            if stat_name in scoring_matrix:
                multiplier = scoring_matrix[stat_name]
                if stat_name in ["MG", "KM"]:
                    calculated_points = math.floor(stat_value * multiplier)
                else:
                    calculated_points = stat_value * multiplier
                pt_col_name = f"{stat_name}_Pts"
                row[pt_col_name] = calculated_points
                all_point_columns.add(pt_col_name)
                total_fantasy_points += calculated_points
        row["Total_Calculated_Pts"] = total_fantasy_points

        # Compute break‑even for next round
        be_value = None
        if str(round_label).isdigit():
            # update running totals
            if total_fantasy_points > 0:
                prior_scores.insert(0, total_fantasy_points)
                total_points += total_fantasy_points
                games_played += 1
            s0 = prior_scores[0] if len(prior_scores) > 0 else c_avg
            s1 = prior_scores[1] if len(prior_scores) > 1 else c_avg
            next_price = round_end_price
            if next_price and DYNAMIC_MAGIC_NUMBER:
                target_wa = next_price / DYNAMIC_MAGIC_NUMBER
                weight_x = w0 + (w_avg / (games_played + 1))
                remainder = (w1 * s0) + (w2 * s1) + (w_avg * (total_points / (games_played + 1)))
                if weight_x != 0:
                    be_value = round((target_wa - remainder) / weight_x)
        row["Est. Break Even"] = be_value
        csv_rows.append(row)

# ============================================================
# 4. EXPORT TO CSV
# ============================================================
base_cols = ["Player ID", "Player Name", "Round", "Round Start Price", "Round End Price", "Current Price", "Magic Value", "Est. Break Even"]
stat_cols = sorted(list(all_stat_columns))
point_cols = sorted(list(all_point_columns))
final_cols = ["Total_Calculated_Pts"]

fieldnames = base_cols + stat_cols + point_cols + final_cols

with open("YTD_Player_Stats_Enriched.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(csv_rows)

print(f"✓ SUCCESS! Processed {len(csv_rows)} rows.")
print("Saved as YTD_Player_Stats_Enriched.csv. The Break Evens are now algorithmically calibrated!")