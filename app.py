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

# ===================================================================
def extract_project_from_baseline_name(baseline_name: str) -> str:
    """
    Extract logical project name from baseline filename.

    Example:
    AutomationAPI_Flexi1_automation_api_baseline_20260105_164029.json
    -> Flexi1
    """
    name = baseline_name.replace(".json", "")
    parts = name.split("_")

    # Expected pattern:
    # AutomationAPI_<PROJECT>_automation_api_baseline_<timestamp>
    try:
        return parts[1]
    except IndexError:
        return "UNKNOWN_PROJECT"

# ===================================================================
# Constants
APP_VERSION = "4.0.0"
def extract_provar_project_from_baseline(filename: str) -> str:
    """
    Extract EXACT Provar project name from baseline filename.

    Provar_Smoke_CC_Windows_provar_baseline_20260105_083448.json
    -> Smoke_CC_Windows
    """
    name = filename.replace(".json", "")

    if not name.lower().startswith("provar_"):
        return "UNKNOWN_PROJECT"

    name = name[len("provar_"):]  # remove prefix
    parts = name.split("_")

    project_parts = []
    for part in parts:
        if part.lower() in {"provar", "baseline"}:
            break
        project_parts.append(part)

    return "_".join(project_parts) if project_parts else "UNKNOWN_PROJECT"


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
        'provar': {'icon': '🔍', 'label': 'Provar Reports'},
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
    st.markdown("### 🔗 GitHub Status")
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
    
    admin_key = st.text_input("🔑 Admin Key", type="password", key="admin_key_input")
    
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
    'provar': ('🔍 Provar Reports', 'Analyze Provar XML reports'),
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
            st.metric("🔍 Provar Baselines", len(provar_files))
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
        if st.button("🔍 Analyze Provar", use_container_width=True, type="primary"):
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
# BASELINES PAGE SECTION
# ===================================================================
elif current_page == 'baselines':
    st.markdown("## 📈 Baseline Tracker")
    
    # Platform Selection
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        platform_filter = st.selectbox(
            "Select Platform",
            options=['provar', 'automation_api'],
            format_func=lambda x: '🔍 Provar Baselines' if x == 'provar' else '🔧 AutomationAPI Baselines',
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
        if st.button("📡 Sync GitHub", use_container_width=True):
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
        except Exception as e:
            st.error(f"Failed to load baselines: {e}")
            all_baselines = []
    
    # Overall Statistics - Compact
    if all_baselines:
        # Group baselines by project first
        baselines_by_project = {}

        
        for baseline in all_baselines:
            if platform_filter == "provar":
                project_name = extract_provar_project_from_baseline(baseline["name"])
            else:
                if platform_filter == "automation_api":
                    project_name = baseline.get("project")
                    if not project_name:
                       project_name = extract_project_from_baseline_name(baseline["name"])


            baselines_by_project.setdefault(project_name, []).append(baseline)



            if project_name not in baselines_by_project:
                baselines_by_project[project_name] = []
            baselines_by_project[project_name].append(baseline)

        for project in baselines_by_project:
            def extract_ts(name):
                try:
                    return name.split("_")[-1].replace(".json", "")
                except:
                    return ""

            baselines_by_project[project].sort(
                key=lambda b: extract_ts(b['name']),
                reverse=True
            )


        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📋 Total Baselines", len(all_baselines))
        
        with col2:
            st.metric("🏢 Projects", len(baselines_by_project))
        
        with col3:
            if all_baselines:
                latest = all_baselines[0]
                latest_time = _format_time(latest['name'].split('_')[-1].replace('.json', ''))
                st.metric("🕐 Latest", latest_time)
        
        with col4:
            platform_icon = "🔍" if platform_filter == "provar" else "🔧"
            st.metric("🔧 Platform", f"{platform_icon} {platform_filter.title()}")
        
        st.markdown("---")
        
        # Display baselines grouped by project
        st.markdown(f"### 📂 Baselines by Project ({len(baselines_by_project)} projects)")
        
        # Add custom CSS for compact view
        st.markdown("""
        <style>
        .compact-baseline {
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display each project as a collapsible section
        for project_name, project_baselines in sorted(baselines_by_project.items()):
            with st.expander(
                f"📁 {project_name} ({len(project_baselines)} baseline(s))",
                expanded=False
            ):
                # Show project summary
                total_failures_in_project = 0
                for baseline in project_baselines:
                    try:
                        baseline_data = baseline_service.load(baseline['name'], platform=platform_filter)
                        if baseline_data and 'failures' in baseline_data:
                            total_failures_in_project += len(baseline_data['failures'])
                    except:
                        pass
                
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"📊 Total Failures: **{total_failures_in_project}**")
                with col2:
                    st.caption(f"📅 Latest: **{_format_time(project_baselines[0]['name'].split('_')[-1].replace('.json', ''))}**")
                
                st.markdown("---")
                
                # Baseline selector dropdown
                baseline_options = [b['name'] for b in project_baselines]
                selected_baseline_name = st.selectbox(
                    "Select Baseline to View",
                    options=baseline_options,
                    format_func=lambda x: f"📅 {_format_time(x.split('_')[-1].replace('.json', ''))} ({x.split('_')[0]})",
                    key=f"baseline_selector_{project_name}"
                )
                
                # Find the selected baseline
                selected_baseline = next((b for b in project_baselines if b['name'] == selected_baseline_name), None)
                
                if selected_baseline:
                    # Load baseline data
                    try:
                        baseline_data = baseline_service.load(selected_baseline['name'], platform=platform_filter)
                        has_data = baseline_data and 'failures' in baseline_data
                        failure_count = len(baseline_data['failures']) if has_data else 0
                    except:
                        has_data = False
                        failure_count = 0
                    
                    st.markdown("---")
                    
                    # Compact info display
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        st.markdown(f"**📄 {selected_baseline['name'][:60]}**")
                        st.caption(f"🕐 {_format_time(selected_baseline['name'].split('_')[-1].replace('.json', ''))}")
                    
                    with col2:
                        st.metric("❌ Failures", failure_count)
                    
                    with col3:
                        if has_data and failure_count > 0:
                            failures = baseline_data.get('failures', [])
                            df = pd.DataFrame(failures)
                            csv = df.to_csv(index=False)
                            st.download_button(
                                "📥 CSV",
                                csv,
                                file_name=f"{selected_baseline['name']}_failures.csv",
                                mime="text/csv",
                                key=f"export_{selected_baseline['name']}",
                                use_container_width=True
                            )
                    
                    with col4:
                        if st.button("🗑️", key=f"delete_{selected_baseline['name']}", help="Delete Baseline", use_container_width=True):
                            if admin_key:
                                baseline_service.delete(selected_baseline['name'], platform=platform_filter)
                                st.success("✅ Deleted!")
                                load_cached_baselines.clear()
                                st.rerun()
                            else:
                                st.error("❌ Admin key required!")
                    
                    # View failures section
                    if has_data and failure_count > 0:
                        st.markdown("---")
                        
                        view_key = f"show_failures_{selected_baseline['name']}"
                        
                        if st.button(f"👁️ View {failure_count} Failures", key=f"view_btn_{selected_baseline['name']}", use_container_width=True):
                            st.session_state[view_key] = not st.session_state.get(view_key, False)
                        
                        if st.session_state.get(view_key, False):
                            st.markdown("### 📋 Failure Details")
                            
                            failures = baseline_data.get('failures', [])
                            
                            # Display based on platform
                            if platform_filter == "provar":
                                for i, f in enumerate(failures):
                                    with st.expander(f"{i+1}. {f.get('testcase', 'Unknown')}", expanded=False):
                                        st.write("**Error:**", f.get('error', 'N/A'))
                                        st.write("**Browser:**", f.get('webBrowserType', 'N/A'))
                                        st.code(f.get('details', 'No details'), language="text")
                            
                            else:  # automation_api
                                for i, f in enumerate(failures):
                                    icon = "🟡" if f.get('is_skipped') else "🔴"
                                    with st.expander(f"{icon} {i+1}. {f.get('test_name', 'Unknown')}", expanded=False):
                                        st.write("**Error:**", f.get('error_summary', 'N/A'))
                                        st.write("**Spec:**", f.get('spec_file', 'N/A'))
                                        st.code(f.get('error_details', 'No details'), language="text")
                            
                            if st.button("❌ Close Failures", key=f"close_{selected_baseline['name']}"):
                                st.session_state[view_key] = False
                                st.rerun()
                
                # Show all baselines in this project (compact list)
                st.markdown("---")
                st.markdown("**📜 All Baselines in this Project:**")
                
                for idx, baseline in enumerate(project_baselines):
                    timestamp = _format_time(baseline['name'].split('_')[-1].replace('.json', ''))
                    
                    try:
                        baseline_data = baseline_service.load(baseline['name'], platform=platform_filter)
                        failure_count = len(baseline_data['failures']) if baseline_data and 'failures' in baseline_data else 0
                    except:
                        failure_count = 0
                    
                    col1, col2, col3 = st.columns([4, 1, 1])
                    
                    with col1:
                        st.caption(f"{idx+1}. 📅 {timestamp}")
                    
                    with col2:
                        st.caption(f"❌ {failure_count}")
                    
                    with col3:
                        if baseline['name'] == selected_baseline_name:
                            st.caption("✅ **Selected**")
                        else:
                            st.caption("")
    
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
            if st.button("🔍 Go to Provar Reports", use_container_width=True, type="primary"):
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
            st.rerun()
            # ===================================================================
# PROVAR REPORTS PAGE (OLD LOGIC - WORKING VERSION)
# ===================================================================

elif current_page == 'provar':
    st.markdown("## 🔍 Upload Provar XML Reports")
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
                    detected_project = failures[0].get("project", xml_file.name.replace(".xml", ""))

                    
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
                    
                    # -----------------------------------------------------------
                    # BASELINE COMPARISON LOGIC (FROM OLD APP.PY)
                    # -----------------------------------------------------------
                    baseline_exists_flag = False
                    new_f = []
                    existing_f = []

                    try:
                        # Get all baselines for this project from GitHub
                        github_files = baseline_service.list(
                            platform="provar",
                            project=detected_project
                        )
                        if github_files:
                            baseline_exists_flag = True
                            # Load the latest baseline (files are sorted by timestamp)
                            latest_file = github_files[0]
                            baseline_data = baseline_service.load(
                                latest_file['name'],
                                platform="provar"
                            )
                            if baseline_data and baseline_data.get('failures'):
                                # Compare with baseline
                                baseline_failures = baseline_data.get('failures', [])
                                # Create signature set from baseline
                                baseline_sigs = set()
                                for b in baseline_failures:
                                    sig = f"{b.get('testcase')}|{b.get('error')}"
                                    baseline_sigs.add(sig)
                                # Compare current failures
                                for failure in normalized:
                                    sig = f"{failure.get('testcase')}|{failure.get('error')}"
                                    if sig in baseline_sigs:
                                        existing_f.append(failure)
                                    else:
                                        new_f.append(failure)
                            else:
                                # Baseline exists but has no failures
                                new_f = normalized
                                existing_f = []
                        else:
                            # No baseline exists - all failures are new
                            baseline_exists_flag = False
                            new_f = normalized
                            existing_f = []
                    except Exception as e:
                        print(f"⚠️ Error loading baseline from GitHub: {e}")
                        import traceback
                        traceback.print_exc()
                        # If error, treat all as new
                        baseline_exists_flag = False
                        new_f = normalized
                        existing_f = []
                    # -----------------------------------------------------------
                    
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
        # DISPLAY PROVAR RESULTS (OLD LOGIC)
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
                    f"📄 {result['filename']} | ⏰ {formatted_time} — Project: {result['project']}",
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
                    
                    # Multi-baseline selection (if enabled)
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
                        
                        # Multi-baseline save
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
                            # Legacy baseline save
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
                                                    label=None
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

            # ===================================================================
# AUTOMATION API REPORTS PAGE
# ===================================================================

elif current_page == 'automation_api':
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

                        # Filter out metadata record
                        real_failures = [f for f in failures if not f.get("_no_failures")]
                        
                        # Load baseline from GitHub using BaselineService
                        baseline_exists_flag = False
                        new_f = []
                        existing_f = []
                        
                        try:
                            # Get all baselines for this project from GitHub
                            github_files = baseline_service.list(
                                platform="automation_api",
                                project=project
                            )
                            if github_files:
                                baseline_exists_flag = True
                                # Load the latest baseline (files are sorted by timestamp)
                                latest_file = github_files[0]
                                baseline_data = baseline_service.load(
                                    latest_file['name'],
                                    platform="automation_api"
                                )
                                if baseline_data and baseline_data.get('failures'):
                                    # Compare with baseline
                                    baseline_failures = baseline_data.get('failures', [])
                                    # Create signature set from baseline
                                    def automation_failure_signature(f):
                                        interaction = f.get("interaction", {}) or {}
                                        return "|".join([
                                            f.get("spec_file", ""),
                                            f.get("test_name", ""),
                                            f.get("error_summary", ""),
                                            str(interaction.get("ActualValue", "")),
                                            str(interaction.get("ExpectedValue", "")),
                                        ])


                                    baseline_sigs = set()
                                    for b in baseline_failures:
                                        baseline_sigs.add(automation_failure_signature(b))

                                    for failure in real_failures:
                                        sig = automation_failure_signature(failure)
                                        if sig in baseline_sigs:
                                            existing_f.append(failure)
                                        else:
                                            new_f.append(failure)

                                else:           
                                    # Baseline exists but has no failures
                                    new_f = real_failures
                                    existing_f = []
                            else:  
                                # No baseline exists - all failures are new
                                baseline_exists_flag = False
                                new_f = real_failures
                                existing_f = []
                        except Exception as e:
                            print(f"⚠️ Error loading baseline from GitHub: {e}")
                            import traceback
                            traceback.print_exc()
                            # If error, treat all as new
                            baseline_exists_flag = False
                            new_f = real_failures
                            existing_f = []

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
                    
                    # ============================================================
                    # BASELINE COMPARISON SUMMARY
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
                    
                    st.markdown("---")
                    # ============================================================
                    # DETAILED FAILURES DISPLAY (GROUPED BY SPEC)
                    # ============================================================
                    
                    # Display failures grouped by spec
                    if result['grouped_failures']:
                        st.markdown("### 📋 All Failures (Grouped by Spec)")
                        
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
                                                        failure['error_details'],
                                                        ai_analysis if 'ai_analysis' in locals() else ""
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
                    
                    # ============================================================
                    # BASELINE MANAGEMENT WITH MULTI-BASELINE SUPPORT
                    # ============================================================
                    
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
                                    "Compare with baseline:",
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
                                            label=baseline_label if baseline_label else None
                                        )
                                        st.success(f"✅ Baseline saved to GitHub as {baseline_id}!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error: {str(e)}")
                                        import traceback
                                        st.code(traceback.format_exc())
                    
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
        # Welcome message when no files uploaded
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
        
        if API_MULTI_BASELINE_AVAILABLE:
            st.markdown("---")
            st.info("🆕 **Multi-Baseline Feature Available!** Store up to 10 baselines per project and compare any two baselines.")
        
        st.markdown("---")
        
        st.markdown("### 🆕 AI Features")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**🤖 AI Analysis**")
            st.write("Get intelligent failure analysis with Groq (FREE)")
        with col2:
            st.markdown("**📝 Jira Auto-Generation**")
            st.write("Create ready-to-use Jira tickets instantly")
        with col3:
            st.markdown("**💡 Test Improvements**")
            st.write("Get suggestions to make tests more stable")

# ===================================================================
# END OF AUTOMATION API REPORTS PAGE
# ===================================================================