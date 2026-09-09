"""Watch the leaderboard, and watch the shape of the thing being scored.

The second half is the point. On 2026-09-04 the organisers replaced the ranking set:
July went from three airports to ten, scored departures went from 215,876 to 344,841,
and every submission on the board was erased. There was no announcement on the website.
We found out three days later, by reading the API for another reason.

The API reports `usedPairs` beside every score, and that integer is the row count the
ranking script actually used. It is the cheapest possible alarm: if it ever differs from
what our own `submitting.parquet` holds, the scored set has been swapped again and every
local measurement is stale. This script exits non-zero when that happens, so it can be
put on a timer and be silent until it matters.

    python scripts/watch_board.py                 # table plus the shape check
    python scripts/watch_board.py --quiet         # only speak when something changed
    python scripts/watch_board.py --team vibrant-lollipop --history
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from taxiout import config

TIMEOUT_SEC = 60
PAGE = 100


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as response:  # noqa: S310
        return json.load(response)


def all_submissions() -> list[dict]:
    rows: list[dict] = []
    cursor: str | None = None
    while True:
        url = f"{config.LEADERBOARD_URL}?limit={PAGE}" + (f"&cursor={cursor}" if cursor else "")
        page = fetch(url)
        rows += page["items"]
        cursor = page.get("nextCursor")
        if not cursor:
            return rows


def expected_rows() -> int | None:
    """How many rows our own submission template has, or None if it is not here."""
    template = config.raw() / "submitting.parquet"
    if not template.exists():
        return None
    import polars as pl

    return pl.read_parquet(template).height


def main() -> int:
    ap = argparse.ArgumentParser(description="leaderboard, and an alarm on the scored set")
    ap.add_argument("--team", default=config.TEAM)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--history", action="store_true", help="list our own submissions")
    ap.add_argument("--quiet", action="store_true", help="print only when the shape moved")
    ap.add_argument("--state", default=None, help="remember the shape in this JSON file")
    args = ap.parse_args()

    rows = all_submissions()
    if not rows:
        print("the leaderboard is empty, which has never happened before: check the API")
        return 2

    pairs = sorted({r["usedPairs"] for r in rows})
    expected = expected_rows()
    changed = expected is not None and pairs != [expected]

    if args.state:
        state_file = Path(args.state)
        previous = json.loads(state_file.read_text()) if state_file.exists() else {}
        changed = changed or (previous.get("usedPairs") not in (None, pairs))
        state_file.write_text(json.dumps({"usedPairs": pairs}, indent=2))

    if changed:
        print("!" * 72)
        print(f"THE SCORED SET MOVED. the board scores {pairs} rows, our template has "
              f"{expected}.")
        print("Re-download ranking.parquet and submitting.parquet, rebuild the cache, and")
        print("treat every local measurement taken before now as stale.")
        print("!" * 72)
    elif not args.quiet:
        print(f"scored rows: {pairs[0]:,} (our template agrees)"
              if expected else f"scored rows: {pairs}")

    if args.quiet and not changed:
        return 0

    best: dict[str, dict] = {}
    count: dict[str, int] = {}
    for r in rows:
        team = r["teamName"]
        count[team] = count.get(team, 0) + 1
        if team not in best or r["score"] < best[team]["score"]:
            best[team] = r

    order = sorted(best.items(), key=lambda kv: kv[1]["score"])
    ours = next((i for i, (t, _) in enumerate(order, 1) if t == args.team), None)
    print(f"\n{len(rows)} submissions from {len(best)} scoring teams"
          + (f"; {args.team} is {ours} of {len(best)}" if ours else
             f"; {args.team} has not scored yet"))

    print(f"\n{'#':>3} {'team':<24} {'best':>10} {'subs':>5}  {'when'}")
    shown = order[: args.top]
    if ours and ours > args.top:
        shown = shown + [order[ours - 1]]
    for team, row in shown:
        rank = order.index((team, row)) + 1
        mark = "  <-- us" if team == args.team else ""
        print(f"{rank:>3} {team:<24} {row['score']:>10.4f} {count[team]:>5}  "
              f"{row['processedAt'][:16]}{mark}")

    if args.history:
        mine = sorted((r for r in rows if r["teamName"] == args.team),
                      key=lambda r: r["processedAt"])
        print(f"\n{args.team}, oldest first:")
        for r in mine:
            print(f"  {r['filename']:<34} {r['score']:>10.4f}  {r['processedAt'][:19]}")

    return 3 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
