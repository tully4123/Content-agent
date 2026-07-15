"""
Ingests a Meta Business Suite post-performance CSV from inbox/, computes a
weighted engagement score and percentile rank per post, and upserts the
results into db/pubcam.db (posts table).

Methodology ported from the real "PubCam Post Performance Model v2" Google
Sheet (Drive folder: PubCam/Business/Trackers & Spreadsheets) on 2026-07-15 -
this is CONFIRMED, not a placeholder:

  - Weights: Shares x5, Follows x6, Saves x4, Comments x3, Likes x1
  - Weighted ER = Weighted Engagement / Reach
  - Score = percentile rank against ALL other posts (not within-format)
  - Posts not posted by the pubcam.au account are EXCLUDED from scoring -
    per the source sheet: "collab posts from venue accounts have hidden
    reach/saves and will score wrong." They're still stored (tagged
    scoring_excluded=1) using the sheet's own convention,
    "[Collab post - limited insights]", so they're tracked but never
    compared against real-reach posts.
  - Rating bands: 90-100 A+, 75-89 A, 50-74 B, 25-49 C, 0-24 D

Usage:
    python scripts/score_posts.py                  # scores the newest CSV in inbox/
    python scripts/score_posts.py inbox/export.csv  # scores a specific file
"""
import csv
import datetime as dt
import sys
from pathlib import Path
import sqlite3

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
INBOX_DIR = REPO_ROOT / "inbox"

WEIGHTS = {
    "likes": 1,
    "comments": 3,
    "saves": 4,
    "shares": 5,
    "follows": 6,
}

SCORABLE_ACCOUNT = "pubcam.au"
EXCLUSION_NOTE = "[Collab post - limited insights]"  # matches PubCam_Post_Tracker's own convention
MIN_AGE_DAYS = 7  # source sheet: log posts once they're 7+ days old so scores compare fairly

# Meta Business Suite exports across a Business Portfolio don't include a
# "venue" column - only the posting account. Names match the venue labels
# already used in PubCam_Post_Tracker's "BY VENUE" summary (Drive), not the
# formal partner names in CLAUDE.md Section 1.
ACCOUNT_TO_VENUE = {
    "pubcam.au": "PubCam original",
    "heydaywollongong": "Heyday",
    "socialsundays_": "Illawarra",
    "illa_afterdark": "Illawarra",
    "afterglowshq": "Illawarra",
}

# Accepts a few common Meta Business Suite export header spellings per field.
COLUMN_ALIASES = {
    "post_id": ["post_id", "Post ID", "Permalink"],
    "account_username": ["account_username", "Account username"],
    "venue": ["venue", "Venue"],  # present in hand-built CSVs; real exports use account_username instead
    "format": ["format", "Format", "Post type", "Media type"],
    "caption": ["caption", "Caption", "Description"],
    "posted_at": ["posted_at", "Publish time", "Date", "Posted"],
    "views": ["views", "Views"],
    "reach": ["reach", "Reach", "Accounts reached"],
    "likes": ["likes", "Likes"],
    "comments": ["comments", "Comments"],
    "saves": ["saves", "Saves", "Saved"],
    "shares": ["shares", "Shares"],
    "follows": ["follows", "Follows", "Follows and likes", "New follows"],
}

NUMERIC_FIELDS = ("views", "reach", "likes", "comments", "saves", "shares", "follows")

RATING_BANDS = [
    (90, 100, "A+"),
    (75, 90, "A"),
    (50, 75, "B"),
    (25, 50, "C"),
    (0, 25, "D"),
]

FLAG_TOP_PCT = 0.80   # percentile at/above which a post is flagged an overperformer
FLAG_BOTTOM_PCT = 0.20  # percentile at/below which a post is flagged an underperformer


def rating_for(percentile: float) -> str:
    for low, high, label in RATING_BANDS:
        if low <= percentile <= high:
            return label
    return "?"


def resolve_column(fieldnames: list[str], field: str) -> str | None:
    for alias in COLUMN_ALIASES[field]:
        if alias in fieldnames:
            return alias
    return None


def find_latest_csv() -> Path:
    candidates = sorted(INBOX_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No CSV files found in {INBOX_DIR}")
    return candidates[0]


def normalize_format(raw: str) -> str:
    # "IG reel" / "IG carousel" / "IG image" -> "reel" / "carousel" / "photo"
    value = raw.strip().lower()
    if value.startswith("ig "):
        value = value[3:]
    if value == "image":
        value = "photo"
    return value


def normalize_posted_at(raw: str) -> str:
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(raw.strip(), fmt).isoformat()
        except ValueError:
            continue
    return raw.strip()  # unrecognised format - keep raw rather than fail the whole import


def resolve_venue(row: dict, colmap: dict) -> tuple[str, str | None]:
    """Returns (venue, account_username_or_None)."""
    if colmap.get("venue"):
        return row["venue"], None
    username = row["account_username"]
    if username in ACCOUNT_TO_VENUE:
        return ACCOUNT_TO_VENUE[username], username
    print(f"WARNING: no venue mapping for account '{username}' - using the username as venue. "
          f"Add it to ACCOUNT_TO_VENUE in scripts/score_posts.py.")
    return username, username


def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        colmap = {field: resolve_column(fieldnames, field) for field in COLUMN_ALIASES}

        has_venue = colmap["venue"] is not None
        has_account = colmap["account_username"] is not None
        if not has_venue and not has_account:
            raise ValueError(
                "CSV has neither a 'venue' column nor an 'Account username' column - "
                f"can't determine venue. Found headers: {fieldnames}"
            )
        missing_required = [f for f in ("post_id", "format", "posted_at") if colmap[f] is None]
        if missing_required:
            raise ValueError(
                f"CSV is missing required columns: {missing_required}. "
                f"Found headers: {fieldnames}. Add aliases to COLUMN_ALIASES if this is a new export format."
            )

        rows = []
        for raw in reader:
            row = {}
            for field, col in colmap.items():
                value = raw.get(col, "") if col else ""
                if field in NUMERIC_FIELDS:
                    row[field] = int(float(value)) if value not in ("", None) else None
                else:
                    row[field] = value.strip() if value else ""

            row["format"] = normalize_format(row["format"])
            row["posted_at"] = normalize_posted_at(row["posted_at"])
            row["venue"], row["account"] = resolve_venue(row, colmap)

            for field in ("likes", "comments", "saves", "shares", "follows", "views"):
                if row[field] is None:
                    row[field] = 0

            not_pubcam = row["account"] is not None and row["account"] != SCORABLE_ACCOUNT
            no_reach = row["reach"] is None
            if not_pubcam or no_reach:
                row["scoring_excluded"] = 1
                row["exclusion_reason"] = EXCLUSION_NOTE
            else:
                row["scoring_excluded"] = 0
                row["exclusion_reason"] = None

            rows.append(row)
        return rows


def compute_scores(rows: list[dict]) -> list[dict]:
    scorable = [r for r in rows if not r["scoring_excluded"]]

    for row in scorable:
        weighted_sum = sum(WEIGHTS[k] * row[k] for k in WEIGHTS)
        reach = row["reach"] or 0
        row["weighted_score"] = round((weighted_sum / reach) * 1000, 4) if reach else 0.0

    scorable.sort(key=lambda r: r["weighted_score"])
    n = len(scorable)
    for i, row in enumerate(scorable):
        row["percentile"] = round((i / (n - 1)) * 100, 2) if n > 1 else 100.0
        row["rating"] = rating_for(row["percentile"])

    for row in rows:
        if row["scoring_excluded"]:
            row["weighted_score"] = None
            row["percentile"] = None
            row["rating"] = None

    return rows


def flag_young_posts(rows: list[dict]) -> list[dict]:
    today = dt.date.today()
    young = []
    for row in rows:
        try:
            posted = dt.datetime.fromisoformat(row["posted_at"]).date()
        except ValueError:
            continue
        if (today - posted).days < MIN_AGE_DAYS:
            young.append(row)
    return young


def upsert(rows: list[dict]) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executemany(
            """
            INSERT INTO posts (post_id, account, venue, format, caption, posted_at,
                                views, reach, scoring_excluded, exclusion_reason,
                                likes, comments, saves, shares, follows,
                                weighted_score, percentile, rating)
            VALUES (:post_id, :account, :venue, :format, :caption, :posted_at,
                    :views, :reach, :scoring_excluded, :exclusion_reason,
                    :likes, :comments, :saves, :shares, :follows,
                    :weighted_score, :percentile, :rating)
            ON CONFLICT(post_id) DO UPDATE SET
                account=excluded.account, venue=excluded.venue, format=excluded.format,
                caption=excluded.caption, posted_at=excluded.posted_at, views=excluded.views,
                reach=excluded.reach, scoring_excluded=excluded.scoring_excluded,
                exclusion_reason=excluded.exclusion_reason,
                likes=excluded.likes, comments=excluded.comments, saves=excluded.saves,
                shares=excluded.shares, follows=excluded.follows,
                weighted_score=excluded.weighted_score, percentile=excluded.percentile,
                rating=excluded.rating
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def print_summary(rows: list[dict]) -> None:
    scorable = [r for r in rows if not r["scoring_excluded"]]
    excluded = [r for r in rows if r["scoring_excluded"]]
    overperformers = [r for r in scorable if r["percentile"] >= FLAG_TOP_PCT * 100]
    underperformers = [r for r in scorable if r["percentile"] <= FLAG_BOTTOM_PCT * 100]

    print(f"Scored {len(scorable)} pubcam.au post(s) (global percentile, not by format).")
    if excluded:
        print(f"{len(excluded)} post(s) excluded from scoring - not posted by {SCORABLE_ACCOUNT}, "
              f"tagged '{EXCLUSION_NOTE}' (stored for reference only, per PubCam_Post_Tracker convention).")
    young = flag_young_posts(scorable)
    if young:
        print(f"CAUTION: {len(young)} scored post(s) are under {MIN_AGE_DAYS} days old - "
              f"engagement may still be accruing, scores may shift: "
              + ", ".join(r["post_id"] for r in young))
    print()

    print(f"Overperformers (>= {int(FLAG_TOP_PCT * 100)}th percentile):")
    for r in sorted(overperformers, key=lambda r: -r["percentile"]):
        print(f"  [{r['rating']}] [{r['format']}] {r['post_id']} - {r['venue']} - "
              f"score {r['weighted_score']} (p{r['percentile']})")

    print(f"\nUnderperformers (<= {int(FLAG_BOTTOM_PCT * 100)}th percentile):")
    for r in sorted(underperformers, key=lambda r: r["percentile"]):
        print(f"  [{r['rating']}] [{r['format']}] {r['post_id']} - {r['venue']} - "
              f"score {r['weighted_score']} (p{r['percentile']})")


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_csv()
    print(f"Scoring {csv_path}")
    rows = load_rows(csv_path)
    rows = compute_scores(rows)
    upsert(rows)
    print_summary(rows)


if __name__ == "__main__":
    main()
