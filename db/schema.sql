CREATE TABLE IF NOT EXISTS posts (
    post_id         TEXT PRIMARY KEY,
    account         TEXT,
    venue           TEXT NOT NULL,
    format          TEXT NOT NULL CHECK (format IN ('reel', 'carousel', 'photo', 'collab')),
    caption         TEXT,
    posted_at       TEXT NOT NULL,
    views           INTEGER,
    reach           INTEGER,
    scoring_excluded INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,
    likes           INTEGER,
    comments        INTEGER,
    saves           INTEGER,
    shares          INTEGER,
    follows         INTEGER,
    weighted_score  REAL,
    percentile      REAL,
    rating          TEXT
);

CREATE TABLE IF NOT EXISTS ideas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('trend-sweep', 'capture', 'performance-insight')),
    venue_fit   TEXT,
    format      TEXT,
    priority    TEXT,
    status      TEXT NOT NULL DEFAULT 'backlog'
                CHECK (status IN ('backlog', 'approved', 'scheduled', 'posted', 'killed')),
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schedule (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    idea_id         INTEGER REFERENCES ideas(id),
    venue           TEXT,
    target_date     TEXT,
    slot            TEXT,
    status          TEXT,
    actual_post_id  TEXT REFERENCES posts(post_id)
);

CREATE TABLE IF NOT EXISTS trends (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date_spotted    TEXT NOT NULL DEFAULT (date('now')),
    platform        TEXT,
    description     TEXT NOT NULL,
    source_url      TEXT,
    relevance_note  TEXT,
    acted_on        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS strategy_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT NOT NULL DEFAULT (date('now')),
    insight   TEXT NOT NULL,
    decision  TEXT,
    evidence  TEXT
);
