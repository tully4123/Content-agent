"""
Builds a proposed weekly schedule from approved ideas (ideas.status = 'approved'),
respecting the recurring slots and format ratio in config/schedule_slots.json.

Dry run by default - prints the proposal and writes nothing. Pass --commit to
write schedule rows (status='proposed') and flip used ideas to status='scheduled'.

Usage:
    python scripts/build_schedule.py                        # dry run, next Monday's week
    python scripts/build_schedule.py --week-start 2026-07-20
    python scripts/build_schedule.py --commit
"""
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
CONFIG_PATH = REPO_ROOT / "config" / "schedule_slots.json"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def next_monday(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    days_ahead = (7 - today.weekday()) % 7 or 7
    return today + dt.timedelta(days=days_ahead)


def week_dates(week_start: dt.date, slots: list[dict]) -> list[tuple[dt.date, dict]]:
    out = []
    for slot in slots:
        offset = WEEKDAYS.index(slot["day"])
        out.append((week_start + dt.timedelta(days=offset), slot))
    return out


def format_sequence(ratio: dict, length: int) -> list[str]:
    """Weighted round-robin (largest-remainder, applied repeatedly) so formats interleave
    rather than clumping - e.g. {"carousel":2,"reel":1} over 3 slots -> [carousel, reel, carousel]."""
    formats = list(ratio.keys())
    weights = list(ratio.values())
    total_weight = sum(weights)
    sequence = []
    accumulators = [0.0] * len(formats)
    for _ in range(length):
        for i in range(len(formats)):
            accumulators[i] += weights[i] / total_weight
        pick = max(range(len(formats)), key=lambda i: accumulators[i])
        sequence.append(formats[pick])
        accumulators[pick] -= 1.0
    return sequence


def build_proposal(ideas: list[sqlite3.Row], week_start: dt.date, config: dict) -> list[dict]:
    slots = week_dates(week_start, config["recurring_slots"])
    desired_formats = format_sequence(config["default_format_ratio"], len(slots))

    remaining = list(ideas)  # FIFO by id (see SKILL.md note on priority ordering)
    assignments = []
    for (date, slot), desired_format in zip(slots, desired_formats):
        match = next((idea for idea in remaining if idea["format"] == desired_format), None)
        idea = match or (remaining[0] if remaining else None)
        if idea is None:
            assignments.append({"date": date, "slot": slot, "idea": None, "note": "no approved ideas left"})
            continue
        remaining.remove(idea)
        note = "" if match else f"no approved '{desired_format}' idea available, used next in backlog instead"
        assignments.append({"date": date, "slot": slot, "idea": idea, "note": note})

    # One pass of venue-adjacency smoothing: swap forward if it removes a same-venue-in-a-row
    # collision without creating a new one immediately before it.
    for i in range(len(assignments) - 1):
        cur, nxt = assignments[i], assignments[i + 1]
        if not cur["idea"] or not nxt["idea"]:
            continue
        if cur["idea"]["venue_fit"] == nxt["idea"]["venue_fit"]:
            for j in range(i + 2, len(assignments)):
                cand = assignments[j]
                if not cand["idea"]:
                    continue
                if cand["idea"]["venue_fit"] != cur["idea"]["venue_fit"]:
                    assignments[i + 1]["idea"], assignments[j]["idea"] = cand["idea"], nxt["idea"]
                    break

    if remaining:
        print(f"Note: {len(remaining)} approved idea(s) didn't fit this week's slots and stay 'approved': "
              + ", ".join(f"#{i['id']} {i['title']}" for i in remaining))

    return assignments


def print_proposal(assignments: list[dict]) -> None:
    print(f"{'Date':<12}{'Day':<10}{'Time':<7}{'Venue':<20}{'Format':<10}Idea")
    for a in assignments:
        date_str = a["date"].isoformat()
        day, time = a["slot"]["day"], a["slot"]["time"]
        if a["idea"] is None:
            print(f"{date_str:<12}{day:<10}{time:<7}{'(none)':<20}{'':<10}-- {a['note']} --")
            continue
        idea = a["idea"]
        line = f"{date_str:<12}{day:<10}{time:<7}{(idea['venue_fit'] or ''):<20}{idea['format']:<10}#{idea['id']} {idea['title']}"
        print(line)
        if a["note"]:
            print(f"    note: {a['note']}")


def commit(assignments: list[dict], conn: sqlite3.Connection) -> int:
    committed = 0
    for a in assignments:
        if a["idea"] is None:
            continue
        idea = a["idea"]
        conn.execute(
            "INSERT INTO schedule (idea_id, venue, target_date, slot, status) VALUES (?, ?, ?, ?, 'proposed')",
            (idea["id"], idea["venue_fit"], a["date"].isoformat(), f"{a['slot']['day']} {a['slot']['time']}"),
        )
        conn.execute("UPDATE ideas SET status = 'scheduled' WHERE id = ?", (idea["id"],))
        committed += 1
    conn.commit()
    return committed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-start", help="YYYY-MM-DD, must be a Monday. Defaults to next Monday.")
    parser.add_argument("--commit", action="store_true", help="write to db instead of a dry run")
    args = parser.parse_args()

    week_start = dt.date.fromisoformat(args.week_start) if args.week_start else next_monday()
    if week_start.weekday() != 0:
        raise ValueError(f"--week-start must be a Monday, got {week_start} ({WEEKDAYS[week_start.weekday()]})")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ideas = conn.execute("SELECT * FROM ideas WHERE status = 'approved' ORDER BY id").fetchall()

    if not ideas:
        print("No approved ideas in the backlog. Approve ideas first: "
              "python scripts/db.py update-idea --id N --status approved")
        return

    config = load_config()
    assignments = build_proposal(ideas, week_start, config)
    print(f"Proposed schedule for week of {week_start.isoformat()}:\n")
    print_proposal(assignments)

    if args.commit:
        n = commit(assignments, conn)
        print(f"\nCommitted {n} schedule row(s), status='proposed'. Matching ideas flipped to status='scheduled'.")
    else:
        print("\nDry run - nothing written. Re-run with --commit to write this to the schedule table.")


if __name__ == "__main__":
    main()
