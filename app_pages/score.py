import subprocess
import sys

import streamlit as st

from app_lib import INBOX_DIR, REPO_ROOT, SCORE_SCRIPT

st.write(
    "Export the post-performance CSV from Meta Business Suite "
    "(Insights → Content → Export), upload it here, then score it."
)

uploaded = st.file_uploader("Drop the Meta Business Suite CSV here", type="csv")
if uploaded is not None:
    dest = INBOX_DIR / uploaded.name
    dest.write_bytes(uploaded.getvalue())
    st.success(f"Saved to inbox/{uploaded.name}")

csvs = sorted(INBOX_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
if not csvs:
    st.info("No CSVs in inbox/ yet.")
    st.stop()

newest = csvs[0]
st.write(f"Newest file in inbox: **{newest.name}**")
if st.button("Score newest CSV", type="primary", icon=":material/calculate:"):
    result = subprocess.run(
        [sys.executable, str(SCORE_SCRIPT)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode == 0:
        st.success("Scoring complete.")
    else:
        st.error("Scoring failed - output below.")
    st.code(result.stdout + result.stderr)
    st.page_link("app_pages/dashboard.py", label="See the results", icon=":material/analytics:")
