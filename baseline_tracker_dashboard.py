import streamlit as st
import os
from datetime import datetime

# Import both baseline engines
from baseline_engine import (
    list_baselines as list_provar_baselines,
    load_baseline as load_provar_baseline,
    delete_baseline as delete_provar_baseline,
    get_baseline_stats as get_provar_stats,
    get_all_projects as get_provar_projects,
    _format_timestamp as format_provar_time
)

try:
    from automation_api_baseline_engine import (
        list_baselines as list_api_baselines,
        load_baseline as load_api_baseline,
        delete_baseline as delete_api_baseline,
        get_baseline_stats as get_api_stats,
        get_all_projects as get_api_projects,
        _format_timestamp as format_api_time
    )
    API_ENGINE_AVAILABLE = True
except ImportError:
    API_ENGINE_AVAILABLE = False


# -------------------------------------------------
# HELPER
# -------------------------------------------------
def _format_time(ts: str):
    """Format timestamp string to readable format"""
    try:
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts


# -------------------------------------------------
# RENDER BASELINE SECTION (GENERIC)
# -------------------------------------------------
def render_baseline_section(
    project: str,
    baselines: list,
    stats: dict,
    admin_key: str,
    load_func,
    delete_func,
    section_key: str
):
    """Render baseline section for a project (works for both Provar and AutomationAPI)"""
    
    if not baselines:
        return
    
    latest = baselines[0]
    
    with st.expander(
        f"📂 {project} "
        f"– {stats['count']} baseline(s) "
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

        # Baseline List
        st.markdown("#### 📋 All Baselines")
        
        for idx, baseline in enumerate(baselines):
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
                st.metric("Failures", baseline["failure_count"])

            with cols[2]:
                badge = "Latest" if idx == 0 else f"#{idx + 1}"
                st.info(badge)

            with cols[3]:
                if st.button(
                    "👁️",
                    key=f"view_{section_key}_{project}_{baseline['id']}",
                    help="View baseline details",
                ):
                    st.session_state[f"show_{section_key}_{project}_{baseline['id']}"] = True

            with cols[4]:
                if st.button(
                    "🗑️",
                    key=f"delete_{section_key}_{project}_{baseline['id']}",
                    help="Delete baseline (admin only)",
                ):
                    if not admin_key:
                        st.error("❌ Admin key required to delete baseline")
                    else:
                        expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
                        if admin_key == expected_key:
                            success = delete_func(project, baseline["id"])
                            if success:
                                st.success("✅ Baseline deleted successfully!")
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete baseline")
                        else:
                            st.error("❌ Invalid admin key")

            # Show baseline details if requested
            if st.session_state.get(f"show_{section_key}_{project}_{baseline['id']}", False):
                with st.container():
                    st.markdown("##### 📄 Baseline Details")
                    
                    st.json({
                        "ID": baseline['id'],
                        "Project": baseline['project'],
                        "Label": baseline['label'],
                        "Created At": _format_time(baseline['created_at']),
                        "Failure Count": baseline['failure_count']
                    })
                    
                    if baseline.get('failures'):
                        st.markdown("##### 🔴 Failures")
                        
                        search = st.text_input(
                            "🔍 Search failures", 
                            key=f"search_{section_key}_{project}_{baseline['id']}"
                        )
                        
                        filtered_failures = baseline['failures']
                        if search:
                            filtered_failures = [
                                f for f in baseline['failures']
                                if search.lower() in str(f).lower()
                            ]
                        
                        st.caption(f"Showing {len(filtered_failures)} of {len(baseline['failures'])} failures")
                        
                        for i, failure in enumerate(filtered_failures[:20]):
                            with st.expander(f"❌ {i+1}. {failure.get('testcase', failure.get('test_name', 'Unknown'))}"):
                                # Handle both Provar and AutomationAPI formats
                                if 'testcase' in failure:  # Provar
                                    st.write("**Test Case:**", failure.get('testcase', 'Unknown'))
                                    st.write("**Error:**", failure.get('error', 'Unknown'))
                                else:  # AutomationAPI
                                    st.write("**Test Name:**", failure.get('test_name', 'Unknown'))
                                    st.write("**Spec File:**", failure.get('spec_file', 'Unknown'))
                                    st.write("**Error:**", failure.get('error_summary', 'Unknown'))
                                
                                if 'details' in failure or 'error_details' in failure:
                                    with st.expander("📋 Error Details"):
                                        st.code(failure.get('details', failure.get('error_details', '')), language="text")
                        
                        if len(filtered_failures) > 20:
                            st.info(f"ℹ️ Showing first 20 of {len(filtered_failures)} failures")
                    
                    if st.button("❌ Close", key=f"close_{section_key}_{project}_{baseline['id']}"):
                        st.session_state[f"show_{section_key}_{project}_{baseline['id']}"] = False
                        st.rerun()

            st.markdown("")

        st.markdown("---")
        
        # Comparison Feature
        st.markdown("#### 🔄 Compare Baselines")
        
        if len(baselines) >= 2:
            col1, col2 = st.columns(2)
            
            with col1:
                baseline1_id = st.selectbox(
                    "Select First Baseline",
                    options=[b['id'] for b in baselines],
                    format_func=lambda x: f"{[b for b in baselines if b['id'] == x][0]['label']} ({_format_time([b for b in baselines if b['id'] == x][0]['created_at'])})",
                    key=f"compare1_{section_key}_{project}"
                )
            
            with col2:
                baseline2_id = st.selectbox(
                    "Select Second Baseline",
                    options=[b['id'] for b in baselines if b['id'] != baseline1_id],
                    format_func=lambda x: f"{[b for b in baselines if b['id'] == x][0]['label']} ({_format_time([b for b in baselines if b['id'] == x][0]['created_at'])})",
                    key=f"compare2_{section_key}_{project}"
                )
            
            if st.button("📊 Compare", key=f"compare_btn_{section_key}_{project}"):
                baseline1 = load_func(project, baseline1_id)
                baseline2 = load_func(project, baseline2_id)
                
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
                    baseline1_keys = set()
                    baseline2_keys = set()
                    
                    for f in baseline1.get('failures', []):
                        if 'testcase' in f:  # Provar
                            key = f"{f.get('testcase', '')}|{f.get('error', '')}"
                        else:  # AutomationAPI
                            key = f"{f.get('spec_file', '')}|{f.get('test_name', '')}|{f.get('error_summary', '')}"
                        baseline1_keys.add(key)
                    
                    for f in baseline2.get('failures', []):
                        if 'testcase' in f:  # Provar
                            key = f"{f.get('testcase', '')}|{f.get('error', '')}"
                        else:  # AutomationAPI
                            key = f"{f.get('spec_file', '')}|{f.get('test_name', '')}|{f.get('error_summary', '')}"
                        baseline2_keys.add(key)
                    
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
# MAIN DASHBOARD RENDERER
# -------------------------------------------------
def render_baseline_tracker_dashboard():
    st.markdown("## 📊 Baseline Overview Dashboard")
    st.markdown(
        "This dashboard shows **all saved baselines** for both **Provar** and **AutomationAPI** reports. "
        "You can review baseline history, compare baselines, and manage them securely."
    )

    st.markdown("---")

    # Admin key
    admin_key = st.text_input(
        "🔐 Admin Key (required for delete operations)",
        type="password",
        help="Admin key is required to delete baselines",
    )

    st.markdown("---")

    # Create tabs for Provar and AutomationAPI
    tabs = ["🔧 Provar Baselines"]
    if API_ENGINE_AVAILABLE:
        tabs.append("⚙️ AutomationAPI Baselines")
    
    tab_objects = st.tabs(tabs)

    # -------------------------------------------------
    # PROVAR BASELINES TAB
    # -------------------------------------------------
    with tab_objects[0]:
        st.markdown("### 📋 Provar Regression Test Baselines")
        
        provar_projects = get_provar_projects()
        
        if not provar_projects:
            st.info("ℹ️ No Provar baselines have been saved yet. Upload and save Provar XML reports to create baselines.")
        else:
            # Summary table
            st.markdown("#### 📊 Project Summary")
            
            summary_data = []
            for project in provar_projects:
                stats = get_provar_stats(project)
                baselines = list_provar_baselines(project)
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
            st.markdown("#### 🔍 Detailed Baseline Management")
            
            for project in provar_projects:
                baselines = list_provar_baselines(project)
                if baselines:
                    stats = get_provar_stats(project)
                    render_baseline_section(
                        project,
                        baselines,
                        stats,
                        admin_key,
                        load_provar_baseline,
                        delete_provar_baseline,
                        "provar"
                    )

    # -------------------------------------------------
    # AUTOMATIONAPI BASELINES TAB
    # -------------------------------------------------
    if API_ENGINE_AVAILABLE and len(tab_objects) > 1:
        with tab_objects[1]:
            st.markdown("### 📋 AutomationAPI Test Baselines")
            
            api_projects = get_api_projects()
            
            if not api_projects:
                st.info("ℹ️ No AutomationAPI baselines have been saved yet. Upload and save AutomationAPI XML reports to create baselines.")
            else:
                # Summary table
                st.markdown("#### 📊 Project Summary")
                
                summary_data = []
                for project in api_projects:
                    stats = get_api_stats(project)
                    baselines = list_api_baselines(project)
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
                st.markdown("#### 🔍 Detailed Baseline Management")
                
                for project in api_projects:
                    baselines = list_api_baselines(project)
                    if baselines:
                        stats = get_api_stats(project)
                        render_baseline_section(
                            project,
                            baselines,
                            stats,
                            admin_key,
                            load_api_baseline,
                            delete_api_baseline,
                            "api"
                        )