"""
Fixed Baseline Tracker Dashboard - Reads from GitHub Storage
"""

import streamlit as st
import os
import json
from datetime import datetime
from typing import List, Dict, Optional


def _format_time(ts: str):
    """Format timestamp string to readable format"""
    try:
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts


def _parse_baseline_from_github(file_info: Dict, github_storage, platform: str) -> Optional[Dict]:
    """
    Load and parse a baseline file from GitHub
    
    Args:
        file_info: File metadata from GitHub
        github_storage: GitHubStorage instance
        platform: "provar" or "automation_api"
    
    Returns:
        Parsed baseline data or None
    """
    try:
        folder = f"baselines/{platform}"
        content = github_storage.load_baseline(file_info['name'], folder=folder)
        
        if content:
            data = json.loads(content)
            return data
        
        return None
    
    except Exception as e:
        print(f"Error parsing baseline {file_info['name']}: {e}")
        return None


def render_baseline_section(
    project: str,
    baselines: List[Dict],
    admin_key: str,
    github_storage,
    platform: str,
    section_key: str
):
    """Render baseline section for a project"""
    
    if not baselines:
        return
    
    latest = baselines[0]
    total_failures = sum(b.get('failure_count', 0) for b in baselines)
    
    with st.expander(
        f"📂 {project} "
        f"— {len(baselines)} baseline(s) "
        f"| Latest: {_format_time(latest.get('created_at', 'Unknown'))}",
        expanded=False,
    ):
        # Project Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Total Baselines", len(baselines))
        with col2:
            st.metric("🆕 Latest Failures", latest.get('failure_count', 0))
        with col3:
            st.metric("📅 Latest", _format_time(latest.get('created_at', 'Unknown')))
        with col4:
            st.metric("📈 Total Tracked", total_failures)

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
                    f"{label_color} **{baseline.get('label', 'Unknown')}**  \n"
                    f"🕒 {_format_time(baseline.get('created_at', 'Unknown'))}  \n"
                    f"🆔 `{baseline.get('id', 'Unknown')}`"
                )

            with cols[1]:
                st.metric("Failures", baseline.get("failure_count", 0))

            with cols[2]:
                badge = "Latest" if idx == 0 else f"#{idx + 1}"
                st.info(badge)

            with cols[3]:
                if st.button(
                    "👁️",
                    key=f"view_{section_key}_{project}_{baseline.get('id', idx)}",
                    help="View baseline details",
                ):
                    st.session_state[f"show_{section_key}_{project}_{baseline.get('id', idx)}"] = True

            with cols[4]:
                if st.button(
                    "🗑️",
                    key=f"delete_{section_key}_{project}_{baseline.get('id', idx)}",
                    help="Delete baseline (admin only)",
                ):
                    if not admin_key:
                        st.error("❌ Admin key required to delete baseline")
                    else:
                        expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
                        if admin_key == expected_key:
                            # Delete from GitHub
                            folder = f"baselines/{platform}"
                            filename = baseline.get('_filename', '')
                            
                            if filename:
                                success = github_storage.delete_baseline(filename, folder=folder)
                                if success:
                                    st.success("✅ Baseline deleted successfully!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to delete baseline")
                            else:
                                st.error("❌ Cannot determine filename")
                        else:
                            st.error("❌ Invalid admin key")

            # Show baseline details if requested
            if st.session_state.get(f"show_{section_key}_{project}_{baseline.get('id', idx)}", False):
                with st.container():
                    st.markdown("##### 📄 Baseline Details")
                    
                    st.json({
                        "ID": baseline.get('id', 'Unknown'),
                        "Project": baseline.get('project', 'Unknown'),
                        "Platform": baseline.get('platform', 'Unknown'),
                        "Label": baseline.get('label', 'Unknown'),
                        "Created At": _format_time(baseline.get('created_at', 'Unknown')),
                        "Failure Count": baseline.get('failure_count', 0)
                    })
                    
                    failures = baseline.get('failures', [])
                    if failures:
                        st.markdown("##### 🔴 Failures")
                        
                        search = st.text_input(
                            "🔍 Search failures", 
                            key=f"search_{section_key}_{project}_{baseline.get('id', idx)}"
                        )
                        
                        filtered_failures = failures
                        if search:
                            filtered_failures = [
                                f for f in failures
                                if search.lower() in str(f).lower()
                            ]
                        
                        st.caption(f"Showing {len(filtered_failures)} of {len(failures)} failures")
                        
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
                    
                    if st.button("❌ Close", key=f"close_{section_key}_{project}_{baseline.get('id', idx)}"):
                        st.session_state[f"show_{section_key}_{project}_{baseline.get('id', idx)}"] = False
                        st.rerun()

            st.markdown("")


def render_baseline_tracker_dashboard():
    """Main dashboard renderer - reads from GitHub"""
    
    st.markdown("## 📊 Baseline Overview Dashboard")
    st.markdown(
        "This dashboard shows **all saved baselines** for both **Provar** and **AutomationAPI** reports from GitHub. "
        "You can review baseline history, compare baselines, and manage them securely."
    )

    st.markdown("---")

    # Get GitHub storage instance from session state or app
    try:
        from storage.baseline_service import BaselineService
        from github_storage import GitHubStorage
        
        # Try to get from session state first
        if 'github_storage' not in st.session_state:
            github = GitHubStorage(
                token=st.secrets.get("GITHUB_TOKEN"),
                repo_owner=st.secrets.get("GITHUB_OWNER"),
                repo_name=st.secrets.get("GITHUB_REPO")
            )
            st.session_state.github_storage = github
        else:
            github = st.session_state.github_storage
        
        baseline_service = BaselineService(github)
    
    except Exception as e:
        st.error(f"❌ Failed to initialize GitHub storage: {str(e)}")
        st.info("💡 Make sure GitHub secrets are configured correctly in Streamlit")
        return

    # Admin key
    admin_key = st.text_input(
        "🔐 Admin Key (required for delete operations)",
        type="password",
        help="Admin key is required to delete baselines",
    )

    st.markdown("---")

    # Create tabs for Provar and AutomationAPI
    tab_objects = st.tabs(["🔧 Provar Baselines", "⚙️ AutomationAPI Baselines"])

    # -------------------------------------------------
    # PROVAR BASELINES TAB
    # -------------------------------------------------
    with tab_objects[0]:
        st.markdown("### 📋 Provar Regression Test Baselines")
        
        try:
            # Load from GitHub
            provar_files = github.list_baselines(folder="baselines/provar")
            
            if not provar_files:
                st.info("ℹ️ No Provar baselines have been saved yet. Upload and save Provar XML reports to create baselines.")
            else:
                # Group by project
                projects_data = {}
                
                for file_info in provar_files:
                    baseline_data = _parse_baseline_from_github(file_info, github, "provar")
                    
                    if baseline_data:
                        # Store filename for deletion
                        baseline_data['_filename'] = file_info['name']
                        
                        project = baseline_data.get('project', 'Unknown')
                        if project not in projects_data:
                            projects_data[project] = []
                        projects_data[project].append(baseline_data)
                
                if not projects_data:
                    st.warning("⚠️ Found baseline files but couldn't parse them")
                else:
                    # Summary table
                    st.markdown("#### 📊 Project Summary")
                    
                    summary_data = []
                    for project, baselines in projects_data.items():
                        # Sort by created_at
                        baselines_sorted = sorted(
                            baselines, 
                            key=lambda x: x.get('created_at', ''), 
                            reverse=True
                        )
                        
                        latest = baselines_sorted[0] if baselines_sorted else None
                        
                        summary_data.append({
                            "Project": project,
                            "Baselines": len(baselines),
                            "Latest": _format_time(latest.get("created_at", "Unknown")) if latest else "-",
                            "Latest Label": latest.get("label", "-") if latest else "-",
                            "Total Failures": latest.get("failure_count", 0) if latest else 0
                        })
                    
                    st.table(summary_data)
                    
                    st.markdown("---")
                    st.markdown("#### 🔍 Detailed Baseline Management")
                    
                    # Render each project
                    for project, baselines in projects_data.items():
                        # Sort by created_at (newest first)
                        baselines_sorted = sorted(
                            baselines, 
                            key=lambda x: x.get('created_at', ''), 
                            reverse=True
                        )
                        
                        render_baseline_section(
                            project,
                            baselines_sorted,
                            admin_key,
                            github,
                            "provar",
                            "provar"
                        )
        
        except Exception as e:
            st.error(f"❌ Error loading Provar baselines: {str(e)}")
            import traceback
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())

    # -------------------------------------------------
    # AUTOMATIONAPI BASELINES TAB
    # -------------------------------------------------
    with tab_objects[1]:
        st.markdown("### 📋 AutomationAPI Test Baselines")
        
        try:
            # Load from GitHub
            api_files = github.list_baselines(folder="baselines/automation_api")
            
            if not api_files:
                st.info("ℹ️ No AutomationAPI baselines have been saved yet. Upload and save AutomationAPI XML reports to create baselines.")
            else:
                # Group by project
                projects_data = {}
                
                for file_info in api_files:
                    baseline_data = _parse_baseline_from_github(file_info, github, "automation_api")
                    
                    if baseline_data:
                        # Store filename for deletion
                        baseline_data['_filename'] = file_info['name']
                        
                        project = baseline_data.get('project', 'Unknown')
                        if project not in projects_data:
                            projects_data[project] = []
                        projects_data[project].append(baseline_data)
                
                if not projects_data:
                    st.warning("⚠️ Found baseline files but couldn't parse them")
                else:
                    # Summary table
                    st.markdown("#### 📊 Project Summary")
                    
                    summary_data = []
                    for project, baselines in projects_data.items():
                        # Sort by created_at
                        baselines_sorted = sorted(
                            baselines, 
                            key=lambda x: x.get('created_at', ''), 
                            reverse=True
                        )
                        
                        latest = baselines_sorted[0] if baselines_sorted else None
                        
                        summary_data.append({
                            "Project": project,
                            "Baselines": len(baselines),
                            "Latest": _format_time(latest.get("created_at", "Unknown")) if latest else "-",
                            "Latest Label": latest.get("label", "-") if latest else "-",
                            "Total Failures": latest.get("failure_count", 0) if latest else 0
                        })
                    
                    st.table(summary_data)
                    
                    st.markdown("---")
                    st.markdown("#### 🔍 Detailed Baseline Management")
                    
                    # Render each project
                    for project, baselines in projects_data.items():
                        # Sort by created_at (newest first)
                        baselines_sorted = sorted(
                            baselines, 
                            key=lambda x: x.get('created_at', ''), 
                            reverse=True
                        )
                        
                        render_baseline_section(
                            project,
                            baselines_sorted,
                            admin_key,
                            github,
                            "automation_api",
                            "api"
                        )
        
        except Exception as e:
            st.error(f"❌ Error loading AutomationAPI baselines: {str(e)}")
            import traceback
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())