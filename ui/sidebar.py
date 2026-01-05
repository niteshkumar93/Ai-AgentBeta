"""
Sidebar UI components with integrated navigation
"""
import streamlit as st
import os
from ui.navigation import NavigationMenu, QuickActions, NavigationState, apply_navigation_css


def render_sidebar(baseline_service, app_version: str, multi_baseline_available: bool, 
                   api_multi_baseline_available: bool) -> dict:
    """
    Render the complete sidebar with navigation
    
    Args:
        baseline_service: BaselineService instance
        app_version: Application version string
        multi_baseline_available: Whether multi-baseline is available
        api_multi_baseline_available: Whether API multi-baseline is available
        
    Returns:
        Dictionary with sidebar settings including selected page
    """
    # Apply custom CSS
    apply_navigation_css()
    
    # Initialize navigation state
    NavigationState.initialize()
    
    with st.sidebar:
        # App branding
        st.markdown("# 🤖 Provar AI")
        st.caption(f"v{app_version}")
        
        # Navigation Menu
        current_page = NavigationMenu.render_navigation()
        
        # Quick Actions
        QuickActions.render_quick_actions()
        
        st.markdown("---")
        
        # GitHub Connection Status
        _render_github_status(baseline_service)
        
        st.markdown("---")
        
        # AI Features (only show on relevant pages)
        ai_settings = {}
        if current_page in ['provar', 'automation_api']:
            ai_settings = _render_ai_settings()
        
        # Admin Key (only show on relevant pages)
        admin_key = ""
        if current_page in ['provar', 'automation_api', 'baselines']:
            admin_key = st.text_input(
                "🔐 Admin Key", 
                type="password", 
                help="Required for saving baselines", 
                key="admin_key_input"
            )
        
        # Multi-baseline toggle (only show on relevant pages)
        use_multi_baseline = False
        if multi_baseline_available and current_page in ['provar', 'automation_api', 'baselines']:
            st.markdown("---")
            st.subheader("🆕 Multi-Baseline")
            use_multi_baseline = st.checkbox(
                "Enable Multi-Baseline (NEW)",
                value=True,
                help="Store up to 10 baselines per project (recommended)"
            )
        
        st.markdown("---")
        
        # Status Section
        _render_status_section(app_version, multi_baseline_available, use_multi_baseline)
        
        # Reset Button
        if st.button("🔄 Reset All", type="secondary", use_container_width=True, 
                    help="Clear all data and start fresh"):
            _reset_app()
        
        st.markdown("---")
        
        # Statistics (only show on analysis pages)
        if current_page in ['provar', 'automation_api', 'dashboard']:
            _render_statistics()
        
        # AI Status
        if current_page in ['provar', 'automation_api', 'settings']:
            _render_ai_status()
        
        # Store baseline_service in session state for quick actions
        st.session_state.baseline_service = baseline_service
        
        return {
            'current_page': current_page,
            'admin_key': admin_key,
            'use_multi_baseline': use_multi_baseline,
            **ai_settings
        }


def _render_github_status(baseline_service):
    """Render GitHub connection status"""
    st.markdown("### 🔍 GitHub Status")
    
    try:
        test_list = baseline_service.github.list_baselines("provar")
        st.success(f"✅ Connected")
        st.caption(f"{len(test_list)} baseline(s)")
    except Exception as e:
        st.error("❌ Connection Failed")
        with st.expander("🔧 Debug Info"):
            st.code(str(e), language="text")
            _show_secret_status()


def _show_secret_status():
    """Show GitHub secret configuration status"""
    secrets_status = []
    
    if st.secrets.get("GITHUB_TOKEN"):
        secrets_status.append("✅ Token")
    else:
        secrets_status.append("❌ Token")
    
    if st.secrets.get("GITHUB_OWNER"):
        secrets_status.append(f"✅ Owner: {st.secrets.get('GITHUB_OWNER')}")
    else:
        secrets_status.append("❌ Owner")
    
    if st.secrets.get("GITHUB_REPO"):
        secrets_status.append(f"✅ Repo: {st.secrets.get('GITHUB_REPO')}")
    else:
        secrets_status.append("❌ Repo")
    
    for status in secrets_status:
        st.caption(status)


def _render_ai_settings():
    """Render AI settings section"""
    st.markdown("---")
    st.subheader("🤖 AI Features")
    
    use_ai = st.checkbox(
        "Enable AI Analysis", 
        value=False, 
        help="Use Groq AI for intelligent failure analysis"
    )
    
    # Advanced AI Features
    enable_batch_analysis = False
    enable_jira_generation = False
    enable_test_improvements = False
    
    if use_ai:
        with st.expander("🎯 Advanced AI Features"):
            enable_batch_analysis = st.checkbox(
                "Batch Pattern Analysis", 
                value=True, 
                help="Find common patterns across failures"
            )
            enable_jira_generation = st.checkbox(
                "Jira Ticket Generation", 
                value=False, 
                help="Auto-generate Jira tickets"
            )
            enable_test_improvements = st.checkbox(
                "Test Improvement Suggestions", 
                value=False, 
                help="Get suggestions to improve test stability"
            )
    
    return {
        'use_ai': use_ai,
        'enable_batch_analysis': enable_batch_analysis,
        'enable_jira_generation': enable_jira_generation,
        'enable_test_improvements': enable_test_improvements
    }


def _render_status_section(app_version: str, multi_baseline_available: bool, use_multi_baseline: bool):
    """Render version and status information"""
    st.markdown("### ℹ️ Status")
    
    status_items = []
    
    # Version
    status_items.append(f"📦 Version {app_version}")
    
    # Multi-baseline status
    if multi_baseline_available and use_multi_baseline:
        status_items.append("✅ Multi-Baseline")
    elif multi_baseline_available:
        status_items.append("⚪ Multi-Baseline (Off)")
    
    for item in status_items:
        st.caption(item)


def _reset_app():
    """Reset application state"""
    # Get current page before reset
    current_page = st.session_state.get('current_page', 'dashboard')
    
    # Clear most session state but preserve navigation
    keys_to_preserve = ['current_page', 'navigation_history', 'baseline_service']
    
    for key in list(st.session_state.keys()):
        if key not in keys_to_preserve:
            del st.session_state[key]
    
    st.success("✅ UI Reset! Ready for new uploads.")
    st.rerun()


def _render_statistics():
    """Render upload statistics"""
    st.markdown("### 📊 Statistics")
    
    if 'upload_stats' in st.session_state:
        stats = st.session_state.upload_stats
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Files", stats.get('count', 0))
        with col2:
            st.metric("Failures", stats.get('total_failures', 0))
        
        if stats.get('new_failures', 0) > 0:
            st.metric(
                "New", 
                stats.get('new_failures', 0),
                delta=f"+{stats.get('new_failures', 0)}",
                delta_color="inverse"
            )
    else:
        st.info("No data yet")


def _render_ai_status():
    """Render AI configuration status"""
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


# Additional helper for page-specific sidebar content
def render_page_sidebar_content(page_key: str):
    """
    Render page-specific sidebar content
    
    Args:
        page_key: Current page identifier
    """
    if page_key == 'dashboard':
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 📊 Dashboard Filters")
            
            date_range = st.selectbox(
                "Time Range",
                ["Last 7 days", "Last 30 days", "Last 90 days", "All time"],
                index=1
            )
            
            project_filter = st.multiselect(
                "Projects",
                ["All", "Provar", "AutomationAPI"],
                default=["All"]
            )
    
    elif page_key == 'trends':
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 📉 Trend Settings")
            
            metric = st.selectbox(
                "Metric",
                ["Failure Rate", "New Failures", "Total Tests", "Pass Rate"],
                index=0
            )
            
            granularity = st.selectbox(
                "Granularity",
                ["Daily", "Weekly", "Monthly"],
                index=1
            )
    
    elif page_key == 'settings':
        with st.sidebar:
            st.markdown("---")
            st.markdown("### ⚙️ Settings Categories")
            
            setting_category = st.radio(
                "Category",
                ["General", "AI Configuration", "GitHub", "Notifications"],
                label_visibility="collapsed"
            )
            
            return {'setting_category': setting_category}
    
    return {}