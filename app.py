"""
Provar AI - Multi-Platform XML Analyzer (Refactored with Navigation)
Main application entry point
"""
import streamlit as st
import os

# Import services
from github_storage import GitHubStorage
from services.analysis_service import AnalysisService
from services.ai_service import AIService

# Import UI components
from ui.sidebar import render_sidebar, render_page_sidebar_content
from ui.navigation import NavigationMenu, NavigationState
from ui.pages import render_dashboard, render_trends, render_settings

# Import existing modules (keep backward compatibility)
from xml_extractor import extract_failed_tests
from automation_api_extractor import (
    extract_automation_api_failures,
    group_failures_by_spec,
    get_failure_statistics
)
import ai_reasoner
from baseline_manager import KNOWN_PROJECTS
from baseline_tracker_dashboard import render_baseline_tracker_dashboard

# -----------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------
APP_VERSION = "4.0.0"  # Updated version with navigation refactor

# Check for multi-baseline availability
try:
    from baseline_engine import baseline_exists as multi_baseline_exists
    MULTI_BASELINE_AVAILABLE = True
except ImportError:
    MULTI_BASELINE_AVAILABLE = False

try:
    from automation_api_baseline_engine import baseline_exists as api_baseline_exists_multi
    API_MULTI_BASELINE_AVAILABLE = True
except ImportError:
    API_MULTI_BASELINE_AVAILABLE = False

# -----------------------------------------------------------
# INITIALIZE SERVICES (CACHED)
# -----------------------------------------------------------
@st.cache_resource
def initialize_services():
    """Initialize all services (cached for performance)"""
    # GitHub Storage
    github = GitHubStorage(
        token=st.secrets.get("GITHUB_TOKEN"),
        repo_owner=st.secrets.get("GITHUB_OWNER"),
        repo_name=st.secrets.get("GITHUB_REPO")
    )

    
    # Analysis Service
    analysis_service = AnalysisService(baseline_service)
    
    # AI Service
    ai_service = AIService(ai_reasoner)
    
    return baseline_service, analysis_service, ai_service

# -----------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------
def detect_project(path: str, filename: str) -> str:
    """Detect project from path or filename"""
    for p in KNOWN_PROJECTS:
        if path and (f"/{p}" in path or f"\\{p}" in path):
            return p
        if p.lower() in filename.lower():
            return p
    if "datetime" in filename.lower():
        return "Date_Time"
    return "UNKNOWN_PROJECT"


def shorten_project_cache_path(path: str) -> str:
    """Shorten project cache path for display"""
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]


# -----------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------
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
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# INITIALIZE SERVICES
# -----------------------------------------------------------
baseline_service, analysis_service, ai_service = initialize_services()

# -----------------------------------------------------------
# AUTO SYNC BASELINES FROM GITHUB (ONCE PER SESSION)
# -----------------------------------------------------------
if "baselines_synced" not in st.session_state:
    try:
        synced = baseline_service.sync_from_github()
        st.session_state.baselines_synced = True
        if synced > 0:
            st.toast(f"🔄 {synced} baseline(s) synced from GitHub", icon="✅")
    except Exception as e:
        print(f"Auto-sync skipped: {e}")

# -----------------------------------------------------------
# INITIALIZE NAVIGATION
# -----------------------------------------------------------
NavigationState.initialize()

# -----------------------------------------------------------
# RENDER SIDEBAR
# -----------------------------------------------------------
sidebar_settings = render_sidebar(
    baseline_service=baseline_service,
    app_version=APP_VERSION,
    multi_baseline_available=MULTI_BASELINE_AVAILABLE,
    api_multi_baseline_available=API_MULTI_BASELINE_AVAILABLE
)

# Render page-specific sidebar content
page_sidebar_settings = render_page_sidebar_content(sidebar_settings['current_page'])
sidebar_settings.update(page_sidebar_settings)

# -----------------------------------------------------------
# MAIN CONTENT ROUTING
# -----------------------------------------------------------
current_page = sidebar_settings['current_page']

# Render page header
NavigationMenu.render_page_header(current_page)

# Route to appropriate page
if current_page == "dashboard":
    # Dashboard page
    render_dashboard(baseline_service)

elif current_page == "provar":
    # Provar Reports page
    from ui.provar_view import render_provar_analysis
    render_provar_analysis(
        analysis_service=analysis_service,
        ai_service=ai_service,
        baseline_service=baseline_service,
        sidebar_settings=sidebar_settings,
        extract_func=extract_failed_tests,
        detect_project_func=detect_project,
        shorten_path_func=shorten_project_cache_path
    )

elif current_page == "automation_api":
    # AutomationAPI Reports page
    from ui.api_view import render_api_analysis
    render_api_analysis(
        analysis_service=analysis_service,
        ai_service=ai_service,
        baseline_service=baseline_service,
        sidebar_settings=sidebar_settings,
        extract_func=extract_automation_api_failures,
        group_func=group_failures_by_spec,
        stats_func=get_failure_statistics
    )

elif current_page == "baselines":
    # Baseline Management page
    render_baseline_tracker_dashboard()

elif current_page == "trends":
    # Trends Analysis page
    render_trends(baseline_service)

elif current_page == "settings":
    # Settings page
    render_settings(baseline_service)

else:
    # Fallback
    st.error(f"Unknown page: {current_page}")
    st.info("Please use the navigation menu to select a valid page.")

# -----------------------------------------------------------
# FOOTER
# -----------------------------------------------------------
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.caption(f"🤖 Provar AI v{APP_VERSION}")

with col2:
    st.caption("Made with ❤️ using Streamlit")

with col3:
    if st.button("📚 Documentation", key="footer_docs", use_container_width=True):
        st.info("📚 Documentation coming soon!")
        