---
name: trend-sweep
description: Web research pass for content trends relevant to PubCam - nightlife/hospitality social content formats, sounds, and meme structures. Writes candidates to the trends table. Use on the Monday cadence or when the user asks what's trending.
---

# trend-sweep

## Goal

Find content *formats and angles* PubCam could adapt - not generic marketing
news. A good trend candidate is something a Wollongong nightlife page could
film or post within a week.

## Steps

1. Check what's already logged so you don't re-add known trends (digest is
   the cheap way - it lists open trend titles):
   ```
   python scripts/db.py digest
   ```
2. Run research passes with WebSearch (and WebFetch on promising results).
   **Token budget: at most 2-3 searches and 1-2 fetches per sweep** - pick
   the highest-yield queries rather than sweeping every area every time.
   Query areas, adapted to the current month/season:
   - "trending Instagram Reels formats bars nightlife" + current month/year
   - "TikTok trends hospitality venues this week"
   - TikTok Creative Center (fetch https://ads.tiktok.com/business/creativecenter/
     trend pages if fetchable; skip without complaint if JS-blocked)
   - Reddit: r/socialmedia, r/InstagramMarketing threads from the past month
   - Australian nightlife/hospitality news for seasonal moments (State of
     Origin, uni semester dates, winter events)
3. Filter hard. Keep a candidate only if ALL of:
   - PubCam or a venue partner could realistically execute it (no big
     production budgets, no US-only references)
   - It fits the collab/venue model or PubCam's guide-carousel strengths
     (see CLAUDE.md Sections 1 and 3)
   - You can cite a real source URL you actually opened - never invent a
     trend or a URL (CLAUDE.md Section 5)
4. Log each keeper:
   ```
   python scripts/db.py add-trend --platform tiktok --description "..." --source-url "..." --relevance "why this fits PubCam"
   ```
   3-6 good candidates beat 15 weak ones.
5. Summarise for the user: what you logged, what you saw but rejected (one
   line each, so they can veto your filtering), and whether anything is
   time-sensitive (post this week or lose it).
6. Do NOT create ideas directly - that's idea-generator's job. Trends are
   raw material; ideas are concrete post concepts.

## Cadence note

Designed for Monday mornings (build spec Section 8), before /plan-week, so
fresh trends can feed idea-generator the same morning.
