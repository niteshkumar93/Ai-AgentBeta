import streamlit as st
import os
from datetime import datetime
from baseline_engine import (
    list_baselines,
    load_baseline,
    delete_baseline,
    get_baseline_stats,
    get_all_projects,
    _format_timestamp
)

BASELINE_DIR = "data/baseline"


# -------------------------------------------------
# HELPER
# -------------------------------------------------
def _format_time(ts: str):
    """Format timestamp string to readable format"""
    try:
        # Handle format like "20251223_142530"
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts


# -------------------------------------------------
# MAIN DASHBOARD RENDERER
# -------------------------------------------------
def render_baseline_tracker_dashboard():
    st.markdown("## 📊 Baseline Overview Dashboard")
    st.markdown(
        "This dashboard shows **all saved baselines per project**. "
        "You can review baseline history, compare baselines, and manage them securely."
    )

    st.markdown("---")

    # Admin key (required for delete operations)
    admin_key = st.text_input(
        "🔐 Admin Key (required for delete operations)",
        type="password",
        help="Admin key is required to delete baselines",
    )

    st.markdown("---")

    # Load all projects
    projects = get_all_projects()

    if not projects:
        st.info("ℹ️ No baselines have been saved yet. Upload and save XML reports in the main analyzer to create baselines.")
        return

    # -------------------------------------------------
    # PROJECT SUMMARY TABLE
    # -------------------------------------------------
    st.markdown("### 📋 Project Summary")
    
    summary_data = []
    for project in projects:
        stats = get_baseline_stats(project)
        baselines = list_baselines(project)
        latest = baselines[0] if baselines else None
        
        summary_data.append({
            "Project": project,
            "Baselines": stats["count"],
            "Latest": _format_time(latest["created_at"]) if latest else "-",
            "Latest Label": latest["label"] if latest else "-",
            "Total Failures": latest["failure_count"] if latest else 0
        })
    
    if summary_data:
        st.table(summary_data)

    st.markdown("---")

    # -------------------------------------------------
    # DETAILED PROJECT VIEW
    # -------------------------------------------------
    st.markdown("### 📁 Detailed Baseline Management")

    for project in projects:
        baselines = list_baselines(project)

        if not baselines:
            continue

        stats = get_baseline_stats(project)
        latest = baselines[0]

        with st.expander(
            f"📂 {project} "
            f"— {stats['count']} baseline(s) "
            f"| Latest: {_format_time(latest['created_at'])}",
            expanded=False,
        ):
            # Project Statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Total Baselines", stats['count'])
            with col2:
                st.metric("🆕 Latest Failures", latest['failure_count'])
            with col3:
                st.metric("📅 Latest", _format_time(latest['created_at']))
            with col4:
                st.metric("📈 Total Tracked", stats['total_failures'])

            st.markdown("---")

            # -------------------------------------------------
            # BASELINE LIST
            # -------------------------------------------------
            st.markdown("#### 📝 All Baselines")
            
            for idx, baseline in enumerate(baselines):
                # Color code based on position
                if idx == 0:
                    label_color = "🟢"  # Latest
                elif idx == len(baselines) - 1:
                    label_color = "🔴"  # Oldest
                else:
                    label_color = "🟡"  # Middle

                cols = st.columns([4, 2, 2, 1, 1])

                with cols[0]:
                    st.markdown(
                        f"{label_color} **{baseline['label']}**  \n"
                        f"🕒 {_format_time(baseline['created_at'])}  \n"
                        f"🆔 `{baseline['id']}`"
                    )

                with cols[1]:
                    st.metric(
                        "Failures",
                        baseline["failure_count"],
                    )

                with cols[2]:
                    badge = "Latest" if idx == 0 else f"#{idx + 1}"
                    st.info(badge)

                with cols[3]:
                    # View button
                    if st.button(
                        "👁️",
                        key=f"view_{project}_{baseline['id']}",
                        help="View baseline details",
                    ):
                        st.session_state[f"show_baseline_{project}_{baseline['id']}"] = True

                with cols[4]:
                    # Delete button
                    if st.button(
                        "🗑️",
                        key=f"delete_{project}_{baseline['id']}",
                        help="Delete baseline (admin only)",
                    ):
                        if not admin_key:
                            st.error("❌ Admin key required to delete baseline")
                        else:
                            # Check admin key
                            expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
                            if admin_key == expected_key:
                                success = delete_baseline(project, baseline["id"])
                                if success:
                                    st.success("✅ Baseline deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to delete baseline")
                            else:
                                st.error("❌ Invalid admin key")

                # Show baseline details if requested
                if st.session_state.get(f"show_baseline_{project}_{baseline['id']}", False):
                    with st.container():
                        st.markdown("##### 📄 Baseline Details")
                        
                        # Metadata
                        st.json({
                            "ID": baseline['id'],
                            "Project": baseline['project'],
                            "Label": baseline['label'],
                            "Created At": _format_time(baseline['created_at']),
                            "Failure Count": baseline['failure_count']
                        })
                        
                        # Failures
                        if baseline.get('failures'):
                            st.markdown("##### 🔴 Failures")
                            
                            # Create a searchable/filterable view
                            search = st.text_input(
                                "🔍 Search failures", 
                                key=f"search_{project}_{baseline['id']}"
                            )
                            
                            filtered_failures = baseline['failures']
                            if search:
                                filtered_failures = [
                                    f for f in baseline['failures']
                                    if search.lower() in str(f).lower()
                                ]
                            
                            st.caption(f"Showing {len(filtered_failures)} of {len(baseline['failures'])} failures")
                            
                            for i, failure in enumerate(filtered_failures[:20]):  # Limit to first 20
                                with st.expander(f"❌ {i+1}. {failure.get('testcase', 'Unknown')}"):
                                    st.write("**Test Case:**", failure.get('testcase', 'Unknown'))
                                    st.write("**Error:**", failure.get('error', 'Unknown'))
                                    
                                    if 'error_details' in failure:
                                        with st.expander("📋 Error Details"):
                                            st.code(failure['error_details'], language="text")
                                    
                                    if 'stack_trace' in failure:
                                        with st.expander("🔍 Stack Trace"):
                                            st.code(failure['stack_trace'], language="text")
                            
                            if len(filtered_failures) > 20:
                                st.info(f"ℹ️ Showing first 20 of {len(filtered_failures)} failures")
                        
                        # Close button
                        if st.button("❌ Close", key=f"close_{project}_{baseline['id']}"):
                            st.session_state[f"show_baseline_{project}_{baseline['id']}"] = False
                            st.rerun()

                st.markdown("")

            st.markdown("---")
            
            # -------------------------------------------------
            # COMPARISON FEATURE
            # -------------------------------------------------
            st.markdown("#### 🔄 Compare Baselines")
            
            if len(baselines) >= 2:
                col1, col2 = st.columns(2)
                
                with col1:
                    baseline1_id = st.selectbox(
                        "Select First Baseline",
                        options=[b['id'] for b in baselines],
                        format_func=lambda x: f"{[b for b in baselines if b['id'] == x][0]['label']} ({_format_time([b for b in baselines if b['id'] == x][0]['created_at'])})",
                        key=f"compare1_{project}"
                    )
                
                with col2:
                    baseline2_id = st.selectbox(
                        "Select Second Baseline",
                        options=[b['id'] for b in baselines if b['id'] != baseline1_id],
                        format_func=lambda x: f"{[b for b in baselines if b['id'] == x][0]['label']} ({_format_time([b for b in baselines if b['id'] == x][0]['created_at'])})",
                        key=f"compare2_{project}"
                    )
                
                if st.button("📊 Compare", key=f"compare_btn_{project}"):
                    baseline1 = load_baseline(project, baseline1_id)
                    baseline2 = load_baseline(project, baseline2_id)
                    
                    if baseline1 and baseline2:
                        st.markdown("##### Comparison Results")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(
                                f"{baseline1['label']} Failures",
                                baseline1['failure_count']
                            )
                        with col2:
                            delta = baseline2['failure_count'] - baseline1['failure_count']
                            st.metric(
                                f"{baseline2['label']} Failures",
                                baseline2['failure_count'],
                                delta=delta
                            )
                        with col3:
                            if delta > 0:
                                st.error(f"📈 +{delta} more failures")
                            elif delta < 0:
                                st.success(f"📉 {abs(delta)} fewer failures")
                            else:
                                st.info("➡️ Same number of failures")
                        
                        # Find new and resolved failures
                        baseline1_keys = {
                            f"{f.get('testcase', '')}|{f.get('error', '')}"
                            for f in baseline1.get('failures', [])
                        }
                        baseline2_keys = {
                            f"{f.get('testcase', '')}|{f.get('error', '')}"
                            for f in baseline2.get('failures', [])
                        }
                        
                        new_in_2 = baseline2_keys - baseline1_keys
                        resolved_in_2 = baseline1_keys - baseline2_keys
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("🆕 New Failures", len(new_in_2))
                        with col2:
                            st.metric("✅ Resolved Failures", len(resolved_in_2))
            else:
                st.info("ℹ️ At least 2 baselines required for comparison")


# -------------------------------------------------
# QUICK STATS WIDGET (Optional)
# -------------------------------------------------
def render_baseline_stats_widget():
    """Render a quick stats widget for the sidebar or main page"""
    projects = get_all_projects()
    
    if not projects:
        return
    
    total_baselines = sum(len(list_baselines(p)) for p in projects)
    total_projects = len(projects)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📁 Projects", total_projects)
    with col2:
        st.metric("📊 Total Baselines", total_baselines)