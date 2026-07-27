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
    python scripts/db.py add-trend --platform tiktok --description "..." --source-url "..." --relevance "..."
    python scripts/db.py list-trends --open
    python scripts/db.py mark-trend --id 2 --acted-on
    python scripts/db.py get-reel-ref --id 1
    python scripts/db.py link-reel-ref --id 1 --idea-id 9
    python scripts/db.py get-post-ref --id 1
    python scripts/db.py link-post-ref --id 1 --idea-id 10
    python scripts/db.py voice-sample --limit 6
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Windows consoles default to cp1252, which chokes on emoji in captions/briefs.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB_PATH = Path(__file__).parent.parent / "db" / "pubcam.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def print_rows(rows: list[sqlite3.Row]) -> None:
    # Compact JSON on purpose: these outputs land in agent context windows,
    # so whitespace and bloat cost real tokens on every single run.
    print(json.dumps([dict(r) for r in rows], separators=(",", ":"), ensure_ascii=False))


def clip(text, n: int = 60):
    if text is None:
        return None
    text = str(text).replace("\n", " ")
    return text if len(text) <= n else text[: n - 3] + "..."


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


POST_COLS = ("post_id, format, venue, substr(date(posted_at),1,10) AS posted, caption,"
             " reach, saves, shares, follows, weighted_score, percentile, rating")


def _posts_query(args, order: str) -> None:
    conn = connect()
    query = f"SELECT {POST_COLS} FROM posts WHERE percentile IS NOT NULL"
    params = []
    if args.format:
        query += " AND format = ?"
        params.append(args.format)
    query += f" ORDER BY percentile {order} LIMIT ?"
    params.append(args.limit)
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    for r in rows:
        r["caption"] = clip(r["caption"], 200 if args.full else 60)
    print(json.dumps(rows, separators=(",", ":"), ensure_ascii=False))


def top_posts(args) -> None:
    _posts_query(args, "DESC")


def bottom_posts(args) -> None:
    _posts_query(args, "ASC")


def voice_sample(args) -> None:
    """Full, unclipped captions from the top-scoring posts - grounding for
    voice/style questions. digest and top-posts clip captions for token
    economy, too short to actually learn a tone from; this doesn't clip."""
    conn = connect()
    query = f"SELECT {POST_COLS} FROM posts WHERE percentile IS NOT NULL"
    params = []
    if args.format:
        query += " AND format = ?"
        params.append(args.format)
    query += " ORDER BY percentile DESC LIMIT ?"
    params.append(args.limit)
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    print(json.dumps(rows, separators=(",", ":"), ensure_ascii=False))


def digest(args) -> None:
    """One-shot compact snapshot of the whole database - the cheap way for
    agents to load context (replaces 4+ separate list commands)."""
    conn = connect()
    out = {}

    stats = conn.execute(
        "SELECT COUNT(*) AS n, ROUND(AVG(weighted_score),1) AS avg_score"
        " FROM posts WHERE percentile IS NOT NULL"
    ).fetchone()
    fmt_rows = conn.execute(
        "SELECT format, COUNT(*) AS n, ROUND(AVG(weighted_score),1) AS avg"
        " FROM posts WHERE percentile IS NOT NULL GROUP BY format ORDER BY avg DESC"
    ).fetchall()
    top = conn.execute(
        "SELECT post_id, format, weighted_score, rating, caption FROM posts"
        " WHERE percentile IS NOT NULL ORDER BY percentile DESC LIMIT 3"
    ).fetchall()
    bottom = conn.execute(
        "SELECT post_id, format, weighted_score, rating, caption FROM posts"
        " WHERE percentile IS NOT NULL ORDER BY percentile ASC LIMIT 2"
    ).fetchall()
    out["posts"] = {
        "scored": stats["n"], "avg_score": stats["avg_score"],
        "by_format": {r["format"]: {"n": r["n"], "avg": r["avg"]} for r in fmt_rows},
        "top": [f"{r['post_id']} [{r['format']}/{r['rating']}] {r['weighted_score']} - {clip(r['caption'], 50)}" for r in top],
        "bottom": [f"{r['post_id']} [{r['format']}/{r['rating']}] {r['weighted_score']} - {clip(r['caption'], 50)}" for r in bottom],
    }

    idea_counts = conn.execute("SELECT status, COUNT(*) AS n FROM ideas GROUP BY status").fetchall()
    backlog = conn.execute("SELECT id, title, format FROM ideas WHERE status='backlog' ORDER BY id").fetchall()
    approved = conn.execute(
        "SELECT ideas.id, ideas.title, ideas.format,"
        " EXISTS(SELECT 1 FROM briefs WHERE briefs.idea_id=ideas.id) AS has_brief"
        " FROM ideas WHERE status IN ('approved','scheduled') ORDER BY ideas.id"
    ).fetchall()
    out["ideas"] = {
        "counts": {r["status"]: r["n"] for r in idea_counts},
        "backlog": [f"#{r['id']} [{r['format']}] {clip(r['title'], 60)}" for r in backlog],
        "approved": [f"#{r['id']} [{r['format']}] {clip(r['title'], 60)}{'' if r['has_brief'] else ' (no brief)'}" for r in approved],
    }

    trends = conn.execute(
        "SELECT id, platform, description FROM trends WHERE acted_on=0 ORDER BY id DESC LIMIT 10"
    ).fetchall()
    out["open_trends"] = [f"#{r['id']} [{r['platform']}] {clip(r['description'], 80)}" for r in trends]

    sched = conn.execute(
        "SELECT schedule.target_date, schedule.slot, schedule.status, ideas.title"
        " FROM schedule JOIN ideas ON schedule.idea_id=ideas.id"
        " WHERE schedule.status != 'posted' ORDER BY schedule.target_date LIMIT 10"
    ).fetchall()
    out["upcoming_schedule"] = [
        f"{r['target_date']} {r['slot'] or ''} [{r['status']}] {clip(r['title'], 50)}" for r in sched
    ]

    unbuilt_refs = conn.execute(
        "SELECT id, venue_fit, notes FROM reel_refs WHERE idea_id IS NULL ORDER BY id DESC LIMIT 5"
    ).fetchall()
    out["unbuilt_reel_refs"] = [
        f"#{r['id']} [{r['venue_fit'] or 'unset'}] {clip(r['notes'], 60)}" for r in unbuilt_refs
    ]

    unbuilt_post_refs = conn.execute(
        "SELECT id, notes FROM post_refs WHERE idea_id IS NULL ORDER BY id DESC LIMIT 5"
    ).fetchall()
    out["unbuilt_post_refs"] = [f"#{r['id']} {clip(r['notes'], 60)}" for r in unbuilt_post_refs]

    print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))


def add_trend(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO trends (platform, description, source_url, relevance_note) VALUES (?, ?, ?, ?)",
        (args.platform, args.description, args.source_url, args.relevance),
    )
    conn.commit()
    print(f"Added trend id={cur.lastrowid}")


def list_trends(args) -> None:
    conn = connect()
    query = "SELECT * FROM trends"
    if args.open:
        query += " WHERE acted_on = 0"
    query += " ORDER BY date_spotted DESC, id DESC"
    rows = conn.execute(query).fetchall()
    print_rows(rows)


def mark_trend(args) -> None:
    conn = connect()
    conn.execute("UPDATE trends SET acted_on = ? WHERE id = ?", (1 if args.acted_on else 0, args.id))
    conn.commit()
    print(f"Updated trend id={args.id} acted_on={1 if args.acted_on else 0}")


def add_brief(args) -> None:
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        raise SystemExit("add-brief needs --file or --content")
    conn = connect()
    idea = conn.execute("SELECT id, title FROM ideas WHERE id = ?", (args.idea_id,)).fetchone()
    if not idea:
        raise SystemExit(f"No idea with id={args.idea_id}")
    cur = conn.execute("INSERT INTO briefs (idea_id, content) VALUES (?, ?)", (args.idea_id, content))
    conn.commit()
    print(f"Added brief id={cur.lastrowid} for idea {args.idea_id} ({idea['title']})")


def get_brief(args) -> None:
    conn = connect()
    row = conn.execute(
        "SELECT * FROM briefs WHERE idea_id = ? ORDER BY id DESC LIMIT 1", (args.idea_id,)
    ).fetchone()
    if not row:
        print(f"No brief for idea {args.idea_id}")
    else:
        print(row["content"])


def add_reel_ref(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO reel_refs (source_url, file_name, venue_fit, notes) VALUES (?, ?, ?, ?)",
        (args.source_url, args.file_name, args.venue_fit, args.notes),
    )
    conn.commit()
    print(f"Added reel_ref id={cur.lastrowid}")


def get_reel_ref(args) -> None:
    conn = connect()
    row = conn.execute("SELECT * FROM reel_refs WHERE id = ?", (args.id,)).fetchone()
    if not row:
        raise SystemExit(f"No reel_ref with id={args.id}")
    print(json.dumps(dict(row), separators=(",", ":"), ensure_ascii=False))


def list_reel_refs(args) -> None:
    conn = connect()
    query = "SELECT * FROM reel_refs"
    if args.unbuilt:
        query += " WHERE idea_id IS NULL"
    query += " ORDER BY id DESC"
    print_rows(conn.execute(query).fetchall())


def link_reel_ref(args) -> None:
    conn = connect()
    conn.execute("UPDATE reel_refs SET idea_id = ? WHERE id = ?", (args.idea_id, args.id))
    conn.commit()
    print(f"Linked reel_ref {args.id} -> idea {args.idea_id}")


def add_post_ref(args) -> None:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO post_refs (source_url, file_name, notes) VALUES (?, ?, ?)",
        (args.source_url, args.file_name, args.notes),
    )
    conn.commit()
    print(f"Added post_ref id={cur.lastrowid}")


def get_post_ref(args) -> None:
    conn = connect()
    row = conn.execute("SELECT * FROM post_refs WHERE id = ?", (args.id,)).fetchone()
    if not row:
        raise SystemExit(f"No post_ref with id={args.id}")
    print(json.dumps(dict(row), separators=(",", ":"), ensure_ascii=False))


def list_post_refs(args) -> None:
    conn = connect()
    query = "SELECT * FROM post_refs"
    if args.unbuilt:
        query += " WHERE idea_id IS NULL"
    query += " ORDER BY id DESC"
    print_rows(conn.execute(query).fetchall())


def link_post_ref(args) -> None:
    conn = connect()
    conn.execute("UPDATE post_refs SET idea_id = ? WHERE id = ?", (args.idea_id, args.id))
    conn.commit()
    print(f"Linked post_ref {args.id} -> idea {args.idea_id}")


def list_briefs(args) -> None:
    conn = connect()
    rows = conn.execute(
        "SELECT briefs.id, briefs.idea_id, briefs.created_at, ideas.title,"
        "       substr(briefs.content, 1, 80) AS preview"
        " FROM briefs JOIN ideas ON briefs.idea_id = ideas.id ORDER BY briefs.id DESC"
    ).fetchall()
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
    tp.add_argument("--limit", type=int, default=5)
    tp.add_argument("--full", action="store_true", help="longer captions (default is clipped to save tokens)")
    tp.set_defaults(func=top_posts)

    bp = sub.add_parser("bottom-posts", help="scored (pubcam.au) posts only - excluded posts have no percentile")
    bp.add_argument("--format")
    bp.add_argument("--limit", type=int, default=5)
    bp.add_argument("--full", action="store_true", help="longer captions (default is clipped to save tokens)")
    bp.set_defaults(func=bottom_posts)

    vs = sub.add_parser("voice-sample", help="full unclipped captions from top-scoring posts - grounding for voice/style questions")
    vs.add_argument("--format")
    vs.add_argument("--limit", type=int, default=6)
    vs.set_defaults(func=voice_sample)

    dg = sub.add_parser("digest", help="compact one-shot snapshot of posts/ideas/trends/schedule - agents should start here")
    dg.set_defaults(func=digest)

    at = sub.add_parser("add-trend")
    at.add_argument("--platform", required=True, help="e.g. tiktok, instagram, reddit, news")
    at.add_argument("--description", required=True)
    at.add_argument("--source-url")
    at.add_argument("--relevance", help="why this matters for PubCam specifically")
    at.set_defaults(func=add_trend)

    lt = sub.add_parser("list-trends")
    lt.add_argument("--open", action="store_true", help="only trends not yet acted on")
    lt.set_defaults(func=list_trends)

    mt = sub.add_parser("mark-trend")
    mt.add_argument("--id", required=True, type=int)
    mt.add_argument("--acted-on", action="store_true")
    mt.set_defaults(func=mark_trend)

    ab = sub.add_parser("add-brief", help="attach a production brief to an idea")
    ab.add_argument("--idea-id", required=True, type=int)
    ab.add_argument("--file", help="path to a markdown file with the brief content")
    ab.add_argument("--content", help="brief content inline (short briefs only)")
    ab.set_defaults(func=add_brief)

    gb = sub.add_parser("get-brief", help="print the latest brief for an idea")
    gb.add_argument("--idea-id", required=True, type=int)
    gb.set_defaults(func=get_brief)

    lb = sub.add_parser("list-briefs")
    lb.set_defaults(func=list_briefs)

    ar = sub.add_parser("add-reel-ref", help="log a reference reel (app uses this directly; agents shouldn't need it)")
    ar.add_argument("--source-url")
    ar.add_argument("--file-name")
    ar.add_argument("--venue-fit")
    ar.add_argument("--notes", required=True, help="what to copy from this reference - hook, pacing, structure")
    ar.set_defaults(func=add_reel_ref)

    gr = sub.add_parser("get-reel-ref", help="read one reference reel's notes/url/venue-fit")
    gr.add_argument("--id", required=True, type=int)
    gr.set_defaults(func=get_reel_ref)

    lr = sub.add_parser("list-reel-refs")
    lr.add_argument("--unbuilt", action="store_true", help="only references with no idea built from them yet")
    lr.set_defaults(func=list_reel_refs)

    lkr = sub.add_parser("link-reel-ref", help="attach a reference reel to the idea built from it")
    lkr.add_argument("--id", required=True, type=int)
    lkr.add_argument("--idea-id", required=True, type=int)
    lkr.set_defaults(func=link_reel_ref)

    ap_ = sub.add_parser("add-post-ref", help="log a reference post structure (app uses this directly; agents shouldn't need it)")
    ap_.add_argument("--source-url")
    ap_.add_argument("--file-name")
    ap_.add_argument("--notes", required=True, help="the structure to copy - not a caption, the layout/mechanic")
    ap_.set_defaults(func=add_post_ref)

    gp = sub.add_parser("get-post-ref", help="read one reference post's notes/url")
    gp.add_argument("--id", required=True, type=int)
    gp.set_defaults(func=get_post_ref)

    lp = sub.add_parser("list-post-refs")
    lp.add_argument("--unbuilt", action="store_true", help="only references with no idea built from them yet")
    lp.set_defaults(func=list_post_refs)

    lkp = sub.add_parser("link-post-ref", help="attach a reference post to the idea built from it")
    lkp.add_argument("--id", required=True, type=int)
    lkp.add_argument("--idea-id", required=True, type=int)
    lkp.set_defaults(func=link_post_ref)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
