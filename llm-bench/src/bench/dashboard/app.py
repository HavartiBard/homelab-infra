import streamlit as st

from . import leaderboard, run_detail, about


def main():
    pages = [
        st.Page(leaderboard.render, title="Leaderboard", default=True),
        st.Page(run_detail.render,  title="Run detail"),
        st.Page(about.render,       title="About"),
    ]
    st.navigation(pages).run()


if __name__ == "__main__":
    main()
