import streamlit as st

# Absolute imports — `streamlit run app.py` invokes this file as a top-level
# script, so `from . import ...` raises
# "attempted relative import with no known parent package".
from bench.dashboard import leaderboard, run_detail, about


def main():
    pages = [
        st.Page(leaderboard.render, title="Leaderboard", default=True),
        st.Page(run_detail.render,  title="Run detail"),
        st.Page(about.render,       title="About"),
    ]
    st.navigation(pages).run()


# Streamlit executes the module body directly; no __name__ == "__main__" gate.
main()
