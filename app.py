"""
Provar AI - Multi-Platform XML Analyzer (Refactored)
Main application entry point
"""
import streamlit as st
import os

# Import services
from storage.baseline_service import BaselineService
from github_storage import GitHubStorage
from services.analysis_service import AnalysisService
from services.ai_service import AIService

# Import UI components
from ui.sidebar import render_sidebar
from ui.results_view import (
    format_execution_time,
    render_summary_card,
    render_overall_summary,
    render_failure_details,
    render_export_section,
    render_batch_ai_analysis
)

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
APP_VERSION = "3.3.0"  # Updated version with modular architecture

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
    
    # Baseline Service
    baseline_service = BaselineService(github)
    
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
    page_icon="🚀"
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
    </style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="main-header">🤖 Provar AI - Multi-Platform Report Analysis Tool</div>', 
    unsafe_allow_html=True
)

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
# RENDER SIDEBAR
# -----------------------------------------------------------
sidebar_settings = render_sidebar(
    baseline_service=baseline_service,
    app_version=APP_VERSION,
    multi_baseline_available=MULTI_BASELINE_AVAILABLE,
    api_multi_baseline_available=API_MULTI_BASELINE_AVAILABLE
)

# -----------------------------------------------------------
# MAIN CONTENT ROUTING
# -----------------------------------------------------------
report_type = sidebar_settings['report_type']

if report_type == "📈 Baseline Tracker":
    # Baseline Tracker Dashboard
    render_baseline_tracker_dashboard()

elif report_type == "Provar Regression Reports":
    # Import Provar-specific components
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

else:  # AutomationAPI Reports
    # Import AutomationAPI-specific components
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