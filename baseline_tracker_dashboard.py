import streamlit as st
import os
from datetime import datetime

from baseline_engine import (
    list_baselines,
    load_project_baseline,
    delete_project_baseline,
    get_baseline_stats,
    PROJECT_BASELINE_ROOT,
)


def _format_time(ts: str):
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return ts


def render_baseline_tracker_dashboard():
    st.markdown("## 📊 Baseline Overview Dashboard")
    st.markdown(
        "View all saved baselines per project. "
        "Only admins can delete baselines."
    )

    st.markdown("---")

    admin_key = st.text_input(
        "🔐 Admin Key (required for delete)",
        type="password",
    )

    if not os.path.exists(PROJECT_BASELINE_ROOT):
        st.info("No baselines found.")
        return

    projects = sorted(
        d for d in os.listdir(PROJECT_BASELINE_ROOT)
        if os.path.isdir(os.path.join(PROJECT_BASELINE_ROOT, d))
    )

    if not projects:
        st.info("ℹ️ No baselines saved yet.")
        return

    for project in projects:
        baselines = list_baselines(project)

        with st.expander(
            f"📁 {project} — {len(baselines)} baseline(s)",
            expanded=False,
        ):
            for b in baselines:
                cols = st.columns([4, 2, 1])

                with cols[0]:
                    st.markdown(
                        f"**{b['label']}**  \n"
                        f"🕒 {_format_time(b['created_at'])}"
                    )

                with cols[1]:
                    st.metric("Failures", b["failure_count"])

                with cols[2]:
                    if st.button(
                        "🗑️",
                        key=f"delete_{project}_{b['id']}",
                    ):
                        if not admin_key:
                            st.error("Admin key required")
                        else:
                            delete_project_baseline(project, b["id"], admin_key)
                            st.success("Baseline deleted")
                            st.rerun()
