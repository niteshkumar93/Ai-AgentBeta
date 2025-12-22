import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
from datetime import datetime

# -----------------------------------------------------------
# IMPORT MULTI-BASELINE ENGINE (NEW)
# -----------------------------------------------------------
from baseline_engine import (
    save_baseline,
    load_baseline,
    list_baselines,
    get_latest_baseline,
    compare_with_baseline,
    baseline_exists,
    get_baseline_stats
)

# Import the new dashboard
from baseline_tracker_dashboard import render_baseline_tracker_dashboard

# -----------------------------------------------------------
# IMPORT OLD BASELINE MANAGER (BACKWARD COMPATIBILITY)
# -----------------------------------------------------------
from baseline_manager import (
    save_baseline as save_legacy_baseline,
    load_baseline as load_legacy_baseline,
    compare_with_baseline as compare_legacy_baseline,
    baseline_exists as legacy_baseline_exists,
    KNOWN_PROJECTS
)

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
APP_VERSION = "3.1.0"  # Updated version with multi-baseline support

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
st.set_page_config(
    page_title="Provar Failure Analyzer Pro",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .section-divider {
        height: 2px;
        background: linear-gradient(to right, #667eea, #764ba2);
        margin: 2rem 0;
    }
    .real-failure {
        border-left: 4px solid #FF4B4B;
        padding-left: 1rem;
        margin: 0.5rem 0;
    }
    .skipped-failure {
        border-left: 4px solid #FFA500;
        padding-left: 1rem;
        margin: 0.5rem 0;
        opacity: 0.7;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR - NAVIGATION
# -----------------------------------------------------------
with st.sidebar:
    st.markdown("# 🔬 Provar Analyzer Pro")
    st.markdown(f"**Version:** {APP_VERSION}")
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["📊 Provar XML Analyzer", "🤖 AutomationAPI Analyzer", "📈 Baseline Tracker", "ℹ️ About"],
        key="navigation"
    )
    
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    
    # Admin key for baseline operations
    admin_key = st.text_input(
        "🔐 Admin Key",
        type="password",
        help="Required for saving/managing baselines"
    )
    
    # AI Settings
    use_ai = st.checkbox("🤖 Enable AI Analysis", value=True)
    
    if use_ai:
        enable_jira_generation = st.checkbox("📝 Enable Jira Ticket Generation", value=True)
        enable_test_improvements = st.checkbox("💡 Enable Test Improvements", value=True)
    else:
        enable_jira_generation = False
        enable_test_improvements = False

# -----------------------------------------------------------
# PAGE 1: PROVAR XML ANALYZER
# -----------------------------------------------------------
if page == "📊 Provar XML Analyzer":
    st.markdown('<div class="main-header">📊 Provar XML Failure Analyzer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload Provar XML reports to analyze failures and compare with baselines</div>', unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "📁 Upload Provar XML Files",
        type=['xml'],
        accept_multiple_files=True,
        help="Upload one or more Provar test result XML files"
    )
    
    if uploaded_files:
        if 'results' not in st.session_state:
            st.session_state.results = []
        
        # Process files button
        if st.button("🔄 Process Files", type="primary"):
            st.session_state.results = []
            
            with st.spinner("Processing XML files..."):
                for file in uploaded_files:
                    failures = safe_extract_failures(file)
                    
                    if failures:
                        project = detect_project(
                            failures[0].get('path', ''),
                            file.name
                        )
                        
                        # Compare with latest baseline using new engine
                        new_failures, existing_failures = compare_with_baseline(
                            project,
                            failures
                        )
                        
                        st.session_state.results.append({
                            'filename': file.name,
                            'project': project,
                            'failures': failures,
                            'new_failures': new_failures,
                            'existing_failures': existing_failures,
                            'new_count': len(new_failures),
                            'existing_count': len(existing_failures),
                            'total_count': len(failures)
                        })
        
        # Display results
        if st.session_state.results:
            st.success(f"✅ Processed {len(st.session_state.results)} file(s)")
            
            # Overall summary
            total_new = sum(r['new_count'] for r in st.session_state.results)
            total_existing = sum(r['existing_count'] for r in st.session_state.results)
            total_failures = sum(r['total_count'] for r in st.session_state.results)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Files Processed", len(st.session_state.results))
            with col2:
                st.metric("🆕 New Failures", total_new)
            with col3:
                st.metric("♻️ Existing Failures", total_existing)
            with col4:
                st.metric("📊 Total Failures", total_failures)
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            # Comparison chart
            render_comparison_chart(st.session_state.results)
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            # Individual file results
            for idx, result in enumerate(st.session_state.results):
                with st.expander(
                    f"📄 {result['filename']} — Project: {result['project']} | "
                    f"New: {result['new_count']} | Existing: {result['existing_count']} | "
                    f"Total: {result['total_count']}",
                    expanded=True
                ):
                    render_summary_card(
                        result['filename'],
                        result['new_count'],
                        result['existing_count'],
                        result['total_count']
                    )
                    
                    st.markdown("---")
                    
                    # Baseline selection for comparison
                    st.markdown("### 🎯 Baseline Selection")
                    baselines = list_baselines(result['project'])
                    
                    if baselines:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            selected_baseline = st.selectbox(
                                "Compare with baseline:",
                                options=['Latest'] + [b['id'] for b in baselines],
                                format_func=lambda x: f"Latest ({baselines[0]['label']})" if x == 'Latest' else f"{[b for b in baselines if b['id'] == x][0]['label']} ({[b for b in baselines if b['id'] == x][0]['created_at']})",
                                key=f"baseline_select_{idx}"
                            )
                        
                        with col2:
                            if st.button("🔄 Recompare", key=f"recompare_{idx}"):
                                baseline_id = None if selected_baseline == 'Latest' else selected_baseline
                                new_f, existing_f = compare_with_baseline(
                                    result['project'],
                                    result['failures'],
                                    baseline_id
                                )
                                result['new_failures'] = new_f
                                result['existing_failures'] = existing_f
                                result['new_count'] = len(new_f)
                                result['existing_count'] = len(existing_f)
                                st.rerun()
                        
                        st.info(f"📊 {len(baselines)} baseline(s) available for {result['project']}")
                    else:
                        st.warning(f"⚠️ No baseline found for {result['project']}")
                    
                    st.markdown("---")
                    
                    # Display failures
                    tabs = st.tabs(["🆕 New Failures", "♻️ Existing Failures", "📊 All Failures"])
                    
                    with tabs[0]:
                        if result['new_failures']:
                            st.markdown(f"**{len(result['new_failures'])} new failure(s) detected**")
                            for i, failure in enumerate(result['new_failures']):
                                with st.expander(f"❌ {i+1}. {failure.get('testcase', 'Unknown')}"):
                                    st.write("**Test Case:**", failure.get('testcase'))
                                    st.write("**Path:**", shorten_project_cache_path(failure.get('path')))
                                    st.error(f"**Error:** {failure.get('error')}")
                                    
                                    if 'stack_trace' in failure:
                                        with st.expander("🔍 Stack Trace"):
                                            st.code(failure['stack_trace'], language="text")
                                    
                                    # AI Analysis
                                    if use_ai:
                                        with st.expander("🤖 AI Analysis"):
                                            with st.spinner("Analyzing..."):
                                                ai_summary = generate_ai_summary(
                                                    failure.get('testcase'),
                                                    failure.get('error'),
                                                    failure.get('stack_trace', '')
                                                )
                                                st.info(ai_summary)
                        else:
                            st.success("✅ No new failures detected!")
                    
                    with tabs[1]:
                        if result['existing_failures']:
                            st.markdown(f"**{len(result['existing_failures'])} existing (baselined) failure(s)**")
                            for i, failure in enumerate(result['existing_failures']):
                                with st.expander(f"⚠️ {i+1}. {failure.get('testcase', 'Unknown')}"):
                                    st.write("**Test Case:**", failure.get('testcase'))
                                    st.write("**Path:**", shorten_project_cache_path(failure.get('path')))
                                    st.warning(f"**Error:** {failure.get('error')}")
                        else:
                            st.info("ℹ️ No existing failures")
                    
                    with tabs[2]:
                        st.markdown(f"**{len(result['failures'])} total failure(s)**")
                        df = pd.DataFrame(result['failures'])
                        st.dataframe(df, use_container_width=True)
                    
                    st.markdown("---")
                    
                    # Baseline Management
                    st.markdown("### 🛠️ Baseline Management")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        baseline_label = st.text_input(
                            "Baseline Label",
                            value="Auto",
                            key=f"label_{idx}"
                        )
                    
                    with col2:
                        if st.button(f"💾 Save as New Baseline", key=f"save_{idx}"):
                            if not admin_key:
                                st.error("❌ Admin key required!")
                            else:
                                expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
                                if admin_key == expected_key:
                                    try:
                                        baseline_id = save_baseline(
                                            result['project'],
                                            result['failures'],
                                            baseline_label
                                        )
                                        st.success(f"✅ Baseline saved! ID: {baseline_id}")
                                        st.info(f"📊 This project now has {len(list_baselines(result['project']))} baseline(s)")
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                                else:
                                    st.error("❌ Invalid admin key")
                    
                    with col3:
                        # Show baseline stats
                        stats = get_baseline_stats(result['project'])
                        st.metric("Saved Baselines", stats['count'])
                    
                    # Export options
                    st.markdown("### 📤 Export Options")
                    if result['failures']:
                        export_data = pd.DataFrame(result['failures'])
                        csv = export_data.to_csv(index=False)
                        st.download_button(
                            label="📥 Download as CSV",
                            data=csv,
                            file_name=f"{result['filename']}_failures.csv",
                            mime="text/csv",
                            key=f"export_{idx}"
                        )
    
    else:
        st.info("👆 Upload Provar XML files to begin analysis")

# -----------------------------------------------------------
# PAGE 2: AUTOMATIONAPI ANALYZER
# -----------------------------------------------------------
elif page == "🤖 AutomationAPI Analyzer":
    st.markdown('<div class="main-header">🤖 AutomationAPI Analyzer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Upload AutomationAPI XML reports for spec-based failure analysis</div>', unsafe_allow_html=True)
    
    # ... (keep existing AutomationAPI analyzer code)
    st.info("AutomationAPI Analyzer - Feature implementation continues here...")

# -----------------------------------------------------------
# PAGE 3: BASELINE TRACKER
# -----------------------------------------------------------
elif page == "📈 Baseline Tracker":
    render_baseline_tracker_dashboard()

# -----------------------------------------------------------
# PAGE 4: ABOUT
# -----------------------------------------------------------
elif page == "ℹ️ About":
    st.markdown('<div class="main-header">ℹ️ About Provar Analyzer Pro</div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    ### Version {APP_VERSION}
    
    #### 🆕 What's New in v3.1.0
    - **Multi-Baseline Support**: Store up to 10 baselines per project
    - **Baseline Comparison**: Compare any two baselines to track changes
    - **Enhanced Dashboard**: View all baselines with detailed statistics
    - **Backward Compatible**: Works with existing single-baseline projects
    
    #### Features
    - 📊 **Provar XML Analysis**: Parse and analyze Provar test results
    - 🤖 **AutomationAPI Support**: Spec-based failure analysis
    - 📈 **Multi-Baseline Tracking**: Store and compare multiple baselines
    - 🤖 **AI-Powered Analysis**: Get intelligent insights on failures
    - 📝 **Jira Integration**: Generate Jira tickets automatically
    - 💡 **Test Improvements**: Receive suggestions for test optimization
    
    #### How to Use Multi-Baseline Feature
    1. Upload XML reports in the analyzer
    2. Save reports as baselines with custom labels
    3. System automatically maintains up to 10 most recent baselines
    4. Use Baseline Tracker to view, compare, and manage baselines
    5. Compare current reports with any saved baseline
    
    #### Support
    For issues or questions, please contact your QA team.
    """)
    
    st.markdown("---")
    st.markdown("**Built with ❤️ using Streamlit**")