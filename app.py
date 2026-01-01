import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
from datetime import datetime

from storage.baseline_service import BaselineService
from github_storage import GitHubStorage
github = GitHubStorage(
    token=st.secrets.get("GITHUB_TOKEN"),
    repo_owner=st.secrets.get("GITHUB_OWNER"),
    repo_name=st.secrets.get("GITHUB_REPO")
)

baseline_service = BaselineService(github)


# -----------------------------------------------------------
# IMPORT MULTI-BASELINE ENGINE (NEW - OPTIONAL)
# -----------------------------------------------------------
try:
    from baseline_engine import (
        save_baseline as save_multi_baseline,
        load_baseline as load_multi_baseline,
        list_baselines,
        get_latest_baseline,
        compare_with_baseline as compare_multi_baseline,
        baseline_exists as multi_baseline_exists,
        get_baseline_stats
    )
    MULTI_BASELINE_AVAILABLE = True
except ImportError:
    MULTI_BASELINE_AVAILABLE = False
    print("⚠️ Multi-baseline engine not available, using legacy baseline manager")
    # -----------------------------------------------------------
# IMPORT AUTOMATIONAPI MODULES (NEW)
# -----------------------------------------------------------
from automation_api_extractor import (
    extract_automation_api_failures,
    group_failures_by_spec,
    get_failure_statistics
)

# Import BOTH old and new baseline managers for AutomationAPI
from automation_api_baseline_manager import (
    save_baseline as save_api_baseline_legacy,
    compare_with_baseline as compare_api_baseline_legacy,
    load_baseline as load_api_baseline_legacy,
    baseline_exists as api_baseline_exists_legacy
)

try:
    from automation_api_baseline_engine import (
        save_baseline as save_api_baseline_multi,
        compare_with_baseline as compare_api_baseline_multi,
        list_baselines as list_api_baselines,
        get_baseline_stats as get_api_baseline_stats,
        baseline_exists as api_baseline_exists_multi,
        get_latest_baseline as get_api_latest_baseline
    )
    API_MULTI_BASELINE_AVAILABLE = True
except ImportError:
    API_MULTI_BASELINE_AVAILABLE = False
    print("⚠️ AutomationAPI multi-baseline engine not available")

# -----------------------------------------------------------
# IMPORT OLD BASELINE MANAGER (BACKWARD COMPATIBILITY - ALWAYS WORKS)
# -----------------------------------------------------------
from baseline_manager import (
    save_baseline,
    load_baseline,
    compare_with_baseline,
    baseline_exists as legacy_baseline_exists,
    KNOWN_PROJECTS
)

# Import dashboard
from baseline_tracker_dashboard import render_baseline_tracker_dashboard

# -----------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------
def format_execution_time(raw_time: str):
    """Format timestamp from XML to readable format"""
    if raw_time in (None, "", "Unknown"):
        return "Unknown"
    
    # Try different datetime formats
    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",           # ISO format: 2025-01-15T14:30:00
        "%Y-%m-%d %H:%M:%S",           # Common format: 2025-01-15 14:30:00
        "%a %b %d %H:%M:%S %Z %Y",     # Full format: Wed Jan 15 14:30:00 UTC 2025
        "%Y-%m-%dT%H:%M:%S.%f",        # With milliseconds
        "%Y-%m-%dT%H:%M:%SZ",          # With Z suffix
        "%d/%m/%Y %H:%M:%S",           # DD/MM/YYYY format
        "%m/%d/%Y %H:%M:%S",           # MM/DD/YYYY format
    ]
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(raw_time, fmt)
            return dt.strftime("%d %b %Y, %H:%M UTC")
        except ValueError:
            continue
    
    # If no format matches, return as-is
    return raw_time

def _format_time(ts: str):
    """Format timestamp string to readable format"""
    try:
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts

# -----------------------------------------------------------
# IMPORT PROVAR MODULES (EXISTING)
# -----------------------------------------------------------
from xml_extractor import extract_failed_tests
from ai_reasoner import (
    generate_ai_summary, 
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)
from baseline_manager import (
    save_baseline as save_provar_baseline,
    compare_with_baseline as compare_provar_baseline,
    load_baseline as load_provar_baseline
)

# -----------------------------------------------------------
# IMPORT AUTOMATIONAPI MODULES (NEW)
# -----------------------------------------------------------
from automation_api_extractor import (
    extract_automation_api_failures,
    group_failures_by_spec,
    get_failure_statistics
)
from automation_api_baseline_manager import (
    save_baseline as save_api_baseline,
    compare_with_baseline as compare_api_baseline,
    load_baseline as load_api_baseline,
    baseline_exists as api_baseline_exists
)

# -----------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------
APP_VERSION = "3.2.0"  # Updated version with baseline management UI

# -----------------------------------------------------------
# PROVAR HELPER FUNCTIONS (EXISTING)
# -----------------------------------------------------------
def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {str(e)}")
        return []

def detect_project(path: str, filename: str):
    for p in KNOWN_PROJECTS:
        if path and (f"/{p}" in path or f"\\{p}" in path):
            return p
        if p.lower() in filename.lower():
            return p
    if "datetime" in filename.lower():
        return "Date_Time"
    return "UNKNOWN_PROJECT"

def shorten_project_cache_path(path):
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]

def render_summary_card(xml_name, new_count, existing_count, total_count):
    """Render a summary card for each XML file"""
    status_color = "🟢" if new_count == 0 else "🔴"
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", status_color)
    with col2:
        st.metric("New Failures", new_count, delta=None if new_count == 0 else f"+{new_count}", delta_color="inverse")
    with col3:
        st.metric("Existing Failures", existing_count)
    with col4:
        st.metric("Total Failures", total_count)

def render_comparison_chart(all_results):
    """Create a comparison chart across all uploaded XMLs"""
    if not all_results:
        return
    
    df_data = []
    for result in all_results:
        df_data.append({
            'File': result['project'],
            'New Failures': result['new_count'],
            'Existing Failures': result['existing_count'],
            'Total': result['total_count']
        })
    
    df = pd.DataFrame(df_data)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='New Failures',
        x=df['File'],
        y=df['New Failures'],
        marker_color='#FF4B4B'
    ))
    fig.add_trace(go.Bar(
        name='Existing Failures',
        x=df['File'],
        y=df['Existing Failures'],
        marker_color='#FFA500'
    ))
    
    fig.update_layout(
        title='Failure Comparison Across All Reports',
        xaxis_title='XML Files',
        yaxis_title='Number of Failures',
        barmode='stack',
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------
st.set_page_config("Provar AI - Multi-Platform XML Analyzer", layout="wide", page_icon="🚀")
# -----------------------------------------------------------
# STEP-3: AUTO SYNC BASELINES FROM GITHUB (ONCE PER SESSION)
# -----------------------------------------------------------
if "baselines_synced" not in st.session_state:
    try:
        synced = baseline_service.sync_from_github()
        st.session_state.baselines_synced = True

        if synced > 0:
            st.toast(f"🔄 {synced} baseline(s) synced from GitHub", icon="✅")
    except Exception as e:
        # Do NOT block app startup if sync fails
        print(f"Auto-sync skipped: {e}")
# -----------------------------------------------------------

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .section-divider {
        border-top: 2px solid #e0e0e0;
        margin: 2rem 0;
    }
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .ai-feature-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    .spec-group {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 8px;
    }
    .real-failure {
        border-left: 4px solid #dc3545;
    }
    .skipped-failure {
        border-left: 4px solid #ffc107;
        background: #fff9e6;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🤖 Provar AI - Multi-Platform Report Analysis Tool</div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR CONFIGURATION
# -----------------------------------------------------------
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🔍 GitHub Connection Status")
    
    try:
        # Test GitHub connection
        test_list = github.list_baselines()
        st.success(f"✅ GitHub Connected")
        st.caption(f"Found {len(test_list)} baseline(s)")
    except Exception as e:
        st.error("❌ GitHub Connection Failed")
        st.code(str(e))
        
        # Show which secrets are missing
        if st.secrets.get("GITHUB_TOKEN"):
            st.info("✅ GITHUB_TOKEN found")
        else:
            st.error("❌ GITHUB_TOKEN missing")
            
        if st.secrets.get("GITHUB_OWNER"):
            st.info(f"✅ Owner: {st.secrets.get('GITHUB_OWNER')}")
        else:
            st.error("❌ GITHUB_OWNER missing")
            
        if st.secrets.get("GITHUB_REPO"):
            st.info(f"✅ Repo: {st.secrets.get('GITHUB_REPO')}")
        else:
            st.error("❌ GITHUB_REPO missing")
    st.markdown("---")
    st.subheader("🔄 Baseline Sync")

    if st.button("🔄 Sync Baselines from GitHub"):
        with st.spinner("Syncing baselines from GitHub..."):
            synced = baseline_service.sync_from_github()
        st.success(f"✅ {synced} baseline(s) synced from GitHub")
        st.rerun()

    # -----------------------------------------------------------
    # NEW: BASELINE MANAGEMENT SECTION
    # -----------------------------------------------------------
    st.markdown("---")
    st.subheader("📋 Manage Saved Baselines")
    
    # Dropdown to select platform
    platform_filter = st.selectbox(
        "Filter by Platform:",
        options=["All", "Provar", "AutomationAPI"],
        index=0,
        key="platform_filter"
    )
    
    # Load baselines from GitHub
    if st.button("🔍 Show Baselines", key="show_baselines_btn"):
        try:
            # Get all baselines from GitHub
            all_files = github.list_baselines()
            
            if all_files:
                # Filter by platform if needed
                if platform_filter == "Provar":
                    filtered = [f for f in all_files if "_provar_" in f['name'].lower()]
                elif platform_filter == "AutomationAPI":
                    filtered = [f for f in all_files if "_automation_api_" in f['name'].lower()]
                else:
                    filtered = all_files
                
                st.session_state['baseline_list'] = filtered
                st.success(f"✅ Found {len(filtered)} baseline(s)")
            else:
                st.info("No baselines found in GitHub")
                st.session_state['baseline_list'] = []
        
        except Exception as e:
            st.error(f"Error loading baselines: {str(e)}")
            st.session_state['baseline_list'] = []
    
    # Display baselines if they exist in session state
    if 'baseline_list' in st.session_state and st.session_state['baseline_list']:
        st.write(f"**{len(st.session_state['baseline_list'])} baseline(s) available:**")
        
        for idx, baseline in enumerate(st.session_state['baseline_list']):
            with st.expander(f"📄 {baseline['name']}", expanded=False):
                st.caption(f"Size: {baseline.get('size', 'Unknown')} bytes")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📥 Load", key=f"load_baseline_{idx}"):
                        try:
                            content = github.load_baseline(baseline['name'])
                            if content:
                                st.session_state['loaded_baseline'] = content
                                st.session_state['loaded_baseline_name'] = baseline['name']
                                st.success("✅ Baseline loaded!")
                                st.rerun()
                            else:
                                st.error("Failed to load baseline")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_baseline_{idx}"):
                        # Get admin_key from session state or show error
                        admin_key = st.session_state.get('admin_key_input', '')
                        if admin_key:
                            try:
                                if github.delete_baseline(baseline['name']):
                                    st.success("✅ Deleted!")
                                    # Remove from session state
                                    st.session_state['baseline_list'].remove(baseline)
                                    st.rerun()
                                else:
                                    st.error("Delete failed")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                        else:
                            st.error("🔒 Admin key required for deletion")
    
    # Show loaded baseline info if exists
    if 'loaded_baseline_name' in st.session_state:
        st.markdown("---")
        st.success(f"📂 Loaded: **{st.session_state['loaded_baseline_name']}**")
        if st.button("🗑️ Clear Loaded", key="clear_loaded"):
            del st.session_state['loaded_baseline']
            del st.session_state['loaded_baseline_name']
            st.rerun()
    
    # -----------------------------------------------------------
    # END OF NEW BASELINE MANAGEMENT SECTION
    # -----------------------------------------------------------

    st.markdown("---")
    st.header("⚙️ Configuration")
    
    # NEW: Radio button for report type selection
    st.subheader("📊 Report Type")
    report_type = st.radio(
        "Select Report Type:",
        options=["Provar Regression Reports", "AutomationAPI Reports", "📈 Baseline Tracker"],
        index=0,
        help="Choose the type of XML report you want to analyze"
    )
    
    st.markdown("---")
    
    # AI Settings
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=False, help="Use Groq AI for intelligent failure analysis")
    
    # Advanced AI Features
    with st.expander("🎯 Advanced AI Features"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", value=True, help="Find common patterns across failures")
        enable_jira_generation = st.checkbox("Jira Ticket Generation", value=True, help="Auto-generate Jira tickets")
        enable_test_improvements = st.checkbox("Test Improvement Suggestions", value=False, help="Get suggestions to improve test stability")
    
    admin_key = st.text_input("🔐 Admin Key", type="password", help="Required for saving baselines", key="admin_key_input")
    
    # Multi-baseline toggle (only show if available)
    if MULTI_BASELINE_AVAILABLE:
        st.markdown("---")
        st.subheader("🆕 Multi-Baseline")
        use_multi_baseline = st.checkbox(
            "Enable Multi-Baseline (NEW)",
            value=True,
            help="Store up to 10 baselines per project (recommended)"
        )
    else:
        use_multi_baseline = False
    
    st.markdown("---")
    
    # Version info
    st.caption(f"Version: {APP_VERSION}")
    if MULTI_BASELINE_AVAILABLE and use_multi_baseline:
        st.success("✅ Multi-Baseline Active")
    
    # Reset Button
    if st.button("🔄 Reset All", type="secondary", use_container_width=True, help="Clear all data and start fresh"):
        # Clear session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ UI Reset! Ready for new uploads.")
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Upload Statistics")
    if 'upload_stats' in st.session_state:
        st.info(f"**Files Uploaded:** {st.session_state.upload_stats.get('count', 0)}")
        st.info(f"**Total Failures:** {st.session_state.upload_stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {st.session_state.upload_stats.get('new_failures', 0)}")
    
    # AI Status
    st.markdown("---")
    st.markdown("### 🤖 AI Status")
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if groq_key:
        st.success("✅ Groq AI (Free)")
    elif openai_key:
        st.info("ℹ️ OpenAI (Paid)")
    else:
        st.warning("⚠️ No AI configured")

# -----------------------------------------------------------
# MAIN CONTENT AREA - ADD LOADED BASELINE DISPLAY
# -----------------------------------------------------------

# OPTIONAL: Display loaded baseline in main area
if 'loaded_baseline' in st.session_state:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("## 📂 Loaded Baseline Details")
    
    st.info(f"📄 Currently viewing: **{st.session_state.get('loaded_baseline_name', 'Unknown')}**")
    
    with st.expander("👁️ View Baseline Content", expanded=False):
        st.code(st.session_state['loaded_baseline'], language='json')
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "📥 Download Baseline",
            st.session_state['loaded_baseline'],
            file_name=st.session_state.get('loaded_baseline_name', 'baseline.json'),
            mime='application/json',
            key="download_baseline_main"
        )
    
    with col2:
        if st.button("🗑️ Clear Loaded Baseline", key="clear_main"):
            del st.session_state['loaded_baseline']
            del st.session_state['loaded_baseline_name']
            st.rerun()
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# MAIN CONTENT AREA
# -----------------------------------------------------------

# BASELINE TRACKER PAGE (NEW - USES MULTI-BASELINE IF AVAILABLE)
if report_type == "📈 Baseline Tracker":
    render_baseline_tracker_dashboard()

elif report_type == "Provar Regression Reports":
    # ============================================================
    # PROVAR XML REPORT ANALYSIS (EXISTING FUNCTIONALITY - COMPLETE)
    # ============================================================
    st.markdown("## 📁 Upload Provar XML Reports")
    st.markdown("Upload multiple JUnit XML reports from Provar test executions for simultaneous AI-powered analysis")
    
    uploaded_files = st.file_uploader(
        "Choose Provar XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="provar_uploader",
        help="Select one or more XML files to analyze"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} Provar file(s) uploaded successfully!")
        
        # Initialize session state for results
        if 'all_results' not in st.session_state:
            st.session_state.all_results = []
        
        # -----------------------------------------------------------
        # GLOBAL ANALYSIS BUTTON
        # -----------------------------------------------------------
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_all = st.button("🔍 Analyze All Provar Reports", type="primary", use_container_width=True)
        
        if analyze_all:
            st.session_state.all_results = []
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, xml_file in enumerate(uploaded_files):
                status_text.text(f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_files)})")
                
                failures = safe_extract_failures(xml_file)
                
                if failures:
                    project_path = failures[0].get("projectCachePath", "")
                    detected_project = detect_project(project_path, xml_file.name)
                    
                    # Capture timestamp from first failure
                    execution_time = failures[0].get("timestamp", "Unknown")
                    
                    normalized = []
                    for f in failures:
                        if f.get("name") != "__NO_FAILURES__":
                            normalized.append({
                                "testcase": f["name"],
                                "testcase_path": f.get("testcase_path", ""),
                                "error": f["error"],
                                "details": f["details"],
                                "source": xml_file.name,
                                "webBrowserType": f.get("webBrowserType", "Unknown"),
                                "projectCachePath": shorten_project_cache_path(f.get("projectCachePath", "")),
                            })
                    
                    # Compare with baseline (use multi-baseline if enabled and available)
                    baseline_exists_flag = False
                    if MULTI_BASELINE_AVAILABLE and use_multi_baseline:
                        baseline_exists_flag = multi_baseline_exists(detected_project)
                        if baseline_exists_flag:
                            new_f, existing_f = compare_multi_baseline(detected_project, normalized)
                        else:
                            new_f, existing_f = normalized, []
                    else:
                        baseline_exists_flag = bool(load_provar_baseline(detected_project))
                        if baseline_exists_flag:
                            new_f, existing_f = compare_provar_baseline(detected_project, normalized)
                        else:
                            new_f, existing_f = normalized, []
                    
                    st.session_state.all_results.append({
                        'filename': xml_file.name,
                        'project': detected_project,
                        'new_failures': new_f,
                        'existing_failures': existing_f,
                        'new_count': len(new_f),
                        'existing_count': len(existing_f),
                        'total_count': len(normalized),
                        'baseline_exists': baseline_exists_flag,
                        'execution_time': execution_time
                    })
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.text("✅ Analysis complete!")
            progress_bar.empty()
            
            # Update upload statistics
            total_failures = sum(r['total_count'] for r in st.session_state.all_results)
            new_failures = sum(r['new_count'] for r in st.session_state.all_results)
            
            st.session_state.upload_stats = {
                'count': len(uploaded_files),
                'total_failures': total_failures,
                'new_failures': new_failures
            }
            
            # Generate batch analysis if enabled
            if use_ai and enable_batch_analysis:
                with st.spinner("🧠 Running batch pattern analysis..."):
                    all_failures = []
                    for result in st.session_state.all_results:
                        all_failures.extend(result['new_failures'])
                    
                    if all_failures:
                        st.session_state.batch_analysis = generate_batch_analysis(all_failures)
        
        # -----------------------------------------------------------
        # DISPLAY PROVAR RESULTS
        # -----------------------------------------------------------
        if st.session_state.all_results:
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            # Batch Pattern Analysis
            if 'batch_analysis' in st.session_state and st.session_state.batch_analysis:
                st.markdown('<div class="ai-feature-box">', unsafe_allow_html=True)
                st.markdown("## 🧠 AI Batch Pattern Analysis")
                st.markdown("AI has analyzed all failures together to identify patterns and priorities.")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.markdown(st.session_state.batch_analysis)
                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            st.markdown("## 📊 Overall Summary")
            
            # Overall statistics
            total_new = sum(r['new_count'] for r in st.session_state.all_results)
            total_existing = sum(r['existing_count'] for r in st.session_state.all_results)
            total_all = sum(r['total_count'] for r in st.session_state.all_results)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Total Files", len(st.session_state.all_results))
            with col2:
                st.metric("🆕 Total New Failures", total_new, delta=f"+{total_new}" if total_new > 0 else "0", delta_color="inverse")
            with col3:
                st.metric("♻️ Total Existing Failures", total_existing)
            with col4:
                st.metric("📈 Total All Failures", total_all)
            
            # Comparison chart
            render_comparison_chart(st.session_state.all_results)
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("## 📋 Detailed Results by File")
            
            # Individual file results
            for idx, result in enumerate(st.session_state.all_results):
                formatted_time = format_execution_time(result.get("execution_time", "Unknown"))

                with st.expander(
                    f"📄 {result['filename']} | ⏰ {formatted_time} – Project: {result['project']}",
                    expanded=False
                ):
                    
                    # Summary card for this file
                    render_summary_card(
                        result['filename'],
                        result['new_count'],
                        result['existing_count'],
                        result['total_count']
                    )
                    
                    st.markdown("---")
                    
                    # Multi-baseline selection (NEW - only if enabled)
                    if MULTI_BASELINE_AVAILABLE and use_multi_baseline:
                        st.markdown("### 🎯 Baseline Selection")
                        baselines = list_baselines(result['project'])
                        
                        if baselines:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                baseline_options = ['Latest'] + [b['id'] for b in baselines]
                                selected_baseline = st.selectbox(
                                    "Compare with baseline:",
                                    options=baseline_options,
                                    format_func=lambda x: f"Latest ({baselines[0]['label']}) - {baselines[0]['failure_count']} failures" if x == 'Latest' else f"{[b for b in baselines if b['id'] == x][0]['label']} - {[b for b in baselines if b['id'] == x][0]['failure_count']} failures",
                                    key=f"baseline_select_{idx}"
                                )
                            
                            with col2:
                                if st.button("🔄 Recompare", key=f"recompare_{idx}"):
                                    baseline_id = None if selected_baseline == 'Latest' else selected_baseline
                                    all_failures = result['new_failures'] + result['existing_failures']
                                    new_f, existing_f = compare_multi_baseline(
                                        result['project'],
                                        all_failures,
                                        baseline_id
                                    )
                                    result['new_failures'] = new_f
                                    result['existing_failures'] = existing_f
                                    result['new_count'] = len(new_f)
                                    result['existing_count'] = len(existing_f)
                                    st.rerun()
                            
                            st.info(f"📊 {len(baselines)} baseline(s) available for {result['project']}")
                            
                            # Show baseline stats
                            if baselines:
                                stats = get_baseline_stats(result['project'])
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Baselines", stats['count'])
                                with col2:
                                    st.metric("Latest", stats['latest'][:8] if stats['latest'] else '-')
                                with col3:
                                    st.metric("Oldest", stats['oldest'][:8] if stats.get('oldest') else '-')
                        else:
                            st.warning(f"⚠️ No baseline found for {result['project']}")
                        
                        st.markdown("---")

                    # Tabs for different failure types
                    tab1, tab2, tab3 = st.tabs(["🆕 New Failures", "♻️ Existing Failures", "⚙️ Actions"])
                    
                    with tab1:
                        if result['new_count'] == 0:
                            st.success("✅ No new failures detected!")
                        else:
                            for i, f in enumerate(result['new_failures']):
                                with st.expander(f"🆕 {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.markdown("**Path:**")
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    st.markdown("**Error Details (click copy icon):**")
                                    st.code(f['details'], language="text")
                                    
                                    # AI Features
                                    if use_ai:
                                        ai_tabs = []
                                        if True:
                                            ai_tabs.append("🤖 AI Analysis")
                                        if enable_jira_generation:
                                            ai_tabs.append("📝 Jira Ticket")
                                        if enable_test_improvements:
                                            ai_tabs.append("💡 Improvements")
                                        
                                        if len(ai_tabs) > 0:
                                            ai_tab_objects = st.tabs(ai_tabs)
                                            
                                            with ai_tab_objects[0]:
                                                with st.spinner("Analyzing..."):
                                                    ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'])
                                                    st.info(ai_analysis)
                                            
                                            if enable_jira_generation and len(ai_tab_objects) > 1:
                                                with ai_tab_objects[1]:
                                                    with st.spinner("Generating Jira ticket..."):
                                                        jira_content = generate_jira_ticket(
                                                            f['testcase'], 
                                                            f['error'], 
                                                            f['details'],
                                                            ai_analysis if 'ai_analysis' in locals() else ""
                                                        )
                                                        st.markdown(jira_content)
                                                        st.download_button(
                                                            "📥 Download Jira Content",
                                                            jira_content,
                                                            file_name=f"jira_{f['testcase'][:30]}.txt",
                                                            key=f"jira_provar_{idx}_{i}"
                                                        )
                                            
                                            if enable_test_improvements and len(ai_tab_objects) > 2:
                                                with ai_tab_objects[-1]:
                                                    with st.spinner("Generating improvement suggestions..."):
                                                        improvements = suggest_test_improvements(
                                                            f['testcase'],
                                                            f['error'],
                                                            f['details']
                                                        )
                                                        st.success(improvements)
                                    
                                    st.markdown("---")
                    
                    with tab2:
                        if result['existing_count'] == 0:
                            st.info("ℹ️ No existing failures found in baseline")
                        else:
                            st.warning(f"Found {result['existing_count']} known failures")
                            for i, f in enumerate(result['existing_failures']):
                                with st.expander(f"♻️ {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.markdown("**Path:**")
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    st.markdown("**Error Details:**")
                                    st.code(f['details'], language="text")
                                    st.markdown("---")
                    
                    with tab3:
                        st.markdown("### 🛠️ Baseline Management")
                        
                        # Project selection
                        st.markdown("### 📌 Select Project for Baseline")
                        project_options = KNOWN_PROJECTS
                        selected_project = result['project']
                        if result['project'] == "UNKNOWN_PROJECT":
                            selected_project = st.selectbox(
                                "Choose correct project",
                                options=project_options,
                                key=f"project_select_{idx}"
                            )
                        else:
                            st.info(f"Detected Project: {result['project']}")
                        
                        # Save baseline section
                        col1, col2 = st.columns(2)
                        
                        # Multi-baseline save (NEW)
                        if MULTI_BASELINE_AVAILABLE and use_multi_baseline:
                            with col1:
                                baseline_label = st.text_input(
                                    "Baseline Label",
                                    value="Auto",
                                    key=f"label_{idx}",
                                    help="Custom label for this baseline (e.g., Sprint 23, Release 1.5)"
                                )
                            
                            with col2:
                                if st.button(f"💾 Save as New Baseline", key=f"save_multi_{idx}"):
                                    if not admin_key:
                                        st.error("❌ Admin key required!")
                                    else:
                                        expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
                                        if admin_key == expected_key:
                                            try:
                                                all_failures = result['new_failures'] + result['existing_failures']
                                                if selected_project == "UNKNOWN_PROJECT":
                                                    st.error("Please select a project before saving baseline.")
                                                else:
                                                    baseline_id = baseline_service.save(
                                                        project=selected_project,
                                                        platform="provar",
                                                        failures=all_failures,
                                                        label=baseline_label if baseline_label else None
                                                        )
                                                    st.success(f"✅ Multi-baseline saved! ID: {baseline_id}")
                                                    baselines = list_baselines(selected_project)
                                                    st.info(f"📊 This project now has {len(baselines)} baseline(s)")
                                            except Exception as e:
                                                st.error(f"❌ Error: {str(e)}")
                                        else:
                                            st.error("❌ Invalid admin key")
                        else:
                            # Legacy baseline save (EXISTING)
                            with col1:
                                if st.button(f"💾 Save as Baseline", key=f"save_provar_{idx}"):
                                    if not admin_key:
                                        st.error("❌ Admin key required!")
                                    else:
                                        try:
                                            all_failures = result['new_failures'] + result['existing_failures']
                                            if selected_project == "UNKNOWN_PROJECT":
                                                st.error("Please select a project before saving baseline.")
                                            else:
                                                baseline_service.save(
                                                    project=selected_project,
                                                    platform="provar",
                                                    failures=all_failures,
                                                    label=baseline_label if baseline_label else None
                                                    )
                                                st.success("✅ Provar baseline saved successfully!")
                                        except Exception as e:
                                            st.error(f"❌ Error: {str(e)}")
                            
                            with col2:
                                if result['baseline_exists']:
                                    st.success("✅ Baseline exists for this project")
                                else:
                                    st.warning("⚠️ No baseline found")
                        
                        # Export options
                        st.markdown("### 📤 Export Options")
                        export_data = pd.DataFrame(result['new_failures'] + result['existing_failures'])
                        
                        if not export_data.empty:
                            csv = export_data.to_csv(index=False)
                            st.download_button(
                                label="📥 Download as CSV",
                                data=csv,
                                file_name=f"{result['filename']}_failures.csv",
                                mime="text/csv",
                                key=f"export_provar_{idx}"
                            )
    else:
        # Welcome message when no files uploaded
        st.info("👆 Upload one or more Provar XML files to begin AI-powered analysis")
        
        st.markdown("### 🎯 Provar Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**📊 Multi-File Analysis**")
            st.write("Upload and analyze multiple XML reports simultaneously")
        with col2:
            st.markdown("**🤖 AI-Powered Insights**")
            st.write("Get intelligent failure analysis with Groq (FREE)")
        with col3:
            st.markdown("**📈 Baseline Tracking**")
            st.write("Compare results against historical baselines")
        
        if MULTI_BASELINE_AVAILABLE:
            st.markdown("---")
            st.info("🆕 **Multi-Baseline Feature Available!** Store up to 10 baselines per project and compare any two baselines.")
        
        st.markdown("---")
        
        st.markdown("### 🆕 AI Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**🧠 Batch Pattern Analysis**")
            st.write("AI identifies common patterns across all failures")
        with col2:
            st.markdown("**📝 Jira Auto-Generation**")
            st.write("Create ready-to-use Jira tickets instantly")
        with col3:
            st.markdown("**💡 Test Improvements**")
            st.write("Get suggestions to make tests more stable")

else:
    # ============================================================
    # AUTOMATION API REPORT ANALYSIS (EXISTING FUNCTIONALITY)
    # ============================================================
    st.markdown("## 🔧 Upload AutomationAPI XML Reports")
    st.markdown("Upload XML reports from AutomationAPI test executions (e.g., Jasmine/Selenium tests)")
    
    uploaded_api_files = st.file_uploader(
        "Choose AutomationAPI XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="api_uploader",
        help="Upload XML reports from AutomationAPI workspace"
    )
    
    if uploaded_api_files:
        st.success(f"✅ {len(uploaded_api_files)} AutomationAPI file(s) uploaded!")
        
        # Initialize session state
        if 'api_results' not in st.session_state:
            st.session_state.api_results = []
        
        # -----------------------------------------------------------
        # ANALYSIS BUTTON
        # -----------------------------------------------------------
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_api = st.button("🔍 Analyze AutomationAPI Reports", type="primary", use_container_width=True)
        
        if analyze_api:
            st.session_state.api_results = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, xml_file in enumerate(uploaded_api_files):
                status_text.text(f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_api_files)})")
                
                try:
                    failures = extract_automation_api_failures(xml_file)
                    
                    if failures:
                        project = failures[0].get("project", "Unknown")
                        
                       # ============================================================
                        # COMPARE WITH BASELINE (MULTI-BASELINE AWARE)
                        # ============================================================
                        
                        # Filter out metadata record
                        real_failures = [f for f in failures if not f.get("_no_failures")]
                        
                        # Determine which baseline system to use
                        if API_MULTI_BASELINE_AVAILABLE and use_multi_baseline:
                            # Use multi-baseline engine
                            if api_baseline_exists_multi(project):
                                # Compare with latest baseline
                                new_f, existing_f = compare_api_baseline_multi(
                                    project,
                                    real_failures
                                )
                            else:
                                # No baseline exists - all failures are new
                                new_f, existing_f = real_failures, []
                            
                            # Check baseline existence
                            baseline_exists_flag = api_baseline_exists_multi(project)
                        
                        else:
                            # Use legacy single-baseline system
                            if api_baseline_exists_legacy(project):
                                # Compare with single baseline
                                new_f, existing_f = compare_api_baseline_legacy(
                                    project,
                                    real_failures
                                )
                            else:
                                # No baseline exists - all failures are new
                                new_f, existing_f = real_failures, []
                            
                            # Check baseline existence
                            baseline_exists_flag = api_baseline_exists_legacy(project)
                        
                        # Get statistics
                        stats = get_failure_statistics(real_failures if real_failures else failures)
                        
                        st.session_state.api_results.append({
                            'filename': xml_file.name,
                            'project': project,
                            'all_failures': real_failures if real_failures else [],
                            'new_failures': new_f,
                            'existing_failures': existing_f,
                            'grouped_failures': group_failures_by_spec(real_failures) if real_failures else {},
                            'stats': stats,
                            'baseline_exists': baseline_exists_flag,
                            'timestamp': failures[0].get("timestamp", "Unknown") if failures else "Unknown"
                        })
                
                except Exception as e:
                    st.error(f"Error parsing {xml_file.name}: {str(e)}")
                
                progress_bar.progress((idx + 1) / len(uploaded_api_files))
            
            status_text.text("✅ Analysis complete!")
            progress_bar.empty()
            
            # Update stats
            total_failures = sum(r['stats']['total_failures'] for r in st.session_state.api_results)
            new_failures = sum(len(r['new_failures']) for r in st.session_state.api_results)
            
            st.session_state.upload_stats = {
                'count': len(uploaded_api_files),
                'total_failures': total_failures,
                'new_failures': new_failures
            }
        
        # -----------------------------------------------------------
        # DISPLAY AUTOMATIONAPI RESULTS
        # -----------------------------------------------------------
        if st.session_state.api_results:
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("## 📊 AutomationAPI Analysis Results")
            
            # Overall statistics
            total_real = sum(r['stats']['real_failures'] for r in st.session_state.api_results)
            total_skipped = sum(r['stats']['skipped_failures'] for r in st.session_state.api_results)
            total_all = sum(r['stats']['total_failures'] for r in st.session_state.api_results)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Total Files", len(st.session_state.api_results))
            with col2:
                st.metric("🔴 Real Failures", total_real)
            with col3:
                st.metric("🟡 Skipped Failures", total_skipped)
            with col4:
                st.metric("📈 Total Failures", total_all)
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            # Individual file results
            for idx, result in enumerate(st.session_state.api_results):
                with st.expander(
                    f"📄 {result['filename']} — Project: {result['project']} | "
                    f"⏰ {result['timestamp']} | "
                    f"Failures: {result['stats']['total_failures']}",
                    expanded=False
                ):
                    
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("🔴 Real Failures", result['stats']['real_failures'])
                    with col2:
                        st.metric("🟡 Skipped", result['stats']['skipped_failures'])
                    with col3:
                        st.metric("📋 Spec Files", result['stats']['unique_specs'])
                    with col4:
                        st.metric("⏱️ Total Time", f"{result['stats']['total_time']}s")
                    
                    st.markdown("---")


                    st.markdown("---")
                    
                    # ============================================================
                    # BASELINE COMPARISON SUMMARY (NEW SECTION)
                    # ============================================================
                    if result['baseline_exists'] and (result['new_failures'] or result['existing_failures']):
                        st.markdown("### 📊 Baseline Comparison Summary")
                        
                        # Separate new and existing failures by spec
                        new_by_spec = {}
                        existing_by_spec = {}
                        
                        for failure in result['new_failures']:
                            spec = failure.get('spec_file', 'Unknown')
                            if spec not in new_by_spec:
                                new_by_spec[spec] = []
                            new_by_spec[spec].append(failure)
                        
                        for failure in result['existing_failures']:
                            spec = failure.get('spec_file', 'Unknown')
                            if spec not in existing_by_spec:
                                existing_by_spec[spec] = []
                            existing_by_spec[spec].append(failure)
                        
                        # Get all unique specs
                        all_specs = set(new_by_spec.keys()) | set(existing_by_spec.keys())
                        
                        # Categorize specs
                        new_specs = [s for s in new_by_spec.keys() if s not in existing_by_spec]
                        mixed_specs = [s for s in all_specs if s in new_by_spec and s in existing_by_spec]
                        existing_only_specs = [s for s in existing_by_spec.keys() if s not in new_by_spec]
                        
                        # Display summary cards
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric(
                                "🆕 New Spec Files",
                                len(new_specs),
                                help="Spec files that are completely new (not in baseline)"
                            )
                        
                        with col2:
                            st.metric(
                                "📊 Specs with New Tests",
                                len(mixed_specs),
                                help="Spec files with mix of new and existing failures"
                            )
                        
                        with col3:
                            st.metric(
                                "♻️ Specs with Known Failures",
                                len(existing_only_specs),
                                help="Spec files with only existing (baseline) failures"
                            )
                        
                        st.markdown("---")
                        
                        # 🆕 NEW SPEC FILES (completely new)
                        if new_specs:
                            st.markdown("#### 🆕 New Spec Files (Not in Baseline)")
                            st.info(f"These {len(new_specs)} spec file(s) are completely new and were not in the baseline")
                            
                            for spec in sorted(new_specs):
                                failures = new_by_spec[spec]
                                real_count = len([f for f in failures if not f.get('is_skipped')])
                                skipped_count = len([f for f in failures if f.get('is_skipped')])
                                
                                with st.expander(
                                    f"🆕 {spec} — {len(failures)} failure(s) "
                                    f"(🔴 {real_count} real, 🟡 {skipped_count} skipped)",
                                    expanded=False
                                ):
                                    for i, failure in enumerate(failures):
                                        icon = "🟡" if failure.get('is_skipped') else "🔴"
                                        st.markdown(
                                            f"{icon} **{i+1}. {failure['test_name']}**  \n"
                                            f"   Error: `{failure['error_summary']}`  \n"
                                            f"   Time: {failure['execution_time']}s"
                                        )
                        
                        # 📊 MIXED SPECS (new + existing failures)
                        if mixed_specs:
                            st.markdown("---")
                            st.markdown("#### 📊 Spec Files with New Failures")
                            st.warning(f"These {len(mixed_specs)} spec file(s) have both NEW and EXISTING failures")
                            
                            for spec in sorted(mixed_specs):
                                new_failures_in_spec = new_by_spec.get(spec, [])
                                existing_failures_in_spec = existing_by_spec.get(spec, [])
                                
                                new_real = len([f for f in new_failures_in_spec if not f.get('is_skipped')])
                                new_skipped = len([f for f in new_failures_in_spec if f.get('is_skipped')])
                                existing_count = len(existing_failures_in_spec)
                                
                                with st.expander(
                                    f"📊 {spec} — 🆕 {len(new_failures_in_spec)} new | ♻️ {existing_count} existing",
                                    expanded=False
                                ):
                                    # Show NEW failures
                                    st.markdown(f"**🆕 New Failures ({len(new_failures_in_spec)}):**")
                                    for i, failure in enumerate(new_failures_in_spec):
                                        icon = "🟡" if failure.get('is_skipped') else "🔴"
                                        st.markdown(
                                            f"{icon} {i+1}. **{failure['test_name']}**  \n"
                                            f"   Error: `{failure['error_summary']}`  \n"
                                            f"   Time: {failure['execution_time']}s"
                                        )
                                    
                                    st.markdown("---")
                                    
                                    # Show EXISTING failures (collapsed by default)
                                    with st.expander(f"♻️ View {existing_count} Known Failures", expanded=False):
                                        for i, failure in enumerate(existing_failures_in_spec):
                                            icon = "🟡" if failure.get('is_skipped') else "🔴"
                                            st.markdown(
                                                f"{icon} {i+1}. {failure['test_name']}  \n"
                                                f"   Error: `{failure['error_summary']}`"
                                            )
                        
                        # ♻️ EXISTING ONLY SPECS
                        if existing_only_specs:
                            st.markdown("---")
                            st.markdown("#### ♻️ Spec Files with Known Failures Only")
                            st.success(f"These {len(existing_only_specs)} spec file(s) have no new failures (all in baseline)")
                            
                            with st.expander(f"View {len(existing_only_specs)} spec(s) with known failures", expanded=False):
                                for spec in sorted(existing_only_specs):
                                    failures = existing_by_spec[spec]
                                    st.markdown(f"- **{spec}** — {len(failures)} known failure(s)")
                        
                        st.markdown("---")
                    
                    elif result['baseline_exists']:
                        # Baseline exists but no failures
                        st.success("✅ No failures detected! All tests passed.")
                    
                    else:
                        # No baseline exists
                        st.info("ℹ️ No baseline found. All failures are considered new. Save a baseline to track changes.")
                    
                    # ============================================================
                    # END OF BASELINE COMPARISON SUMMARY
                    # ============================================================
                    
                    st.markdown("---")
                    
                    # Original failures display continues below...
                    
                    # Display failures grouped by spec
                    if result['grouped_failures']:
                        for spec_name, spec_failures in result['grouped_failures'].items():
                            st.markdown(f"### 📋 Spec: `{spec_name}`")
                            st.caption(f"{len(spec_failures)} failure(s) in this spec")
                            
                            for i, failure in enumerate(spec_failures):
                                # Icon based on type
                                icon = "🟡" if failure['is_skipped'] else "🔴"
                                failure_class = "skipped-failure" if failure['is_skipped'] else "real-failure"
                                
                                with st.expander(
                                    f"{icon} {i+1}. {failure['test_name']} ({failure['execution_time']}s)",
                                    expanded=False
                                ):
                                    st.markdown(f"<div class='{failure_class}'>", unsafe_allow_html=True)
                                    
                                    if failure['is_skipped']:
                                        st.warning("⚠️ Skipped due to previous failure")
                                    
                                    st.write("**Test:** ", failure['test_name'])
                                    st.write("**Type:** ", failure['failure_type'])
                                    
                                    # Error summary
                                    st.error(f"**Error:** {failure['error_summary']}")
                                    
                                    # Full details in expandable section
                                    with st.expander("📋 Full Error Details"):
                                        st.code(failure['error_details'], language="text")
                                    
                                    # Stack trace
                                    if failure['full_stack_trace']:
                                        with st.expander("🔍 Stack Trace"):
                                            st.code(failure['full_stack_trace'], language="text")
                                    
                                    # AI Features
                                    if use_ai and not failure['is_skipped']:
                                        st.markdown("---")
                                        ai_tabs = ["🤖 AI Analysis"]
                                        if enable_jira_generation:
                                            ai_tabs.append("📝 Jira Ticket")
                                        if enable_test_improvements:
                                            ai_tabs.append("💡 Improvements")
                                        
                                        ai_tab_objects = st.tabs(ai_tabs)
                                        
                                        with ai_tab_objects[0]:
                                            with st.spinner("Analyzing..."):
                                                ai_analysis = generate_ai_summary(
                                                    failure['test_name'],
                                                    failure['error_summary'],
                                                    failure['error_details']
                                                )
                                                st.info(ai_analysis)
                                        
                                        if enable_jira_generation and len(ai_tab_objects) > 1:
                                            with ai_tab_objects[1]:
                                                with st.spinner("Generating Jira ticket..."):
                                                    jira_content = generate_jira_ticket(
                                                        failure['test_name'],
                                                        failure['error_summary'],
                                                        failure['error_details']
                                                    )
                                                    st.markdown(jira_content)
                                                    st.download_button(
                                                        "📥 Download Jira Content",
                                                        jira_content,
                                                        file_name=f"jira_{failure['test_name'][:30]}.txt",
                                                        key=f"jira_api_{idx}_{i}"
                                                    )
                                        
                                        if enable_test_improvements and len(ai_tab_objects) > 2:
                                            with ai_tab_objects[-1]:
                                                with st.spinner("Generating improvement suggestions..."):
                                                    improvements = suggest_test_improvements(
                                                        failure['test_name'],
                                                        failure['error_summary'],
                                                        failure['error_details']
                                                    )
                                                    st.success(improvements)
                                    
                                    st.markdown("</div>", unsafe_allow_html=True)
                            
                            st.markdown("---")
                    
                    # Baseline Management with Multi-Baseline Support
                    st.markdown("### 🛠️ Baseline Management")
                    
                    # Check if multi-baseline is available
                    if API_MULTI_BASELINE_AVAILABLE and use_multi_baseline:
                        # Multi-baseline selection interface
                        st.markdown("#### 🎯 Baseline Selection")
                        baselines = list_api_baselines(result['project'])
                        
                        if baselines:
                            # Dropdown to select baseline + Recompare button
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                baseline_options = ['Latest'] + [b['id'] for b in baselines]
                                selected_baseline = st.selectbox(
                                    "Choose correct project",
                                    options=baseline_options,
                                    format_func=lambda x: (
                                        f"Latest ({baselines[0]['label']}) - {baselines[0]['failure_count']} failures" 
                                        if x == 'Latest' 
                                        else f"{[b for b in baselines if b['id'] == x][0]['label']} - {[b for b in baselines if b['id'] == x][0]['failure_count']} failures"
                                    ),
                                    key=f"api_baseline_select_{idx}"
                                )
                            
                            with col2:
                                if st.button("🔄 Recompare", key=f"api_recompare_{idx}"):
                                    baseline_id = None if selected_baseline == 'Latest' else selected_baseline
                                    all_failures_for_compare = result['all_failures']
                                    
                                    # Remove metadata-only records before comparison
                                    real_failures = [f for f in all_failures_for_compare if not f.get("_no_failures")]
                                    
                                    new_f, existing_f = compare_api_baseline_multi(
                                        result['project'],
                                        real_failures,
                                        baseline_id
                                    )
                                    
                                    # Update result with new comparison
                                    result['new_failures'] = new_f
                                    result['existing_failures'] = existing_f
                                    result['stats']['real_failures'] = len([f for f in new_f if not f.get('is_skipped')])
                                    result['stats']['total_failures'] = len(new_f) + len(existing_f)
                                    st.rerun()
                            
                            # Show baseline statistics
                            stats = get_api_baseline_stats(result['project'])
                            st.info(f"📊 {stats['count']} baseline(s) available for {result['project']}")
                            
                            # Display baseline details
                            with st.expander("📋 Baseline Details", expanded=False):
                                for i, baseline in enumerate(baselines[:5]):  # Show top 5
                                    label_color = "🟢" if i == 0 else "🟡"
                                    st.markdown(
                                        f"{label_color} **{baseline['label']}** | "
                                        f"Created: {_format_time(baseline['created_at'])} | "
                                        f"Failures: {baseline['failure_count']}"
                                    )
                                
                                if len(baselines) > 5:
                                    st.caption(f"... and {len(baselines) - 5} more")
                        
                        else:
                            st.warning("⚠️ No baseline found for " + result['project'])
                        
                        st.markdown("---")
                        
                        # Save new baseline section
                        st.markdown("#### 💾 Save New Baseline")
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            baseline_label = st.text_input(
                                "Baseline Label (optional)",
                                value="",
                                placeholder="e.g., Sprint 24.1, Release 3.2",
                                key=f"api_baseline_label_{idx}"
                            )
                        
                        with col2:
                            if st.button(f"💾 Save as Baseline", key=f"save_api_{idx}"):
                                if not admin_key:
                                    st.error("❌ Admin key required!")
                                else:
                                    try:
                                        # Use multi-baseline save
                                        baseline_id = baseline_service.save(
                                        project=result['project'],
                                        platform="automation_api",
                                        failures=result['all_failures'],
                                        label=baseline_label or None
                                        )
                                        st.success(f"✅ Baseline saved to GitHub as {baseline_id}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                                        import traceback
                                        st.code(traceback.format_exc())  # Shows detailed error
                    
                    else:
                        # Legacy single-baseline mode (fallback)
                        st.info("ℹ️ Enable Multi-Baseline in sidebar for advanced baseline management")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"💾 Save as Baseline", key=f"save_api_{idx}"):
                                if not admin_key:
                                    st.error("❌ Admin key required!")
                                else:
                                    try:
                                        baseline_service.save(
                                            project=result['project'],
                                            platform="automation_api",
                                            failures=result['all_failures'],
                                            label=None
                                            )
                                        st.success("✅ AutomationAPI baseline saved!")
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                        
                        with col2:
                            if result['baseline_exists']:
                                st.success("✅ Baseline exists")
                            else:
                                st.warning("⚠️ No baseline found")
                    
                    # Export options
                    st.markdown("### 📤 Export Options")
                    if result['all_failures']:
                        export_data = pd.DataFrame(result['all_failures'])
                        csv = export_data.to_csv(index=False)
                        st.download_button(
                            label="📥 Download as CSV",
                            data=csv,
                            file_name=f"{result['filename']}_failures.csv",
                            mime="text/csv",
                            key=f"export_api_{idx}"
                        )
    
    else:
        # Welcome message
        st.info("👆 Upload AutomationAPI XML files to begin analysis")
        
        st.markdown("### 🎯 AutomationAPI Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**📋 Spec-Based Grouping**")
            st.write("Failures grouped by spec file for clarity")
        with col2:
            st.markdown("**🎨 Smart Color Coding**")
            st.write("🔴 Real failures vs 🟡 Skipped failures")
        with col3:
            st.markdown("**📊 Detailed Statistics**")
            st.write("Per-spec analysis with execution times")