"""
README (top of file) - League of Legends: Top 10 Champions by Playcount & Win Rate
------------------------------------------------------------------------------

This single-file Python utility fetches a player's recent matches, computes the
most-played champions and their win rates (top 10), and attempts to display the
player's ranked entries. It is designed to be GitHub-ready and the source and
instructions are embedded in English at the top of this file.

Requirements
------------
- Python 3.8+
- requests

Install dependencies:
    pip install requests

Usage
-----
1) Export your Riot developer API key or enter it when prompted. Developer keys
   expire after a short time (usually 24 hours) so make sure your key is active.

    # Option A: set environment variable (recommended)
    export RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

    # Option B: you will be prompted to paste the key when running the script

2) Run the script
    python lol_top10_champs_wr.py

3) Provide the Riot ID in the format: gameName#tagLine
   Example: MERTcimek#yiyin

Options
-------
- The script asks for how many recent matches to scan (default 100).
- It writes an optional CSV file (top_champs.csv) if you answer yes at prompt.

Notes / Implementation details
------------------------------
- Uses `riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}` to resolve the
  modern Riot ID to a `puuid`. This avoids TR1/by-name restrictions.
- Uses match-v5 on the continent endpoint (europe) for TR platform's match
  data. Uses platform (tr1) for summoner & league endpoints where applicable.
- For champion names: tries `participant['championName']` first (match data
  usually includes readable names). If missing, the script falls back to
  Data Dragon mapping (champion key -> name).
- Rank lookup uses `summoner/v4/by-puuid` to get the `summonerId`, but if that
  endpoint returns limited data or fails, the script will gracefully skip rank
  display and continue with match statistics.
- The script includes basic rate-limit handling for 429 responses.

License
-------
MIT

"""

import os
import sys
import time
import csv
import requests
from collections import Counter

# ----------------------- Configuration -----------------------
API_KEY = os.getenv("RIOT_API_KEY") or input("Riot API key: ").strip()
RIOT_ID = input("Riot ID (gameName#tagLine), e.g. MERTcimek#yiyin: ").strip()
try:
    MATCH_COUNT = int(input("How many recent matches to scan? [default 100]: ").strip() or "100")
except ValueError:
    MATCH_COUNT = 100

PLATFORM = "tr1"                # platform routing for summoner/league endpoints
REGION_FOR_MATCH = "europe"     # match-v5 continent for TR platform
HEADERS = {"X-Riot-Token": API_KEY}
TIMEOUT = 10
SLEEP_BETWEEN_MATCHES = 0.12

# ----------------------- Helpers -----------------------

def riot_get(url, params=None, max_retries=3):
    """GET wrapper that handles rate limits and simple transient errors."""
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            if attempt + 1 == max_retries:
                print(f"Network error for {url}: {e}")
                return None
            time.sleep(1 + attempt)
            continue

        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                print(f"Invalid JSON from {url}")
                return None
        elif r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "1"))
            print(f"Rate limited (429). Sleeping for {retry_after + 1}s...")
            time.sleep(retry_after + 1)
            continue
        elif r.status_code in (502, 503, 504):
            # transient server error
            print(f"Server error ({r.status_code}) on {url}. Retrying...")
            time.sleep(1 + attempt * 2)
            continue
        else:
            # non-retryable error, show body for debugging
            try:
                body = r.json()
            except Exception:
                body = r.text
            print(f"HTTP {r.status_code} from {url}: {body}")
            return None
    return None


# ----------------------- Step 1: Resolve Riot ID -> puuid -----------------------
if "#" not in RIOT_ID:
    print("Riot ID must be in the format gameName#tagLine (e.g. MERTcimek#yiyin)")
    sys.exit(1)

gameName, tagLine = RIOT_ID.split("#", 1)
account_url = f"https://{REGION_FOR_MATCH}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{requests.utils.quote(gameName)}/{requests.utils.quote(tagLine)}"
print("Resolving Riot ID to PUUID...")
account = riot_get(account_url)
if not account:
    print("Failed to resolve Riot ID -> PUUID. Aborting.")
    sys.exit(1)

puuid = account.get("puuid")
if not puuid:
    print("No puuid returned from account endpoint. Aborting.")
    sys.exit(1)

print(f"PUUID: {puuid}")

# ----------------------- Step 2: (Optional) Try to get summonerId for rank -----------------------
summoner_id = None
summoner_url = f"https://{PLATFORM}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
print("Attempting to fetch summoner object (for rank lookup)...")
summoner = riot_get(summoner_url)
if summoner and isinstance(summoner, dict):
    summoner_id = summoner.get("id") or summoner.get("summonerId") or None
    # Some regions/keys may not return 'id' — handle gracefully
    if summoner_id:
        print(f"Found summoner id: {summoner_id}")
    else:
        print("Summoner object returned but no 'id' field available; rank lookup will be skipped.")
else:
    print("Could not fetch summoner object or summoner endpoint blocked; rank lookup will be skipped.")

# ----------------------- Step 3: Get recent match IDs (match-v5) -----------------------
match_ids_url = f"https://{REGION_FOR_MATCH}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
print(f"Fetching up to {MATCH_COUNT} match IDs...")
match_ids = riot_get(match_ids_url, params={"start": 0, "count": MATCH_COUNT})
if match_ids is None:
    print("Failed to fetch match ids. Aborting.")
    sys.exit(1)
if not match_ids:
    print("No matches found for this PUUID.")
    sys.exit(0)

print(f"Got {len(match_ids)} match ids (will process up to {MATCH_COUNT}).")

# ----------------------- Step 4: DataDragon champion mapping -----------------------
print("Fetching Data Dragon champion mapping...")
try:
    versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=TIMEOUT).json()
    latest = versions[0]
    champ_data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json", timeout=TIMEOUT).json()
    champ_key_to_name = {info["key"]: name for name, info in champ_data["data"].items()}
except Exception as e:
    print(f"Failed to fetch Data Dragon: {e}")
    champ_key_to_name = {}

# ----------------------- Step 5: Process matches -----------------------
champ_counts = Counter()
champ_wins = Counter()

for i, mid in enumerate(match_ids, 1):
    match_url = f"https://{REGION_FOR_MATCH}.api.riotgames.com/lol/match/v5/matches/{mid}"
    match = riot_get(match_url)
    if not match:
        print(f"Skipping match {mid} (could not fetch)")
        continue

    info = match.get("info", {})
    participants = info.get("participants", [])
    player = None
    for p in participants:
        if p.get("puuid") == puuid:
            player = p
            break
    if not player:
        print(f"Match {mid}: player not found in participants (skipping)")
        continue

    # championName is usually available; fallback to championId mapping
    champ_name = player.get("championName") or None
    if not champ_name:
        champ_id = player.get("championId")
        if champ_id is not None:
            champ_name = champ_key_to_name.get(str(champ_id)) or f"ID_{champ_id}"
        else:
            champ_name = "Unknown"

    win = player.get("win")
    champ_counts[champ_name] += 1
    if win:
        champ_wins[champ_name] += 1

    # Respectful pacing to avoid hitting rate limits too fast
    time.sleep(SLEEP_BETWEEN_MATCHES)

# ----------------------- Step 6: Output top 10 champions with WR -----------------------
print("\n=== Top 10 champions by plays (from recent matches) ===")
print(f"Scanned matches: {len(match_ids)}")
print(f"{'#':>2}  {'Champion':<20} {'Plays':>5} {'Win%':>8}")
for idx, (champ, plays) in enumerate(champ_counts.most_common(10), 1):
    wins = champ_wins.get(champ, 0)
    wr = (wins / plays) * 100 if plays > 0 else 0.0
    print(f"{idx:2d}. {champ:<20} {plays:5d} {wr:8.2f}%")

# ----------------------- Step 7: (Optional) CSV export -----------------------
if champ_counts:
    to_csv = input("Write top champions to CSV (top_champs.csv)? [y/N]: ").strip().lower() == 'y'
    if to_csv:
        with open("top_champs.csv", "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["rank", "champion", "plays", "wins", "win_rate_pct"])
            for rank, (champ, plays) in enumerate(champ_counts.most_common(10), 1):
                wins = champ_wins.get(champ, 0)
                wr = (wins / plays) * 100 if plays > 0 else 0.0
                writer.writerow([rank, champ, plays, wins, f"{wr:.2f}"])
        print("Saved top_champs.csv")

# ----------------------- Step 8: Rank lookup if summoner id available -----------------------
if summoner_id:
    league_url = f"https://{PLATFORM}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
    print("\nFetching ranked entries...")
    league_entries = riot_get(league_url)
    if league_entries is None:
        print("Failed to fetch ranked entries.")
    elif not league_entries:
        print("No ranked entries on this account.")
    else:
        print("=== Ranked Queues ===")
        for e in league_entries:
            queue = e.get('queueType', 'UNKNOWN')
            tier = e.get('tier', '')
            rank = e.get('rank', '')
            lp = e.get('leaguePoints', 0)
            wins = e.get('wins', 0)
            losses = e.get('losses', 0)
            wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
            print(f"{queue}: {tier} {rank} - {lp} LP | {wins}W/{losses}L -> WR {wr:.2f}%")
else:
    print("\nRank lookup skipped because summoner id is unavailable for this key/region.")

print("\nDone.")
