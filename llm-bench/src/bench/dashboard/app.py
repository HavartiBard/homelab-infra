import streamlit as st

# Absolute imports — `streamlit run app.py` invokes this file as a top-level
# script, so `from . import ...` raises
# "attempted relative import with no known parent package".
from bench.dashboard import leaderboard, run_detail, about


def main():
    # Explicit url_path on each Page — without it, Streamlit infers the URL
    # pathname from the callable's __name__. All three render functions are
    # named `render`, which would collide ("Multiple Pages specified with URL
    # pathname render").
    pages = [
        st.Page(leaderboard.render, title="Leaderboard", url_path="leaderboard", default=True),
        st.Page(run_detail.render,  title="Run detail",  url_path="run"),
        st.Page(about.render,       title="About",       url_path="about"),
    ]
    st.navigation(pages).run()


# Streamlit executes the module body directly; no __name__ == "__main__" gate.
main()
