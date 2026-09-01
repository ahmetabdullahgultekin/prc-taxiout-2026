"""Fetches the live leaderboard.

The competition page shows no table; the ranking sits behind a REST API and the page embeds
it through Observable. The address was extracted from `ranking.html`.

Every submission is listed as a separate record, so the same team can appear more than once.
Teams are ranked by their **best** score (competition rule F04).

    python scripts/leaderboard.py
    python scripts/leaderboard.py --team vibrant-lollipop
"""

from __future__ import annotations

import argparse
import json
import urllib.request

COMPETITION_ID = "bb3693e1-26bc-4a9e-8619-4fe78b4eab0c"
URL = f"https://datacomp.opensky-network.org/api/competitions/{COMPETITION_ID}/leaderboard"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


def fetch() -> list[dict]:
    """Fetches every submission; paging advances through `nextCursor`."""
    items: list[dict] = []
    cursor: str | None = None
    while True:
        url = URL + (f"?cursor={cursor}" if cursor else "")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            page = json.loads(r.read())
        items.extend(page.get("items", []))
        cursor = page.get("nextCursor")
        if not cursor:
            return items


def best_per_team(items: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for it in items:
        name = it["teamName"]
        if name not in best or it["score"] < best[name]["score"]:
            best[name] = it
    return sorted(best.values(), key=lambda x: x["score"])


def main() -> None:
    ap = argparse.ArgumentParser(description="PRC 2026 leaderboard")
    ap.add_argument("--team", default=None, help="mark this team")
    ap.add_argument("--all", action="store_true", help="list every submission separately")
    args = ap.parse_args()

    items = fetch()
    print(f"{len(items)} submissions, {len({i['teamName'] for i in items})} teams have submitted\n")

    rows = sorted(items, key=lambda x: x["score"]) if args.all else best_per_team(items)
    print(f"{'#':>3}  {'team':<26} {'score':>10}  {'file':<34} processed")
    for i, r in enumerate(rows, 1):
        mark = " <<<" if args.team and r["teamName"] == args.team else ""
        print(f"{i:>3}. {r['teamName']:<26} {r['score']:>10.4f}  {r['filename']:<34} "
              f"{r['processedAt'][:19]}{mark}")

    if args.team:
        ours = [r for r in rows if r["teamName"] == args.team]
        if ours and rows:
            gap = ours[0]["score"] - rows[0]["score"]
            n = sum(1 for i in items if i["teamName"] == args.team)
            print()
            print(
                f"{args.team}: {n} submissions, "
                f"best {ours[0]['score']:.4f}, gap to the leader {gap:+.4f}"
            )


if __name__ == "__main__":
    main()
