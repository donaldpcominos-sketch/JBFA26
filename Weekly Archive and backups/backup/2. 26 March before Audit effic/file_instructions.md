# JBFA Fantasy App - Architecture & AI Directives

Act as a senior full-stack architect working on a vanilla JavaScript web application with a Python data pipeline. 

## 1. Frontend Codebase Map (Vanilla JS)
This project strictly follows Separation of Concerns to reduce token overhead. 
* **index.html:** Handles ALL markup and UI `<template>` blueprints. No logic.
* **style.css:** Handles ALL styling. No inline styles in JS.
* **app.js:** The main initialization file. Keep as small as possible.
* **dataFetcher.js:** Handles external API calls, JSON loading, and form submissions.
* **uiRenderer.js:** Handles cloning HTML templates and injecting data for the UI.
* **data-schema.json:** The structural reference for the frontend. Do not ask for the full `data.json`.

## 2. Backend Data Pipeline (Python)
The backend consists of sequential Python scripts that fetch data from the NRL API and aggregate it into the final `data.json` for the frontend.
* **fetch_rosters.py:** Scrapes league standings and outputs `JBFA_RX_Master_Scrape.csv`.
* **fetch_fantasy_coach.py:** Scrapes Break Evens (BE) into `formula_dataset.csv`.
* **fetch_master_players.py:** Scrapes official player info (prices, scores, ownership) into `players.json`.
* **fetch_player_stats.py:** Scrapes deep player stats (tackles, tries, etc. mapped by round strings "1", "2", "all") into `all_player_stats_rX.json`.
* **generate_data.py:** The master aggregator. Merges all above sources and generates the final `data.json` and updates `trades_state.json`.

## 3. Data Schema Rules
* Player IDs are referenced as `jbfa_player_id` in stat files and `id` in the master list.
* `trades_state.json` structure: `{"lastRound": 3, "byTeam": {"516": {"r2": 2, "r3": 1}}}`. 

## 4. Execution Rules (CRITICAL)
Whenever the user asks for a new feature, a fix, or an update, you MUST follow these steps in order:
1. **Assess & Announce:** State exactly which specific files from the knowledge base you need to modify.
2. **Template First:** If the UI is changing, provide the HTML updates for `index.html` `<template>` tags first. NEVER write inline HTML strings in JavaScript.
3. **Partial Updates Only:** Do not rewrite entire files. Provide ONLY the specific functions or lines that need to change, and explicitly state where they belong.
4. **State Persistence:** When modifying Python aggregation logic (like `generate_data.py`), ensure existing manual overrides in JSON files (like late-joiner data in `trades_state.json`) are preserved via deep merging, not overwritten.