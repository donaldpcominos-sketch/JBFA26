"""
update_inline_data.py
Run this after generate_data.py to sync _INLINE_DATA in index.html with data.json.

Usage:
    python update_inline_data.py
"""

import json
import re
import os

DATA_FILE = "data.json"
HTML_FILE = "index.html"

def main():
    if not os.path.exists(DATA_FILE):
        print(f"ERROR: {DATA_FILE} not found. Run generate_data.py first.")
        return

    if not os.path.exists(HTML_FILE):
        print(f"ERROR: {HTML_FILE} not found.")
        return

    with open(DATA_FILE, encoding="utf-8") as f:
        data = json.load(f)

    minified = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    current_round = data["meta"]["currentRound"]

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    pattern = r'var _INLINE_DATA = \{.*?\};'
    replacement = f'var _INLINE_DATA = {minified};'
    new_html, count = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)

    if count == 0:
        print("ERROR: Could not find _INLINE_DATA in index.html.")
        return

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"Done. _INLINE_DATA updated to Round {current_round}.")

if __name__ == "__main__":
    main()
