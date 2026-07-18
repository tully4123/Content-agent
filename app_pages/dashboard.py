import altair as alt
import pandas as pd
import streamlit as st

from app_lib import FORMAT_COLORS, INK_SECONDARY, query


def compute_insights(scored: pd.DataFrame) -> list[str]:
    """Data-derived observations, honest about sample sizes. No invented claims."""
    insights = []
    df = scored.copy()
    df["posted_dt"] = pd.to_datetime(df["posted_at"], errors="coerce")
    df = df.sort_values("posted_dt")

    fmt = df.groupby("format")["weighted_score"].agg(["mean", "count"])
    if len(fmt) > 1:
        top = fmt["mean"].idxmax()
        ratio = fmt["mean"].max() / fmt["mean"].drop(top).max()
        insights.append(
            f"**{top.capitalize()}s lead**: avg score {fmt['mean'].max():.0f} vs "
            f"{fmt['mean'].drop(top).max():.0f} for the next format ({ratio:.1f}x) - "
            f"across {int(fmt['count'][top])} {top}s."
        )

    df["save_rate"] = df["saves"] / df["reach"] * 100
    top_saver = df.loc[df["save_rate"].idxmax()]
    insights.append(
        f"**Most saved**: \"{str(top_saver['caption'])[:60]}...\" - "
        f"{top_saver['save_rate']:.1f}% of reached accounts saved it. Save-heavy guides "
        "are your DM-share engine."
    )

    if len(df) >= 10:
        recent = df.tail(5)["weighted_score"].mean()
        earlier = df.iloc[:-5]["weighted_score"].mean()
        direction = "up" if recent > earlier else "down"
        insights.append(
            f"**Momentum {direction}**: last 5 posts average {recent:.0f} vs {earlier:.0f} "
            f"for everything before - {'keep doing what changed' if direction == 'up' else 'worth a look at what changed'}."
        )

    followers = df.loc[df["follows"].idxmax()]
    insights.append(
        f"**Best follower converter**: \"{str(followers['caption'])[:60]}...\" "
        f"brought {int(followers['follows'])} new follows from {int(followers['reach']):,} reach."
    )
    return insights


scored = query(
    "SELECT post_id, venue, format, caption, posted_at, reach, likes, comments,"
    "       saves, shares, follows, weighted_score, percentile, rating"
    " FROM posts WHERE scoring_excluded = 0 AND weighted_score IS NOT NULL"
)
excluded_n = query("SELECT COUNT(*) AS n FROM posts WHERE scoring_excluded = 1")["n"][0]

if scored.empty:
    st.info("No scored posts yet. Go to **Score posts** and load a Meta Business Suite CSV.")
    st.stop()

scored["posted_dt"] = pd.to_datetime(scored["posted_at"], errors="coerce")
chrono = scored.sort_values("posted_dt")
score_series = chrono["weighted_score"].round(1).tolist()
reach_series = chrono["reach"].tolist()

with st.container(horizontal=True):
    st.metric("Scored posts", len(scored), border=True)
    st.metric("Average score", f"{scored['weighted_score'].mean():.1f}", border=True,
              chart_data=score_series, chart_type="line")
    best = scored.loc[scored["weighted_score"].idxmax()]
    st.metric("Best score", f"{best['weighted_score']:.1f}", border=True,
              help=str(best["caption"])[:120])
    st.metric("A-grade posts", int(scored["rating"].isin(["A", "A+"]).sum()), border=True)
    st.metric("Total reach", f"{int(scored['reach'].sum()):,}", border=True,
              chart_data=reach_series, chart_type="bar")

st.caption(
    f"pubcam.au posts only - {excluded_n} partner-account posts are excluded from scoring "
    "(limited insights; their Reach/Saves aren't comparable). See CLAUDE.md Section 4."
)

st.subheader("Score over time")
pick_formats = st.pills(
    "Formats", sorted(scored["format"].unique()),
    default=sorted(scored["format"].unique()), selection_mode="multi",
    label_visibility="collapsed",
)
ts = chrono[chrono["format"].isin(pick_formats or [])].copy()
if ts.empty:
    st.caption("Pick at least one format.")
else:
    ts["rolling"] = ts["weighted_score"].rolling(5, min_periods=1).mean()
    ts["caption_short"] = ts["caption"].astype(str).str.slice(0, 70)
    domain_ts = [f for f in FORMAT_COLORS if f in set(ts["format"])]
    points = (
        alt.Chart(ts)
        .mark_circle(size=90)
        .encode(
            x=alt.X("posted_dt:T", title=None),
            y=alt.Y("weighted_score:Q", title="Weighted score"),
            color=alt.Color(
                "format:N", title="Format",
                scale=alt.Scale(domain=domain_ts, range=[FORMAT_COLORS[f] for f in domain_ts]),
            ),
            tooltip=[
                alt.Tooltip("posted_dt:T", title="Posted"),
                alt.Tooltip("caption_short:N", title="Caption"),
                alt.Tooltip("format:N", title="Format"),
                alt.Tooltip("weighted_score:Q", title="Score", format=".1f"),
                alt.Tooltip("rating:N", title="Rating"),
                alt.Tooltip("reach:Q", title="Reach", format=","),
                alt.Tooltip("saves:Q", title="Saves"),
                alt.Tooltip("shares:Q", title="Shares"),
            ],
        )
    )
    trend = (
        alt.Chart(ts)
        .mark_line(strokeWidth=2, color=INK_SECONDARY, strokeDash=[6, 3])
        .encode(x="posted_dt:T", y="rolling:Q",
                tooltip=[alt.Tooltip("rolling:Q", title="5-post rolling avg", format=".1f")])
    )
    st.altair_chart((points + trend).properties(height=320).interactive(), width="stretch")
    st.caption("Dots = individual posts (hover for detail). Dashed line = 5-post rolling average - the trend line.")

left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown("**:material/insights: What the data says**")
    for line in compute_insights(scored):
        st.markdown(f"- {line}")
    st.caption(f"Computed live from your {len(scored)} scored posts - small sample, treat as signals not laws.")

with right, st.container(border=True):
    st.markdown("**:material/tips_and_updates: Tips right now**")
    open_trends = query("SELECT description FROM trends WHERE acted_on = 0 ORDER BY id DESC LIMIT 3")
    if not open_trends.empty:
        st.markdown("- **Open trends waiting**: " + "; ".join(
            d.split(":")[0].strip("'\" ") for d in open_trends["description"]
        ) + " - press *Generate ideas* on the Agent page to turn them into posts.")
    backlog_n = query("SELECT COUNT(*) AS n FROM ideas WHERE status = 'backlog'")["n"][0]
    if backlog_n:
        st.markdown(f"- **{backlog_n} idea(s) in the backlog** need an approve/kill decision on the Ideas page.")
    st.markdown("- **Working theory** (from CLAUDE.md, verify with more data): multi-venue guide "
                "carousels outperform single-venue promo; save-optimised posts travel via DMs.")
    st.markdown("- **Friday habit**: fresh CSV in, score, then check this page's trend line.")

st.subheader("Average score by format")
by_format = (
    scored.groupby("format", as_index=False)
    .agg(avg_score=("weighted_score", "mean"), posts=("post_id", "count"))
)
by_format["avg_score"] = by_format["avg_score"].round(1)
by_format["label"] = by_format.apply(lambda r: f"{r.avg_score}  ({r.posts} posts)", axis=1)

domain = [f for f in FORMAT_COLORS if f in set(by_format["format"])]
bars = (
    alt.Chart(by_format)
    .mark_bar(cornerRadiusEnd=4, height=26)
    .encode(
        x=alt.X("avg_score:Q", title="Average weighted score", axis=alt.Axis(grid=True)),
        y=alt.Y("format:N", title=None, sort="-x"),
        color=alt.Color(
            "format:N",
            scale=alt.Scale(domain=domain, range=[FORMAT_COLORS[f] for f in domain]),
            legend=None,  # single dimension, direct-labeled - the axis names each bar
        ),
        tooltip=["format", "avg_score", "posts"],
    )
)
labels = (
    alt.Chart(by_format)
    .mark_text(align="left", dx=6, color=INK_SECONDARY)
    .encode(x="avg_score:Q", y=alt.Y("format:N", sort="-x"), text="label:N")
)
st.altair_chart((bars + labels).properties(height=40 * len(by_format) + 40), width="stretch")

st.subheader("All scored posts")
ratings = ["A+", "A", "B", "C", "D"]
pick = st.multiselect("Filter by rating", ratings, default=ratings)
table = scored[scored["rating"].isin(pick)].sort_values("weighted_score", ascending=False)
table = table[["rating", "format", "venue", "caption", "posted_at", "reach",
               "saves", "shares", "follows", "weighted_score", "percentile"]]
st.dataframe(table, width="stretch", hide_index=True)

with st.expander(f"Excluded posts ({excluded_n}) - partner accounts, raw numbers only"):
    ex = query(
        "SELECT account, venue, format, caption, posted_at, views, likes, comments, shares"
        " FROM posts WHERE scoring_excluded = 1 ORDER BY posted_at DESC"
    )
    st.dataframe(ex, width="stretch", hide_index=True)
    st.caption("Never compare these raw numbers against weighted scores - different measurement basis.")
