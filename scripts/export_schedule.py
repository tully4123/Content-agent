"""
Exports the `schedule` table to markdown (default) or CSV, for sharing with
the team outside the terminal. Notion sync (build spec Section 6) is a
separate, not-yet-built integration - this just produces a file in reports/.

Usage:
    python scripts/export_schedule.py                          # markdown, all rows
    python scripts/export_schedule.py --format csv
    python scripts/export_schedule.py --status proposed
    python scripts/export_schedule.py --week-start 2026-07-20   # only that Mon-Sun week
"""
import argparse
import csv as csv_module
import datetime as dt
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
REPORTS_DIR = REPO_ROOT / "reports"


def fetch_rows(status: str | None, week_start: dt.date | None) -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = """
        SELECT schedule.id, schedule.target_date, schedule.slot, schedule.venue,
               schedule.status, schedule.actual_post_id,
               ideas.title AS idea_title, ideas.format AS idea_format
        FROM schedule JOIN ideas ON schedule.idea_id = ideas.id
    """
    clauses, params = [], []
    if status:
        clauses.append("schedule.status = ?")
        params.append(status)
    if week_start:
        week_end = week_start + dt.timedelta(days=6)
        clauses.append("schedule.target_date BETWEEN ? AND ?")
        params.extend([week_start.isoformat(), week_end.isoformat()])
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY schedule.target_date"
    return conn.execute(query, params).fetchall()


def write_markdown(rows: list[sqlite3.Row], out_path: Path) -> None:
    lines = ["# PubCam Schedule Export", "", f"Generated {dt.date.today().isoformat()}", ""]
    if not rows:
        lines.append("_No schedule rows match the given filters._")
    else:
        lines.append("| Date | Slot | Venue | Format | Idea | Status |")
        lines.append("|---|---|---|---|---|---|")
        for r in rows:
            lines.append(
                f"| {r['target_date']} | {r['slot']} | {r['venue'] or ''} | "
                f"{r['idea_format'] or ''} | {r['idea_title']} | {r['status']} |"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(rows: list[sqlite3.Row], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv_module.writer(f)
        writer.writerow(["target_date", "slot", "venue", "format", "idea_title", "status", "actual_post_id"])
        for r in rows:
            writer.writerow([r["target_date"], r["slot"], r["venue"], r["idea_format"],
                              r["idea_title"], r["status"], r["actual_post_id"]])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    parser.add_argument("--status", help="filter to a single schedule status (e.g. proposed)")
    parser.add_argument("--week-start", help="YYYY-MM-DD Monday; export only that week")
    args = parser.parse_args()

    week_start = dt.date.fromisoformat(args.week_start) if args.week_start else None
    rows = fetch_rows(args.status, week_start)

    REPORTS_DIR.mkdir(exist_ok=True)
    ext = "md" if args.format == "markdown" else "csv"
    out_path = REPORTS_DIR / f"schedule-{dt.date.today().isoformat()}.{ext}"

    if args.format == "markdown":
        write_markdown(rows, out_path)
    else:
        write_csv(rows, out_path)

    print(f"Wrote {len(rows)} row(s) to {out_path}")


if __name__ == "__main__":
    main()
