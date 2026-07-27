import streamlit as st

st.markdown(
    """
This app is your home base - open it **before** you make anything on Instagram.
It shares one database with the Claude Code agent (the terminal side), so
anything you do here, the agent sees instantly, and vice versa.

**The flow:** Home tells you what needs attention. Chat with Smeaton or press
Agent buttons for the thinking work. You make the decisions. Instagram is the
last stop.
"""
)

st.subheader("Your weekly routine")
st.markdown(
    """
| When | What | Where |
|---|---|---|
| **Friday** | Export the post CSV from Meta Business Suite → drag into **Score posts** → click Score | Score posts |
| **Friday** | Run **Weekly report** | Agent |
| **Anytime** | Spotted a good post idea? Capture it (30 seconds) | Ideas |
| **Monday** | Run **Trend sweep**, then **Generate ideas** (or ask in Chat) | Agent / Chat |
| **Monday** | Approve/kill backlog ideas - approval auto-builds the production brief | Ideas |
| **Monday** | Run **Plan week**; confirm the proposal in Claude Code | Agent |
| **Post days** | Open the brief, make the thing, post it, hit **Mark posted** | Home → Ideas / Schedule |
"""
)

st.subheader("What each page does")
with st.expander("Home - your pre-Instagram ritual"):
    st.markdown(
        """
- **Needs you**: decisions waiting (idea approvals, proposed schedules, stale trends).
- **Hot right now**: newest open trends.
- **Going out this week**: scheduled posts with brief-ready badges.
- Clear this page top to bottom, then go create.
"""
    )
with st.expander("Chat - talk to the agent"):
    st.markdown(
        """
- Ask anything about your data ("which venue converts followers best?") or
  tell it to do things ("generate 3 reel ideas for Heyday").
- Ask about PubCam's posting style or a caption and it grounds the answer
  in real top-performing captions (`scripts/db.py voice-sample`), not a
  guess - CLAUDE.md Section 2 is still a TODO for the real guidelines, so
  this is the honest stand-in until then.
- It reads and writes the same database as everything else. Replies can take
  a couple of minutes when it has to dig.
- It won't approve ideas or commit schedules - those stay yours.
"""
    )
with st.expander("Post builder - rough idea in, finished carousel out"):
    st.markdown(
        """
- Type a basic idea ("cheapest parmas in the gong"), pick the venue fit,
  hit build. You get the full PubCam-layout carousel: SAVE-THIS hook
  cover, one item per slide, the screenshot-and-send payoff slide, outro,
  and a caption draft.
- Want a different layout? Open "Copy a specific post structure", drop in
  an example post (image and/or link) and describe the structure - a Q&A,
  a ranked countdown, a this-or-that, whatever it is - and it builds to
  that instead. The agent never analyses the image, only your
  description, so be specific. Leave it empty for the proven default.
- It lands in Ideas (backlog) with the brief attached; approve it there
  to queue it for scheduling.
- Unverifiable facts come back as [CHECK] items - tick them off before
  posting.
- Hit **Render carousel images** (here or on any past build) for actual
  1080x1350 PNGs in PubCam's real carousel style - photo, dark scrim,
  script signature. Free, instant, no agent call.
- Photos come from `assets/venue_photos/` - drop real shots in there
  (subfolders per venue, or descriptive filenames) and it picks the right
  one for each slide automatically. Nothing matching yet? It renders on a
  placeholder with a note on what to shoot, and upgrades the moment a
  photo turns up in the library - no re-typing anything.
"""
    )
with st.expander("Reel builder - reference reel in, PubCam script out"):
    st.markdown(
        """
- Drop a video file and/or a link, plus a note on what you actually want
  copied (the hook, the pacing, a specific mechanic) - be specific, since
  the agent works from your note, not the video itself (no vision step).
- Get back a script in that style: hooks, shot list with text overlays,
  caption. Lands in Ideas as backlog with its brief attached.
- No trending sound gets named unless your note or link actually said
  so - otherwise it's flagged [CHECK].
- The reference library below keeps every saved reel so you can build
  from it later, or just browse for inspiration.
"""
    )
with st.expander("Dashboard - how did our content perform?"):
    st.markdown(
        """
- Trend line of every scored post with a 5-post rolling average.
- Insights computed live from your numbers; only **pubcam.au** posts get
  scores (partner-account posts appear under *Excluded posts*).
"""
    )
with st.expander("Score posts - feed in fresh numbers"):
    st.markdown(
        """
1. Meta Business Suite: **Insights → Content → Export → CSV**.
2. Drag the file into the upload box, click **Score newest CSV**.
Re-scoring the same file is safe; posts under 7 days old are held back.
"""
    )
with st.expander("Ideas - the backlog that feeds everything"):
    st.markdown(
        """
- Capture anything worth trying. **Approve** triggers an automatic
  production brief (hooks, shot list/slide layout, caption, fact-check
  list) within a few minutes. **Kill** archives.
- Facts (prices, dates) flagged in briefs must be checked before posting.
"""
    )
with st.expander("Trends - what's working out in the wild"):
    st.markdown(
        """
- Sweep results with source links. Open trends feed *Generate ideas*;
  mark one acted to retire it.
"""
    )
with st.expander("Schedule - what's going out and when"):
    st.markdown(
        """
- The committed week. **Mark posted** after publishing so reports stay honest.
- Ask Claude Code to `/sync-drive` to share with Jack and Dakota.
"""
    )
with st.expander("Strategy log - what we believe and why"):
    st.markdown("- Decisions with evidence. The form refuses hunches.")
with st.expander("Agent - one-click agent runs"):
    st.markdown(
        """
- Trend sweep, Generate ideas, Weekly report, Plan week (dry run).
- Each takes 2-5 minutes, uses your Claude subscription, and never
  approves or publishes anything.
"""
    )

st.subheader("What the numbers mean")
st.markdown(
    """
| Term | Meaning |
|---|---|
| **Weighted score** | Engagement weighted by value - share (x5) and follow (x6) beat like (x1) - divided by reach. How hard the post worked per person who saw it. |
| **Percentile** | Rank against all scored PubCam posts. 90 = beat 90% of them. |
| **Rating** | The percentile as a grade: A+ (top 10%) down to D (bottom 25%). |
| **Excluded** | Partner-account post with limited insights - raw numbers only, never compared against weighted scores. |
"""
)
