"""
Small CLI over db/pubcam.db for the ideas / schedule / strategy_log / trends
tables, so slash commands and skills don't hand-roll SQL. `posts` writes stay
in scripts/score_posts.py - this is for everything downstream of scoring.

Usage examples:
    python scripts/db.py add-idea --title "..." --source capture --venue-fit Heyday --format reel --notes "..."
    python scripts/db.py list-ideas --status backlog
    python scripts/db.py update-idea --id 3 --status approved
    python scripts/db.py add-schedule --idea-id 3 --venue Heyday --target-date 2026-07-22 --slot "Wed 9pm"
    python scripts/db.py list-schedule --status proposed
    python scripts/db.py add-strategy --insight "..." --decision "..." --evidence "..."
    python scripts/db.py list-strategy
    python scripts/db.py top-posts --format carousel --limit 5
    python scripts/db.py bottom-posts --format carousel --limit 5
"""
import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "pubcam.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def print_rows(rows: list[sqlite3.Row]) -> None:
    print(json.dumps([dict(r) for r in rows], indent=2))


def add_idea(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO ideas (title, source, venue_fit, format, priority, status, notes) "
        "VALUES (?, ?, ?, ?, ?, 'backlog', ?)",
        (args.title, args.source, args.venue_fit, args.format, args.priority, args.notes),
    )
    conn.commit()
    print(f"Added idea id={cur.lastrowid} status=backlog")


def list_ideas(args) -> None:
    conn = connect()
    if args.status:
        rows = conn.execute("SELECT * FROM ideas WHERE status = ? ORDER BY id", (args.status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ideas ORDER BY id").fetchall()
    print_rows(rows)


def update_idea(args) -> None:
    conn = connect()
    fields, values = [], []
    for field in ("title", "venue_fit", "format", "priority", "status", "notes"):
        val = getattr(args, field.replace("-", "_"))
        if val is not None:
            fields.append(f"{field} = ?")
            values.append(val)
    if not fields:
        print("Nothing to update.")
        return
    values.append(args.id)
    conn.execute(f"UPDATE ideas SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    print(f"Updated idea id={args.id}")


def add_schedule(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO schedule (idea_id, venue, target_date, slot, status) VALUES (?, ?, ?, ?, ?)",
        (args.idea_id, args.venue, args.target_date, args.slot, args.status),
    )
    conn.commit()
    print(f"Added schedule row id={cur.lastrowid} status={args.status}")


def list_schedule(args) -> None:
    conn = connect()
    query = """
        SELECT schedule.*, ideas.title AS idea_title, ideas.format AS idea_format
        FROM schedule JOIN ideas ON schedule.idea_id = ideas.id
    """
    params = []
    if args.status:
        query += " WHERE schedule.status = ?"
        params.append(args.status)
    query += " ORDER BY schedule.target_date"
    rows = conn.execute(query, params).fetchall()
    print_rows(rows)


def add_strategy(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO strategy_log (insight, decision, evidence) VALUES (?, ?, ?)",
        (args.insight, args.decision, args.evidence),
    )
    conn.commit()
    print(f"Added strategy_log id={cur.lastrowid}")


def list_strategy(args) -> None:
    conn = connect()
    rows = conn.execute("SELECT * FROM strategy_log ORDER BY date DESC, id DESC").fetchall()
    print_rows(rows)


def top_posts(args) -> None:
    conn = connect()
    query = "SELECT * FROM posts WHERE percentile IS NOT NULL"
    params = []
    if args.format:
        query += " AND format = ?"
        params.append(args.format)
    query += " ORDER BY percentile DESC LIMIT ?"
    params.append(args.limit)
    rows = conn.execute(query, params).fetchall()
    print_rows(rows)


def bottom_posts(args) -> None:
    conn = connect()
    query = "SELECT * FROM posts WHERE percentile IS NOT NULL"
    params = []
    if args.format:
        query += " AND format = ?"
        params.append(args.format)
    query += " ORDER BY percentile ASC LIMIT ?"
    params.append(args.limit)
    rows = conn.execute(query, params).fetchall()
    print_rows(rows)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add-idea")
    a.add_argument("--title", required=True)
    a.add_argument("--source", required=True, choices=["trend-sweep", "capture", "performance-insight"])
    a.add_argument("--venue-fit")
    a.add_argument("--format")
    a.add_argument("--priority")
    a.add_argument("--notes")
    a.set_defaults(func=add_idea)

    l = sub.add_parser("list-ideas")
    l.add_argument("--status", choices=["backlog", "approved", "scheduled", "posted", "killed"])
    l.set_defaults(func=list_ideas)

    u = sub.add_parser("update-idea")
    u.add_argument("--id", required=True, type=int)
    u.add_argument("--title")
    u.add_argument("--venue-fit")
    u.add_argument("--format")
    u.add_argument("--priority")
    u.add_argument("--status", choices=["backlog", "approved", "scheduled", "posted", "killed"])
    u.add_argument("--notes")
    u.set_defaults(func=update_idea)

    s = sub.add_parser("add-schedule")
    s.add_argument("--idea-id", required=True, type=int)
    s.add_argument("--venue", required=True)
    s.add_argument("--target-date", required=True, help="YYYY-MM-DD")
    s.add_argument("--slot", required=True, help='e.g. "Thu 6pm"')
    s.add_argument("--status", default="proposed")
    s.set_defaults(func=add_schedule)

    ls = sub.add_parser("list-schedule")
    ls.add_argument("--status")
    ls.set_defaults(func=list_schedule)

    st = sub.add_parser("add-strategy")
    st.add_argument("--insight", required=True)
    st.add_argument("--decision")
    st.add_argument("--evidence")
    st.set_defaults(func=add_strategy)

    lst = sub.add_parser("list-strategy")
    lst.set_defaults(func=list_strategy)

    tp = sub.add_parser("top-posts", help="scored (pubcam.au) posts only - excluded posts have no percentile")
    tp.add_argument("--format")
    tp.add_argument("--limit", type=int, default=10)
    tp.set_defaults(func=top_posts)

    bp = sub.add_parser("bottom-posts", help="scored (pubcam.au) posts only - excluded posts have no percentile")
    bp.add_argument("--format")
    bp.add_argument("--limit", type=int, default=10)
    bp.set_defaults(func=bottom_posts)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
