## lol-top10-champs-wr

**Short description**

This utility resolves a Riot ID (gameName#tagLine) to a PUUID, fetches recent match history via Match-v5, computes the player's most-played champions and their win rates (top 10), and attempts to display ranked entries where possible. It uses Data Dragon to obtain champion names when necessary.


## Features

- Resolve modern Riot IDs (`gameName#tagLine`) to `puuid` using `riot/account/v1` (avoids platform `by-name` restrictions).
- Fetch recent matches (match-v5) and compute top 10 champions by play count.
- Calculate win rate per champion from recent matches.
- Attempt to fetch ranked entries (league-v4) when the summoner object is available.
- Optional CSV export of the top champions.
- Basic rate-limit handling for 429 responses.


## Requirements

- Python 3.8+
- `requests` library

Install dependencies:

```bash
pip install requests
```


## Usage

1. Set your Riot API key as an environment variable (recommended) or paste it when prompted:

```bash
export RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# on Windows (PowerShell):
# setx RIOT_API_KEY "RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

2. Run the script (single-file):

```bash
python lol_top10_champs_wr.py
```

3. Enter the Riot ID (format `gameName#tagLine`, e.g. `MERTcimek#yiyin`) and the number of recent matches to scan (default 100).

4. Optionally export the top champions to `top_champs.csv` when prompted.


## Important notes

- Developer API keys expire quickly (usually 24 hours). If you see 401/403 errors, ensure your key is active and not surrounded by `<` or `>`.
- For TR platform, the script uses `europe` as the match-v5 continent routing. Summoner/league endpoints use `tr1` platform routing where applicable.
- Some Riot developer keys may have region/endpoint restrictions; the script gracefully skips rank lookup if summoner endpoints return limited data.
- Respect Riot API rate limits. The script includes basic backoff for 429 responses but is not meant for heavy production usage.


## File(s)

- `lol_top10_champs_wr.py` — Single-file Python tool containing the implementation and usage instructions.


## Example output

```
PUUID: Oyy3Z5W_...
=== Top 10 champions by plays (from recent matches) ===
Scanned matches: 100
#  Champion              Plays    Win%
1. Jinx                 12      58.33%
2. Yasuo                 9      44.44%
...

=== Ranked Queues ===
RANKED_SOLO_5x5: GOLD II - 75 LP | 120W/100L -> WR 54.55%
```


## License

MIT


## Contributing

Contributions welcome. Please open issues or PRs for bugfixes and enhancements.

