import streamlit as st
from datetime import datetime

from baseline_engine import (
    list_baselines,
    load_project_baseline,
    delete_project_baseline,
)

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def _format_time(ts: str):
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts


# -------------------------------------------------
# BASELINE OVERVIEW DASHBOARD
# -------------------------------------------------
def render_baseline_tracker_dashboard():
    st.markdown("## 📊 Baseline Overview Dashboard")
    st.markdown(
        "Manage **all saved baselines per project**. "
        "View baseline history, inspect failures, and securely delete baselines."
    )

    st.markdown("---")

    admin_key = st.text_input(
        "🔐 Admin Key (required only for delete)",
        type="password",
    )

    projects = list_baselines()

    if not projects:
        st.info("ℹ️ No baselines have been saved yet.")
        return

    # -------------------------------------------------
    # PROJECT LOOP
    # -------------------------------------------------
    for project, baselines in projects.items():
        if not baselines:
            continue

        latest = baselines[0]

        with st.expander(
            f"📁 {project} — {len(baselines)} baseline(s) "
            f"| Latest: {_format_time(latest['created_at'])}",
            expanded=False,
        ):
            st.markdown(
                f"**Latest Baseline:** {latest['label']}  \n"
                f"**Created:** {_format_time(latest['created_at'])}  \n"
                f"**Failures:** {latest['failure_count']}"
            )

            st.markdown("---")

            # -------------------------------------------------
            # BASELINE LIST
            # -------------------------------------------------
            for baseline in baselines:
                cols = st.columns([4, 2, 2, 1])

                with cols[0]:
                    st.markdown(
                        f"**{baseline['label']}**  \n"
                        f"🕒 {_format_time(baseline['created_at'])}"
                    )

                with cols[1]:
                    st.metric("Failures", baseline["failure_count"])

                with cols[2]:
                    if st.button(
                        "👁️ View",
                        key=f"view_{project}_{baseline['id']}",
                    ):
                        data = load_project_baseline(project, baseline["id"])
                        st.json(data, expanded=False)

                with cols[3]:
                    if st.button(
                        "🗑️",
                        key=f"delete_{project}_{baseline['id']}",
                        help="Delete baseline (admin only)",
                    ):
                        if not admin_key:
                            st.error("❌ Admin key required to delete baseline")
                        else:
                            try:
                                delete_project_baseline(
                                    project,
                                    baseline["id"],
                                    admin_key,
                                )
                                st.success("✅ Baseline deleted")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
