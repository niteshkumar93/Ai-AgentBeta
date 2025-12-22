import streamlit as st
from baseline_engine import (
    list_baselines,
    get_latest_baseline,
    delete_baseline,
    get_baseline_stats,
)

import streamlit as st
import os
import json

BASELINE_DIR = "data/baseline"

def render_baseline_tracker_dashboard():
    st.markdown("## 📊 Baseline Overview")

    if not os.path.exists(BASELINE_DIR):
        st.info("No baselines found.")
        return

    rows = []
    for file in os.listdir(BASELINE_DIR):
        if file.endswith(".json"):
            project = file.replace(".json", "")
            with open(os.path.join(BASELINE_DIR, file)) as f:
                data = json.load(f)
            rows.append({
                "Project": project,
                "Baselines": len(data),
                "Latest Label": data[0]["label"] if data else "-"
            })

    st.table(rows)

# -------------------------------------------------
# HELPER
# -------------------------------------------------
def _format_time(ts: str):
    try:
        return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts


# -------------------------------------------------
# MAIN DASHBOARD RENDERER
# -------------------------------------------------
def render_baseline_tracker_dashboard():
    st.markdown("## 📊 Baseline Overview Dashboard")
    st.markdown(
        "This dashboard shows **all saved baselines per project**. "
        "You can review baseline history and manage them securely."
    )

    st.markdown("---")

    # Admin key (optional – only needed for delete)
    admin_key = st.text_input(
        "🔐 Admin Key (required only for delete)",
        type="password",
        help="Admin key is required only to delete baselines",
    )

    # Load all project folders
    projects = []
    try:
        from baseline_engine import PROJECT_BASELINE_ROOT
        import os

        if os.path.exists(PROJECT_BASELINE_ROOT):
            projects = sorted(
                d for d in os.listdir(PROJECT_BASELINE_ROOT)
                if os.path.isdir(os.path.join(PROJECT_BASELINE_ROOT, d))
            )
    except Exception as e:
        st.error(f"Failed to load baselines: {e}")
        return

    if not projects:
        st.info("ℹ️ No baselines have been saved yet.")
        return

    # -------------------------------------------------
    # PROJECT LOOP
    # -------------------------------------------------
    for project in projects:
        baselines = list_baselines(project)

        if not baselines:
            continue

        latest = baselines[0]

        with st.expander(
            f"📁 {project} "
            f"— {len(baselines)} baseline(s) "
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
            for idx, baseline in enumerate(baselines):
                cols = st.columns([4, 2, 2, 1])

                with cols[0]:
                    st.markdown(
                        f"**{baseline['label']}**  \n"
                        f"🕒 {_format_time(baseline['created_at'])}"
                    )

                with cols[1]:
                    st.metric(
                        "Failures",
                        baseline["failure_count"],
                    )

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

            st.markdown("")

