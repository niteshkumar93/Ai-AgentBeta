"""
Provar AI - Multi-Platform XML Analyzer v4.0.0
Modern Navigation with All Existing Features Preserved
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime

# Storage and Services
from storage.baseline_service import BaselineService
from github_storage import GitHubStorage

# Initialize GitHub and Baseline Service
github = GitHubStorage(
    token=st.secrets.get("GITHUB_TOKEN"),
    repo_owner=st.secrets.get("GITHUB_OWNER"),
    repo_name=st.secrets.get("GITHUB_REPO")
)
baseline_service = BaselineService(github)

# Import extractors
from xml_extractor import extract_failed_tests
from automation_api_extractor import (
    extract_automation_api_failures,
    group_failures_by_spec,
    get_failure_statistics
)

# Import AI modules
from ai_reasoner import (
    generate_ai_summary,
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)

# Import baseline managers
from baseline_manager import (
    save_baseline,
    load_baseline,
    compare_with_baseline,
    baseline_exists as legacy_baseline_exists,
    KNOWN_PROJECTS
)

from automation_api_baseline_manager import (
    save_baseline as save_api_baseline,
    compare_with_baseline as compare_api_baseline,
    load_baseline as load_api_baseline,
    baseline_exists as api_baseline_exists
)

# Import dashboard
from baseline_tracker_dashboard import render_baseline_tracker_dashboard

# Multi-baseline engines (optional)
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

# Constants
APP_VERSION = "4.0.0"
# ===================================================================
# CACHING AND SESSION STATE INITIALIZATION
# ===================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_cached_baselines(platform, project=None):
    """Load baselines with caching to improve performance"""
    try:
        if project:
            return baseline_service.list(platform=platform, project=project)
        return baseline_service.list(platform=platform)
    except Exception as e:
        st.error(f"Error loading baselines: {e}")
        return []

@st.cache_data(ttl=300)
def get_baseline_projects(platform):
    """Get unique projects for a platform"""
    try:
        baselines = baseline_service.list(platform=platform)
        projects = set()
        for baseline in baselines:
            # Extract project from filename pattern: platform_project_timestamp
            parts = baseline['name'].split('_')
            if len(parts) >= 3:
                project = parts[1]
                projects.add(project)
        return sorted(list(projects))
    except Exception as e:
        return []

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'dashboard'

if 'baseline_platform_filter' not in st.session_state:
    st.session_state.baseline_platform_filter = 'provar'

if 'baselines_cache' not in st.session_state:
    st.session_state.baselines_cache = {}
# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def format_execution_time(raw_time: str):
    """Format timestamp from XML to readable format"""
    if raw_time in (None, "", "Unknown"):
        return "Unknown"
    
    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%a %b %d %H:%M:%S %Z %Y",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]
    
    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(raw_time, fmt)
            return dt.strftime("%d %b %Y, %H:%M UTC")
        except ValueError:
            continue
    
    return raw_time

def _format_time(ts: str):
    """Format timestamp string to readable format"""
    try:
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return ts

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

# ===================================================================
# PAGE CONFIGURATION
# ===================================================================

st.set_page_config(
    "Provar AI - Multi-Platform XML Analyzer",
    layout="wide",
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

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
    .nav-button {
        width: 100%;
        text-align: left;
        padding: 0.5rem 1rem;
        margin: 0.2rem 0;
        border-radius: 5px;
        border: none;
        background: transparent;
        cursor: pointer;
    }
    .nav-button:hover {
        background: #f0f2f6;
    }
    .nav-button-active {
        background: #e3f2fd;
        border-left: 4px solid #1f77b4;
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
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ===================================================================
# NAVIGATION INITIALIZATION
# ===================================================================

if 'current_page' not in st.session_state:
    st.session_state.current_page = 'dashboard'

# Auto-sync baselines from GitHub
if "baselines_synced" not in st.session_state:
    try:
        synced = baseline_service.sync_from_github()
        st.session_state.baselines_synced = True
        if synced > 0:
            st.toast(f"🔄 {synced} baseline(s) synced from GitHub", icon="✅")
    except Exception as e:
        print(f"Auto-sync skipped: {e}")

# ===================================================================
# SIDEBAR - NAVIGATION & SETTINGS
# ===================================================================

with st.sidebar:
    st.title("🤖 Provar AI")
    st.caption(f"v{APP_VERSION}")
    
    st.markdown("---")
    st.markdown("### 🧭 Navigation")
    
    # Navigation buttons
    pages = {
        'dashboard': {'icon': '📊', 'label': 'Dashboard'},
        'provar': {'icon': '📁', 'label': 'Provar Reports'},
        'automation_api': {'icon': '🔧', 'label': 'AutomationAPI Reports'},
        'baselines': {'icon': '📈', 'label': 'Baseline Tracker'},
        'settings': {'icon': '⚙️', 'label': 'Settings'}
    }
    
    for page_key, page_info in pages.items():
        is_active = st.session_state.current_page == page_key
        button_label = f"{page_info['icon']} {page_info['label']}"
        
        if st.button(
            button_label,
            key=f"nav_{page_key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
            disabled=is_active
        ):
            st.session_state.current_page = page_key
            st.rerun()
    
    st.markdown("---")
    
    # GitHub Connection Status
    st.markdown("### 🔍 GitHub Status")
    try:
        test_list = github.list_baselines()
        st.success(f"✅ Connected")
        st.caption(f"Found {len(test_list)} baseline(s)")
    except Exception as e:
        st.error("❌ Connection Failed")
        st.caption(str(e)[:50])
    
    if st.button("🔄 Sync from GitHub", use_container_width=True):
        with st.spinner("Syncing..."):
            synced = baseline_service.sync_from_github()
        st.success(f"✅ Synced {synced} baseline(s)")
        st.rerun()
    
    st.markdown("---")
    
    # AI Settings
    st.markdown("### 🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=False)
    
    with st.expander("🎯 Advanced AI"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", value=True)
        enable_jira_generation = st.checkbox("Jira Ticket Generation", value=True)
        enable_test_improvements = st.checkbox("Test Improvements", value=False)
    
    admin_key = st.text_input("🔐 Admin Key", type="password", key="admin_key_input")
    
    # Multi-baseline toggle
    if MULTI_BASELINE_AVAILABLE:
        st.markdown("---")
        use_multi_baseline = st.checkbox("🆕 Multi-Baseline Mode", value=True)
    else:
        use_multi_baseline = False
    
    st.markdown("---")
    
    # Upload Statistics
    if 'upload_stats' in st.session_state:
        st.markdown("### 📊 Stats")
        stats = st.session_state.upload_stats
        st.info(f"**Files:** {stats.get('count', 0)}")
        st.info(f"**Total Failures:** {stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {stats.get('new_failures', 0)}")
    
    # AI Status
    st.markdown("---")
    st.markdown("### 🤖 AI Status")
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if groq_key:
        st.success("✅ Groq AI")
    elif openai_key:
        st.info("ℹ️ OpenAI")
    else:
        st.warning("⚠️ No AI")

# ===================================================================
# MAIN CONTENT ROUTING
# ===================================================================

current_page = st.session_state.current_page

# Page Headers
page_headers = {
    'dashboard': ('📊 Dashboard', 'Overview and quick stats'),
    'provar': ('📁 Provar Reports', 'Analyze Provar XML reports'),
    'automation_api': ('🔧 AutomationAPI Reports', 'Analyze AutomationAPI XML reports'),
    'baselines': ('📈 Baseline Tracker', 'Manage and track baselines'),
    'settings': ('⚙️ Settings', 'Configure application settings')
}

if current_page in page_headers:
    header, description = page_headers[current_page]
    st.markdown(f'<div class="main-header">{header}</div>', unsafe_allow_html=True)
    st.caption(description)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ===================================================================
# DASHBOARD PAGE
# ===================================================================

if current_page == 'dashboard':
    st.markdown("## 📊 Overview")
    
    try:
        provar_files = baseline_service.list(platform="provar")
        api_files = baseline_service.list(platform="automation_api")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📁 Provar Baselines", len(provar_files))
        with col2:
            st.metric("🔧 API Baselines", len(api_files))
        with col3:
            st.metric("📊 Total Baselines", len(provar_files) + len(api_files))
        with col4:
            if 'upload_stats' in st.session_state:
                st.metric("🆕 Recent Uploads", st.session_state.upload_stats.get('count', 0))
            else:
                st.metric("🆕 Recent Uploads", 0)
    except Exception as e:
        st.error(f"Failed to load dashboard: {e}")
    
    st.markdown("---")
    st.markdown("## 📋 Recent Activity")
    
    if 'upload_stats' in st.session_state:
        stats = st.session_state.upload_stats
        st.info(f"""
        **Last Analysis:**
        - Files Analyzed: {stats.get('count', 0)}
        - Total Failures: {stats.get('total_failures', 0)}
        - New Failures: {stats.get('new_failures', 0)}
        """)
    else:
        st.info("No recent activity. Upload files to begin analysis.")
    
    st.markdown("---")
    st.markdown("## ⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📁 Analyze Provar", use_container_width=True, type="primary"):
            st.session_state.current_page = 'provar'
            st.rerun()
    with col2:
        if st.button("🔧 Analyze API", use_container_width=True, type="primary"):
            st.session_state.current_page = 'automation_api'
            st.rerun()
    with col3:
        if st.button("📈 View Baselines", use_container_width=True, type="primary"):
            st.session_state.current_page = 'baselines'
            st.rerun()

# ===================================================================
# BASELINES PAGE WITH PLATFORM FILTER AND CACHING
# ===================================================================

elif current_page == 'baselines':
    st.markdown("## 📈 Baseline Tracker")
    
    # Platform Selection with caching
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        platform_filter = st.selectbox(
            "Select Platform",
            options=['provar', 'automation_api'],
            format_func=lambda x: '📁 Provar Baselines' if x == 'provar' else '🔧 AutomationAPI Baselines',
            key='baseline_platform_selector',
            index=0 if st.session_state.baseline_platform_filter == 'provar' else 1
        )
        
        if platform_filter != st.session_state.baseline_platform_filter:
            st.session_state.baseline_platform_filter = platform_filter
            st.rerun()
    
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            load_cached_baselines.clear()
            get_baseline_projects.clear()
            st.rerun()
    
    with col3:
        if st.button("🔄 Sync GitHub", use_container_width=True):
            with st.spinner("Syncing..."):
                synced = baseline_service.sync_from_github()
                load_cached_baselines.clear()
                get_baseline_projects.clear()
            st.success(f"✅ Synced {synced} baseline(s)")
            st.rerun()
    
    st.markdown("---")
    
    # Load baselines with caching
    with st.spinner(f"Loading {platform_filter} baselines..."):
        try:
            all_baselines = load_cached_baselines(platform_filter)
            projects = get_baseline_projects(platform_filter)
        except Exception as e:
            st.error(f"Failed to load baselines: {e}")
            all_baselines = []
            projects = []
    
    # Overall Statistics
    st.markdown("### 📊 Overview")
    
    if all_baselines:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📋 Total Baselines", len(all_baselines))
        
        with col2:
            st.metric("🏢 Projects", len(projects))
        
        with col3:
            if all_baselines:
                latest = all_baselines[0]
                latest_time = _format_time(latest['name'].split('_')[-1].replace('.json', ''))
                st.metric("🕐 Latest", latest_time)
        
        with col4:
            platform_icon = "📁" if platform_filter == "provar" else "🔧"
            st.metric("🔧 Platform", f"{platform_icon} {platform_filter.title()}")
        
        st.markdown("---")
        
        # Project Filter
        st.markdown("### 🔍 Filter by Project")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            selected_project = st.selectbox(
                "Select Project",
                options=['All Projects'] + projects,
                key='project_filter_selector'
            )
        
        with col2:
            show_all = st.checkbox("Show All", value=False, key='show_all_baselines')
        
        # Filter baselines
        if selected_project != 'All Projects':
            filtered_baselines = [
                b for b in all_baselines 
                if selected_project in b['name']
            ]
        else:
            filtered_baselines = all_baselines
        
        # Limit display unless "Show All" is checked
        display_baselines = filtered_baselines if show_all else filtered_baselines[:20]
        
        st.markdown("---")
        
        # Display baselines
        st.markdown(f"### 📋 Baselines ({len(filtered_baselines)} total, showing {len(display_baselines)})")
        
        if not show_all and len(filtered_baselines) > 20:
            st.info(f"ℹ️ Showing first 20 of {len(filtered_baselines)} baselines. Check 'Show All' to see more.")
        
        # Group by project for better organization
        baselines_by_project = {}
        for baseline in display_baselines:
            # Extract project from filename
            parts = baseline['name'].split('_')
            if len(parts) >= 3:
                project = parts[1]
                if project not in baselines_by_project:
                    baselines_by_project[project] = []
                baselines_by_project[project].append(baseline)
        
        # Display by project
        for project, project_baselines in sorted(baselines_by_project.items()):
            st.markdown(f"#### 🏢 Project: {project}")
            
            for baseline in project_baselines:
                timestamp = _format_time(baseline['name'].split('_')[-1].replace('.json', ''))
                
                # ✅ Use expander for better layout
                with st.expander(f"📄 {baseline['name']} | 🕐 {timestamp}", expanded=False):
                    
                    # Load baseline data
                    try:
                        baseline_data = baseline_service.load(baseline['name'], platform=platform_filter)
                        has_data = baseline_data and 'failures' in baseline_data
                        failure_count = len(baseline_data['failures']) if has_data else 0
                    except:
                        has_data = False
                        failure_count = 0
                    
                    # Metrics row
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    
                    with col1:
                        st.metric("❌ Failures", failure_count)
                    
                    with col2:
                        st.caption(f"📅 {timestamp}")
                    
                    with col3:
                        # ✅ NEW: View Failures Button
                        view_key = f"view_state_{baseline['name']}"
                        btn_key = f"view_btn_{baseline['name']}"

                        if btn_key not in st.session_state:
                            st.session_state[view_key] = False

                        if st.button("👁️ View Failures", key=btn_key, use_container_width=True):
                            st.session_state[view_key] = not st.session_state[view_key]

                        if st.session_state[view_key]:
                            st.markdown("---")
                            st.markdown("### 📋 Failures")
      
                    with col4:
                        if st.button("🗑️", key=f"delete_{baseline['name']}", help="Delete"):
                            if admin_key:
                                baseline_service.delete(baseline['name'], platform=platform_filter)
                                st.success("✅ Deleted!")
                                load_cached_baselines.clear()
                                st.rerun()
                            else:
                                st.error("❌ Admin key required!")
                    
                    # ✅ NEW: Show failures if button clicked
                    if st.session_state.get(view_key, False):
                        st.markdown("---")
                        st.markdown("### 📋 Failures")
                        
                        if has_data and failure_count > 0:
                            failures = baseline_data.get('failures', [])
                            
                            # Display based on platform
                            if platform_filter == "provar":
                                for i, f in enumerate(failures):
                                    with st.expander(f"{i+1}. {f.get('testcase', 'Unknown')}", expanded=False):
                                        st.write("**Error:**", f.get('error', 'N/A'))
                                        st.code(f.get('details', 'No details'), language="text")
                            
                            else:  # automation_api
                                for i, f in enumerate(failures):
                                    with st.expander(f"{i+1}. {f.get('test_name', 'Unknown')}", expanded=False):
                                        st.write("**Error:**", f.get('error_summary', 'N/A'))
                                        st.code(f.get('error_details', 'No details'), language="text")
                            
                            # Export
                            df = pd.DataFrame(failures)
                            csv = df.to_csv(index=False)
                            st.download_button(
                                "📥 Download CSV",
                                csv,
                                file_name=f"{baseline['name']}_failures.csv",
                                mime="text/csv",
                                key=f"export_{baseline['name']}"
                            )
                        
                        if st.button("❌ Close", key=f"close_{baseline['name']}"):
                            st.session_state[view_key] = False
                            st.rerun()
                        if admin_key:
                            try:
                                baseline_service.delete(baseline['name'], platform=platform_filter)
                                st.success("✅ Deleted!")
                                load_cached_baselines.clear()
                                get_baseline_projects.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                        else:
                            st.error("❌ Admin key required!")
            
            st.markdown("---")
        
        # Bulk actions
        st.markdown("### 🛠️ Bulk Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Export All Metadata", use_container_width=True):
                metadata_list = []
                for baseline in filtered_baselines:
                    metadata_list.append({
                        'name': baseline['name'],
                        'platform': platform_filter,
                        'timestamp': _format_time(baseline['name'].split('_')[-1].replace('.json', ''))
                    })
                
                df = pd.DataFrame(metadata_list)
                csv = df.to_csv(index=False)
                
                st.download_button(
                    "📥 Download CSV",
                    csv,
                    file_name=f"{platform_filter}_baselines_metadata.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("🔄 Clear Cache", use_container_width=True):
                load_cached_baselines.clear()
                get_baseline_projects.clear()
                st.success("✅ Cache cleared!")
                st.rerun()
        
        with col3:
            if st.button("📊 View Statistics", use_container_width=True):
                st.session_state.show_stats = not st.session_state.get('show_stats', False)
        
        # Statistics panel
        if st.session_state.get('show_stats', False):
            st.markdown("---")
            st.markdown("### 📊 Detailed Statistics")
            
            total_failures = 0
            baseline_details = []
            
            for baseline in filtered_baselines[:50]:  # Limit to 50 for performance
                try:
                    baseline_data = baseline_service.load(baseline['name'], platform=platform_filter)
                    if baseline_data and 'failures' in baseline_data:
                        failure_count = len(baseline_data['failures'])
                        total_failures += failure_count
                        baseline_details.append({
                            'name': baseline['name'],
                            'failures': failure_count,
                            'timestamp': _format_time(baseline['name'].split('_')[-1].replace('.json', ''))
                        })
                except:
                    continue
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📊 Total Failures (Top 50)", total_failures)
            
            with col2:
                if baseline_details:
                    avg_failures = total_failures / len(baseline_details)
                    st.metric("📈 Avg Failures", f"{avg_failures:.1f}")
            
            with col3:
                if baseline_details:
                    max_failures = max(b['failures'] for b in baseline_details)
                    st.metric("🔥 Max Failures", max_failures)
            
            # Chart
            if baseline_details:
                st.markdown("#### 📈 Failure Trend (Top 50)")
                
                df_chart = pd.DataFrame(baseline_details)
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_chart['timestamp'],
                    y=df_chart['failures'],
                    mode='lines+markers',
                    name='Failures',
                    line=dict(color='#FF4B4B', width=2),
                    marker=dict(size=8)
                ))
                
                fig.update_layout(
                    title='Failure Trend Over Time',
                    xaxis_title='Timestamp',
                    yaxis_title='Number of Failures',
                    height=400,
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info(f"ℹ️ No baselines found for {platform_filter}")
        st.markdown("""
        ### 🚀 Get Started
        
        1. Upload XML reports in the **Provar Reports** or **AutomationAPI Reports** pages
        2. Analyze the failures
        3. Save a baseline to start tracking changes
        4. Come back here to view and manage your baselines
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📁 Go to Provar Reports", use_container_width=True, type="primary"):
                st.session_state.current_page = 'provar'
                st.rerun()
        
        with col2:
            if st.button("🔧 Go to AutomationAPI Reports", use_container_width=True, type="primary"):
                st.session_state.current_page = 'automation_api'
                st.rerun()
# ===================================================================
# SETTINGS PAGE
# ===================================================================

elif current_page == 'settings':
    st.markdown("## ⚙️ Application Settings")
    
    # GitHub Settings
    st.markdown("### 🔗 GitHub Integration")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Connection Status**")
        try:
            test_list = baseline_service.github.list_baselines()
            st.success(f"✅ Connected ({len(test_list)} baselines)")
        except Exception as e:
            st.error(f"❌ Failed: {str(e)[:50]}")
    
    with col2:
        st.markdown("**Repository Info**")
        try:
            st.info(f"Owner: {st.secrets.get('GITHUB_OWNER', 'Not set')}")
            st.info(f"Repo: {st.secrets.get('GITHUB_REPO', 'Not set')}")
        except:
            st.warning("GitHub credentials not configured")
    
    st.markdown("---")
    
    # AI Configuration
    st.markdown("### 🤖 AI Configuration")
    if groq_key:
        st.success("✅ Groq AI configured (Free)")
    elif openai_key:
        st.info("ℹ️ OpenAI configured (Paid)")
    else:
        st.warning("⚠️ No AI provider configured")
    
    st.markdown("---")
    
    # Data Management
    st.markdown("### 🗄️ Data Management")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Clear Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key != 'current_page':
                    del st.session_state[key]
            st.success("✅ Session cleared!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Sync All Baselines", use_container_width=True):
            with st.spinner("Syncing..."):
                synced = baseline_service.sync_from_github()
            st.success(f"✅ Synced {synced} baseline(s)")

# ===================================================================
# CORRECTED PROVAR REPORTS SECTION
# Replace the section starting from "elif current_page == 'provar':" 
# with this corrected version

elif current_page == 'provar':
    st.markdown("## 📁 Upload Provar XML Reports")
    st.markdown("Upload multiple JUnit XML reports from Provar test executions")
    
    uploaded_files = st.file_uploader(
        "Choose Provar XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="provar_uploader"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) uploaded!")
        
        if 'all_results' not in st.session_state:
            st.session_state.all_results = []
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_all = st.button("🔍 Analyze All", type="primary", use_container_width=True)
        
        if analyze_all:
            st.session_state.all_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, xml_file in enumerate(uploaded_files):
                status_text.text(f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_files)})")
                failures = safe_extract_failures(xml_file)
                
                if failures:
                    project_path = failures[0].get("projectCachePath", "")
                    detected_project = detect_project(project_path, xml_file.name)
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
                    
                    # Load baselines for this project
                    try:
                        available_baselines = load_cached_baselines("provar", detected_project)
                    except:
                        available_baselines = []
                    
                    # ✅ AUTOMATIC BASELINE COMPARISON
                        new_f = []
                        existing_f = []
                        baseline_compared = False

                        if available_baselines:
                            try:
                                latest_baseline = available_baselines[0]
                                baseline_data = baseline_service.load(latest_baseline['name'], platform="provar")
                                
                                if baseline_data and baseline_data.get('failures'):
                                    baseline_failures = baseline_data.get('failures', [])
                                    baseline_sigs = set()
                                    
                                    for b in baseline_failures:
                                        sig = f"{b.get('testcase')}|{b.get('error')}"
                                        baseline_sigs.add(sig)
                                    
                                    for failure in normalized:
                                        sig = f"{failure.get('testcase')}|{failure.get('error')}"
                                        if sig in baseline_sigs:
                                            existing_f.append(failure)
                                        else:
                                            new_f.append(failure)
                                    
                                    baseline_compared = True
                                else:
                                    new_f = normalized
                                    existing_f = []
                            except Exception as e:
                                print(f"Auto-comparison error: {e}")
                                new_f = normalized
                                existing_f = []
                        else:
                            new_f = normalized
                            existing_f = []

                        st.session_state.all_results.append({
                            'filename': xml_file.name,
                            'project': detected_project,
                            'all_failures': normalized,
                            'new_failures': new_f,  # ✅ Populated automatically
                            'existing_failures': existing_f,  # ✅ Populated automatically
                            'new_count': len(new_f),
                            'existing_count': len(existing_f),
                            'total_count': len(normalized),
                            'baseline_exists': len(available_baselines) > 0,
                            'available_baselines': available_baselines,
                            'execution_time': execution_time,
                            'baseline_compared': baseline_compared  # ✅ True if auto-compared
                        })
                
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.text("✅ Analysis complete!")
            progress_bar.empty()
            
            total_failures = sum(r['total_count'] for r in st.session_state.all_results)
            
            st.session_state.upload_stats = {
                'count': len(uploaded_files),
                'total_failures': total_failures,
                'new_failures': 0
            }
        
        # Display results
        if st.session_state.all_results:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            st.markdown("## 📊 Overall Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Files", len(st.session_state.all_results))
            with col2:
                total_new = sum(r['new_count'] for r in st.session_state.all_results)
                st.metric("🆕 New", total_new, delta=f"+{total_new}" if total_new > 0 else "0", delta_color="inverse")
            with col3:
                total_existing = sum(r['existing_count'] for r in st.session_state.all_results)
                st.metric("♻️ Known", total_existing)
            with col4:
                total_all = sum(r['total_count'] for r in st.session_state.all_results)
                st.metric("📈 Total", total_all)
            
            render_comparison_chart(st.session_state.all_results)
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("## 📋 Detailed Results")
            
            # MAIN LOOP FOR EACH FILE
            for idx, result in enumerate(st.session_state.all_results):
                formatted_time = format_execution_time(result.get("execution_time", "Unknown"))
                
                with st.expander(
                    f"📄 {result['filename']} | ⏰ {formatted_time} – {result['project']}",
                    expanded=False
                ):
                    # === BASELINE COMPARISON SECTION (TOP) ===
                    st.markdown("### 🎯 Baseline Comparison")
                    
                    if result['available_baselines']:
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            baseline_options = ['Select a baseline...'] + [
                                f"{b['name']} ({_format_time(b['name'].split('_')[-1].replace('.json', ''))})"
                                for b in result['available_baselines']
                            ]
                            
                            selected_baseline_display = st.selectbox(
                                "Compare with baseline:",
                                options=baseline_options,
                                key=f"baseline_select_{idx}",
                                index=0 if not result['baseline_compared'] else 1
                            )
                        
                        with col2:
                            if st.button("🔄 Compare", key=f"compare_{idx}", use_container_width=True):
                                if selected_baseline_display == 'Select a baseline...':
                                    st.warning("⚠️ Please select a baseline")
                                else:
                                    # Extract baseline name
                                    baseline_name = result['available_baselines'][
                                        baseline_options.index(selected_baseline_display) - 1
                                    ]['name']
                                    
                                    with st.spinner("Comparing..."):
                                        try:
                                            baseline_data = baseline_service.load(baseline_name, platform="provar")
                                            
                                            if baseline_data and baseline_data.get('failures'):
                                                baseline_failures = baseline_data.get('failures', [])
                                                baseline_sigs = set()
                                                for b in baseline_failures:
                                                    sig = f"{b.get('testcase')}|{b.get('error')}"
                                                    baseline_sigs.add(sig)
                                                
                                                new_f = []
                                                existing_f = []
                                                
                                                for failure in result['all_failures']:
                                                    sig = f"{failure.get('testcase')}|{failure.get('error')}"
                                                    if sig in baseline_sigs:
                                                        existing_f.append(failure)
                                                    else:
                                                        new_f.append(failure)
                                                
                                                result['new_failures'] = new_f
                                                result['existing_failures'] = existing_f
                                                result['new_count'] = len(new_f)
                                                result['existing_count'] = len(existing_f)
                                                result['baseline_compared'] = True
                                                
                                                st.success(f"✅ Compared with {baseline_name}")
                                                st.rerun()
                                            else:
                                                st.error("❌ Invalid baseline data")
                                        except Exception as e:
                                            st.error(f"❌ Comparison failed: {str(e)}")
                        
                        st.info(f"📊 {len(result['available_baselines'])} baseline(s) available for {result['project']}")
                    else:
                        st.warning(f"⚠️ No baselines found for project: {result['project']}")
                        st.caption("Save a baseline below to start tracking changes")
                    
                    st.markdown("---")
                    
                    # === SUMMARY CARDS (if baseline compared) ===
                    if result['baseline_compared']:
                        render_summary_card(
                            result['filename'],
                            result['new_count'],
                            result['existing_count'],
                            result['total_count']
                        )
                        st.markdown("---")
                    
                    # === TABS SECTION (SINGLE OCCURRENCE) ===
                    tab1, tab2, tab3 = st.tabs(["🆕 New Failures", "♻️ Known Failures", "⚙️ Actions"])
                    
                    with tab1:
                        if not result['baseline_compared']:
                            st.info("ℹ️ Select and compare with a baseline to see new failures")
                            # Show all failures if not compared yet
                            for i, f in enumerate(result['all_failures']):
                                with st.expander(f"📋 {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    st.code(f['details'], language="text")
                        elif result['new_count'] == 0:
                            st.success("✅ No new failures!")
                        else:
                            for i, f in enumerate(result['new_failures']):
                                with st.expander(f"🆕 {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    st.code(f['details'], language="text")
                                    
                                    if use_ai:
                                        with st.spinner("Analyzing..."):
                                            ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'])
                                            st.info(ai_analysis)
                                        
                                        if enable_jira_generation:
                                            if st.button("📝 Generate Jira", key=f"jira_{idx}_{i}"):
                                                jira_content = generate_jira_ticket(f['testcase'], f['error'], f['details'], ai_analysis)
                                                st.markdown(jira_content)
                                                st.download_button(
                                                    "📥 Download",
                                                    jira_content,
                                                    file_name=f"jira_{f['testcase'][:30]}.txt",
                                                    key=f"jira_dl_{idx}_{i}"
                                                )
                    
                    with tab2:
                        if not result['baseline_compared']:
                            st.info("ℹ️ Compare with a baseline to see known failures")
                        elif result['existing_count'] == 0:
                            st.info("ℹ️ No known failures")
                        else:
                            st.warning(f"Found {result['existing_count']} known failures")
                            for i, f in enumerate(result['existing_failures']):
                                with st.expander(f"♻️ {i+1}. {f['testcase']}", expanded=False):
                                    st.write("**Browser:**", f['webBrowserType'])
                                    st.code(f['testcase_path'], language="text")
                                    st.error(f"Error: {f['error']}")
                                    st.code(f['details'], language="text")
                    
                    with tab3:
                        st.markdown("### 🛠️ Baseline Management")
                        
                        selected_project = result['project']
                        if result['project'] == "UNKNOWN_PROJECT":
                            selected_project = st.selectbox(
                                "Choose project",
                                options=KNOWN_PROJECTS,
                                key=f"project_select_{idx}"
                            )
                        else:
                            st.info(f"Project: {result['project']}")
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            baseline_label = st.text_input(
                                "Label (optional)",
                                value="",
                                placeholder="e.g., Sprint 24, Pre-Release",
                                key=f"label_{idx}"
                            )
                        
                        with col2:
                            if st.button(f"💾 Save Baseline", key=f"save_{idx}", use_container_width=True):
                                if not admin_key:
                                    st.error("❌ Admin key required!")
                                else:
                                    try:
                                        baseline_id = baseline_service.save(
                                            project=selected_project,
                                            platform="provar",
                                            failures=result['all_failures'],
                                            label=baseline_label if baseline_label else None
                                        )
                                        st.success(f"✅ Saved! ID: {baseline_id}")
                                        # Clear cache
                                        load_cached_baselines.clear()
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                        
                        # Export
                        st.markdown("### 📤 Export")
                        export_data = pd.DataFrame(result['all_failures'])
                        if not export_data.empty:
                            csv = export_data.to_csv(index=False)
                            st.download_button(
                                "📥 Download CSV",
                                csv,
                                file_name=f"{result['filename']}_failures.csv",
                                mime="text/csv",
                                key=f"export_{idx}"
                            )
    
    else:
        st.info("👆 Upload Provar XML files to begin")
        
        st.markdown("### 🎯 Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**📊 Multi-File**")
            st.write("Analyze multiple reports")
        with col2:
            st.markdown("**🤖 AI Insights**")
            st.write("Intelligent analysis")
        with col3:
            st.markdown("**📈 Baselines**")
            st.write("Track changes over time")
# ===================================================================
# AUTOMATION API REPORTS PAGE
# ===================================================================

elif current_page == 'automation_api':
    st.markdown("## 🔧 Upload AutomationAPI XML Reports")
    st.markdown("Upload XML reports from AutomationAPI test executions")
    
    uploaded_api_files = st.file_uploader(
        "Choose AutomationAPI XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="api_uploader"
    )
    
    if uploaded_api_files:
        st.success(f"✅ {len(uploaded_api_files)} file(s) uploaded!")
        
        if 'api_results' not in st.session_state:
            st.session_state.api_results = []
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_api = st.button("🔍 Analyze All", type="primary", use_container_width=True)
        
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
                        real_failures = [f for f in failures if not f.get("_no_failures")]
                        
                        # Load baselines for this project
                        try:
                            available_baselines = load_cached_baselines("automation_api", project)
                        except:
                            available_baselines = []
                        
                        stats = get_failure_statistics(real_failures if real_failures else failures)
                        
                        # ✅ AUTOMATIC BASELINE COMPARISON
                        new_f = []
                        existing_f = []
                        baseline_compared = False

                        if available_baselines:
                            try:
                                latest_baseline = available_baselines[0]
                                baseline_data = baseline_service.load(latest_baseline['name'], platform="automation_api")
                                
                                if baseline_data and baseline_data.get('failures'):
                                    baseline_failures = baseline_data.get('failures', [])
                                    baseline_sigs = set()
                                    
                                    for b in baseline_failures:
                                        sig = f"{b.get('spec_file')}|{b.get('test_name')}|{b.get('error_summary', '')}"
                                        baseline_sigs.add(sig)
                                    
                                    for failure in real_failures:
                                        sig = f"{failure.get('spec_file')}|{failure.get('test_name')}|{failure.get('error_summary', '')}"
                                        if sig in baseline_sigs:
                                            existing_f.append(failure)
                                        else:
                                            new_f.append(failure)
                                    
                                    baseline_compared = True
                                else:
                                    new_f = real_failures
                                    existing_f = []
                            except Exception as e:
                                print(f"Auto-comparison error: {e}")
                                new_f = real_failures
                                existing_f = []
                        else:
                            new_f = real_failures
                            existing_f = []

                        st.session_state.api_results.append({
                            'filename': xml_file.name,
                            'project': project,
                            'all_failures': real_failures if real_failures else [],
                            'new_failures': new_f,  # ✅ Populated automatically
                            'existing_failures': existing_f,  # ✅ Populated automatically
                            'grouped_failures': group_failures_by_spec(real_failures) if real_failures else {},
                            'stats': stats,
                            'baseline_exists': len(available_baselines) > 0,
                            'available_baselines': available_baselines,
                            'timestamp': failures[0].get("timestamp", "Unknown") if failures else "Unknown",
                            'baseline_compared': baseline_compared  # ✅ True if auto-compared
                        })
                
                except Exception as e:
                    st.error(f"Error parsing {xml_file.name}: {str(e)}")
                
                progress_bar.progress((idx + 1) / len(uploaded_api_files))
            
            status_text.text("✅ Analysis complete!")
            progress_bar.empty()
            
            total_failures = sum(r['stats']['total_failures'] for r in st.session_state.api_results)
            
            st.session_state.upload_stats = {
                'count': len(uploaded_api_files),
                'total_failures': total_failures,
                'new_failures': 0
            }
        
        # Display results
        if st.session_state.api_results:
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("## 📊 Analysis Results")
            
            total_real = sum(r['stats']['real_failures'] for r in st.session_state.api_results)
            total_skipped = sum(r['stats']['skipped_failures'] for r in st.session_state.api_results)
            total_all = sum(r['stats']['total_failures'] for r in st.session_state.api_results)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📄 Files", len(st.session_state.api_results))
            with col2:
                st.metric("🔴 Real", total_real)
            with col3:
                st.metric("🟡 Skipped", total_skipped)
            with col4:
                st.metric("📈 Total", total_all)
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            # Individual results
            for idx, result in enumerate(st.session_state.api_results):
                with st.expander(
                    f"📄 {result['filename']} — {result['project']} | "
                    f"⏰ {result['timestamp']} | Failures: {result['stats']['total_failures']}",
                    expanded=False
                ):
                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("🔴 Real", result['stats']['real_failures'])
                    with col2:
                        st.metric("🟡 Skipped", result['stats']['skipped_failures'])
                    with col3:
                        st.metric("📋 Specs", result['stats']['unique_specs'])
                    with col4:
                        st.metric("⏱️ Time", f"{result['stats']['total_time']}s")
                    
                    st.markdown("---")
                    
                    # Baseline Comparison at the TOP
                    st.markdown("### 🎯 Baseline Comparison")
                    
                    if result['available_baselines']:
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            baseline_options = ['Select a baseline...'] + [
                                f"{b['name']} ({_format_time(b['name'].split('_')[-1].replace('.json', ''))})"
                                for b in result['available_baselines']
                            ]
                            
                            selected_baseline_display = st.selectbox(
                                "Compare with baseline:",
                                options=baseline_options,
                                key=f"api_baseline_select_{idx}",
                                index=0 if not result['baseline_compared'] else 1
                            )
                        
                        with col2:
                            if st.button("🔄 Compare", key=f"api_compare_{idx}", use_container_width=True):
                                if selected_baseline_display == 'Select a baseline...':
                                    st.warning("⚠️ Please select a baseline")
                                else:
                                    # Extract baseline name
                                    baseline_name = result['available_baselines'][
                                        baseline_options.index(selected_baseline_display) - 1
                                    ]['name']
                                    
                                    with st.spinner("Comparing..."):
                                        try:
                                            baseline_data = baseline_service.load(baseline_name, platform="automation_api")
                                            
                                            if baseline_data and baseline_data.get('failures'):
                                                baseline_failures = baseline_data.get('failures', [])
                                                baseline_sigs = set()
                                                for b in baseline_failures:
                                                    sig = f"{b.get('spec_file')}|{b.get('test_name')}|{b.get('error_summary', '')}"
                                                    baseline_sigs.add(sig)
                                                
                                                new_f = []
                                                existing_f = []
                                                
                                                for failure in result['all_failures']:
                                                    sig = f"{failure.get('spec_file')}|{failure.get('test_name')}|{failure.get('error_summary', '')}"
                                                    if sig in baseline_sigs:
                                                        existing_f.append(failure)
                                                    else:
                                                        new_f.append(failure)
                                                
                                                result['new_failures'] = new_f
                                                result['existing_failures'] = existing_f
                                                result['baseline_compared'] = True
                                                
                                                st.success(f"✅ Compared with {baseline_name}")
                                                st.rerun()
                                            else:
                                                st.error("❌ Invalid baseline data")
                                        except Exception as e:
                                            st.error(f"❌ Comparison failed: {str(e)}")
                        
                        st.info(f"📊 {len(result['available_baselines'])} baseline(s) available for {result['project']}")
                    else:
                        st.warning(f"⚠️ No baselines found for project: {result['project']}")
                        st.caption("Save a baseline below to start tracking changes")
                    
                    st.markdown("---")
                    # Display baseline comparison if done
                    if result['baseline_compared'] and (result['new_failures'] or result['existing_failures']):
                        st.markdown("### 📊 Comparison Results")
                        
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
                        
                        all_specs = set(new_by_spec.keys()) | set(existing_by_spec.keys())
                        new_specs = [s for s in new_by_spec.keys() if s not in existing_by_spec]
                        mixed_specs = [s for s in all_specs if s in new_by_spec and s in existing_by_spec]
                        existing_only_specs = [s for s in existing_by_spec.keys() if s not in new_by_spec]
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("🆕 New Specs", len(new_specs))
                        with col2:
                            st.metric("📊 Mixed", len(mixed_specs))
                        with col3:
                            st.metric("♻️ Known", len(existing_only_specs))
                        
                        st.markdown("---")
                        
                        # Tabs for organized display
                        tab1, tab2, tab3 = st.tabs(["🆕 New Failures", "♻️ Known Failures", "📋 All Failures"])
                        
                        with tab1:
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
                                            
                                            # ✅ CRITICAL: This expander MUST be at the same indentation level
                                            # as the for loop above it
                                            with st.expander(f"{icon} {i+1}. {failure['test_name']}", expanded=False):
                                                if failure.get('is_skipped'):
                                                    st.warning("⚠️ This test was skipped.")
                                                
                                                st.write("**Test:**", failure['test_name'])
                                                st.write("**Type:**", failure['failure_type'])
                                                st.write("**Time:**", f"{failure['execution_time']}s")
                                                st.error(f"**Error:** {failure['error_summary']}")
                                                
                                                # Details expander
                                                with st.expander("📋 Full Error Details"):
                                                    st.code(failure['error_details'], language="text")
                                                
                                                # Stack trace expander
                                                if failure.get('full_stack_trace'):
                                                    with st.expander("🔍 Stack Trace"):
                                                        st.code(failure['full_stack_trace'], language="text")


                                            if failure['is_skipped']:
                                                 st.warning("⚠️ This test was skipped.")
                                            
                                            st.write("**Test:**", failure['test_name'])
                                            st.write("**Type:**", failure['failure_type'])
                                            st.write("**Time:**", f"{failure['execution_time']}s")
                                            st.error(f"**Error:** {failure['error_summary']}")
                                            
                                             # Details expander - inside the failure expander
                                            with st.expander("📋 Full Error Details"):
                                                 st.code(failure['error_details'], language="text")
                                            
                                             # Stack trace expander - inside the failure expander
                                            if failure.get('full_stack_trace'):
                                                with st.expander("🔍 Stack Trace"):
                                                    st.code(failure['full_stack_trace'], language="text")
                            
                            if mixed_specs:
                                st.markdown("---")
                                st.markdown("#### 📊 Specs with New Failures")
                                for spec in sorted(mixed_specs):
                                    new_count = len(new_by_spec.get(spec, []))
                                    with st.expander(f"📊 {spec} — {new_count} new failures", expanded=False):
                                        for i, failure in enumerate(new_by_spec.get(spec, [])):
                                            icon = "🟡" if failure.get('is_skipped') else "🔴"
                                            # Each failure gets its own expander - MUST be indented here!
                                        with st.expander(f"{icon} {i+1}. {failure['test_name']}", expanded=False):
                                             if failure['is_skipped']:
                                                 st.warning("⚠️ This test was skipped.")
                                            
                                             st.write("**Test:**", failure['test_name'])
                                             st.write("**Type:**", failure['failure_type'])
                                             st.write("**Time:**", f"{failure['execution_time']}s")
                                             st.error(f"**Error:** {failure['error_summary']}")
                                            
                                             # Details expander - inside the failure expander
                                             with st.expander("📋 Full Error Details"):
                                                 st.code(failure['error_details'], language="text")
                                            
                                             # Stack trace expander - inside the failure expander
                                             if failure.get('full_stack_trace'):
                                                 with st.expander("🔍 Stack Trace"):
                                                     st.code(failure['full_stack_trace'], language="text")
                        
                        with tab2:
                            if existing_only_specs or mixed_specs:
                                for spec in sorted(set(existing_only_specs + mixed_specs)):
                                    existing_count = len(existing_by_spec.get(spec, []))
                                    if existing_count > 0:
                                        with st.expander(f"♻️ {spec} — {existing_count} known", expanded=False):
                                            for i, failure in enumerate(existing_by_spec.get(spec, [])):
                                                st.markdown(f"{i+1}. {failure['test_name']}")
                            else:
                                st.success("✅ No known failures")
                        
                        with tab3:
                            # Display grouped failures
                            for spec_name, spec_failures in result['grouped_failures'].items():
                                with st.expander(f"📋 {spec_name} — {len(spec_failures)} failures", expanded=False):
                                    for i, failure in enumerate(spec_failures):
                                        icon = "🟡" if failure['is_skipped'] else "🔴"
                                        # Each failure gets its own expander - MUST be indented here!
                                        with st.expander(f"{icon} {i+1}. {failure['test_name']}", expanded=False):
                                             if failure['is_skipped']:
                                                 st.warning("⚠️ This test was skipped.")
                                            
                                             st.write("**Test:**", failure['test_name'])
                                             st.write("**Type:**", failure['failure_type'])
                                             st.write("**Time:**", f"{failure['execution_time']}s")
                                             st.error(f"**Error:** {failure['error_summary']}")
                                            
                                             # Details expander - inside the failure expander
                                             with st.expander("📋 Full Error Details"):
                                                 st.code(failure['error_details'], language="text")
                                            
                                             # Stack trace expander - inside the failure expander
                                             if failure.get('full_stack_trace'):
                                                 with st.expander("🔍 Stack Trace"):
                                                     st.code(failure['full_stack_trace'], language="text")
                    else:
                        # Display all failures if not compared
                        st.markdown("### 📋 All Failures")
                        if result['grouped_failures']:
                            for spec_name, spec_failures in result['grouped_failures'].items():
                                with st.expander(f"📋 {spec_name} — {len(spec_failures)} failures", expanded=False):
                                    for i, failure in enumerate(spec_failures):
                                        icon = "🟡" if failure['is_skipped'] else "🔴"
                                        
                                        # Each failure gets its own expander - MUST be indented here!
                                        with st.expander(f"{icon} {i+1}. {failure['test_name']}", expanded=False):
                                             if failure['is_skipped']:
                                                 st.warning("⚠️ This test was skipped.")
                                            
                                             st.write("**Test:**", failure['test_name'])
                                             st.write("**Type:**", failure['failure_type'])
                                             st.write("**Time:**", f"{failure['execution_time']}s")
                                             st.error(f"**Error:** {failure['error_summary']}")
                                            
                                             # Details expander - inside the failure expander
                                             with st.expander("📋 Full Error Details"):
                                                 st.code(failure['error_details'], language="text")
                                            
                                             # Stack trace expander - inside the failure expander
                                             if failure.get('full_stack_trace'):
                                                 with st.expander("🔍 Stack Trace"):
                                                     st.code(failure['full_stack_trace'], language="text")
                                            
                                            # AI Analysis - inside the failure expander
                                             if use_ai and not failure['is_skipped']:
                                                 with st.spinner("Analyzing..."):
                                                     ai_analysis = generate_ai_summary(
                                                         failure['test_name'],
                                                         failure['error_summary'],
                                                         failure['error_details']
                                                     )
                                                     st.info(ai_analysis)
                # Baseline Management
                st.markdown("---")
                st.markdown("### 💾 Save Baseline")
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    baseline_label = st.text_input(
                        "Label (optional)",
                        value="",
                        placeholder="e.g., Sprint 24",
                        key=f"api_label_{idx}"
                    )
                
                with col2:
                    if st.button(f"💾 Save", key=f"api_save_{idx}", use_container_width=True):
                        if not admin_key:
                            st.error("❌ Admin key required!")
                        else:
                            try:
                                baseline_id = baseline_service.save(
                                    project=result['project'],
                                    platform="automation_api",
                                    failures=result['all_failures'],
                                    label=baseline_label if baseline_label else None
                                )
                                st.success(f"✅ Saved! ID: {baseline_id}")
                                # Clear cache
                                load_cached_baselines.clear()
                            except Exception as e:
                                st.error(f"❌ Error: {str(e)}")
                
                # Export
                st.markdown("### 📤 Export")
                if result['all_failures']:
                    export_data = pd.DataFrame(result['all_failures'])
                    csv = export_data.to_csv(index=False)
                    st.download_button(
                        "📥 Download CSV",
                        csv,
                        file_name=f"{result['filename']}_failures.csv",
                        mime="text/csv",
                        key=f"api_export_{idx}"
                    )

else:
    st.info("👆 Upload AutomationAPI XML files to begin")
    
    st.markdown("### 🎯 Features")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📋 Spec Grouping**")
        st.write("Organized by spec file")
    with col2:
        st.markdown("**🎨 Color Coding**")
        st.write("🔴 Real vs 🟡 Skipped")
    with col3:
        st.markdown("**📊 Statistics**")
        st.write("Detailed metrics")
# ===================================================================
# FOOTER
# ===================================================================

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.caption(f"🤖 Provar AI v{APP_VERSION}")

with col2:
    st.caption("Made with ❤️ using Streamlit")

with col3:
    if st.button("📚 Docs", key="footer_docs", use_container_width=True):
        st.info("📚 Documentation coming soon!")