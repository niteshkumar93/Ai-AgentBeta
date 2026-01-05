"""
Sidebar UI components
"""
import streamlit as st
import os

def render_sidebar(baseline_service, app_version: str, multi_baseline_available: bool, api_multi_baseline_available: bool):
    """
    Render the complete sidebar
    
    Args:
        baseline_service: BaselineService instance
        app_version: Application version string
        multi_baseline_available: Whether multi-baseline is available
        api_multi_baseline_available: Whether API multi-baseline is available
        
    Returns:
        Dictionary with sidebar settings
    """
    with st.sidebar:
        # GitHub Connection Status
        st.markdown("---")
        st.markdown("### 🔍 GitHub Connection Status")
        
        try:
            test_list = baseline_service.github.list_baselines("provar")
            st.success(f"✅ GitHub Connected")
            st.caption(f"Found {len(test_list)} baseline(s)")
        except Exception as e:
            st.error("❌ GitHub Connection Failed")
            st.code(str(e))
            
            # Show secret status
            _show_secret_status()
        
        st.markdown("---")
        
        # Baseline Sync
        st.subheader("🔄 Baseline Sync")
        if st.button("🔄 Sync Baselines from GitHub"):
            with st.spinner("Syncing baselines from GitHub..."):
                synced = baseline_service.sync_from_github()
            st.success(f"✅ {synced} baseline(s) synced from GitHub")
            st.rerun()
        
        st.markdown("---")
        
        # Configuration
        st.header("⚙️ Configuration")
        
        # Report Type Selection
        st.subheader("📊 Report Type")
        report_type = st.radio(
            "Select Report Type:",
            options=["Provar Regression Reports", "AutomationAPI Reports", "📈 Baseline Tracker"],
            index=0,
            help="Choose the type of XML report you want to analyze"
        )
        
        st.markdown("---")
        
        # AI Features
        ai_settings = _render_ai_settings()
        
        # Admin Key
        admin_key = st.text_input(
            "🔐 Admin Key", 
            type="password", 
            help="Required for saving baselines", 
            key="admin_key_input"
        )
        
        # Multi-baseline toggle
        use_multi_baseline = False
        if multi_baseline_available:
            st.markdown("---")
            st.subheader("🆕 Multi-Baseline")
            use_multi_baseline = st.checkbox(
                "Enable Multi-Baseline (NEW)",
                value=True,
                help="Store up to 10 baselines per project (recommended)"
            )
        
        st.markdown("---")
        
        # Version and Status
        _render_status_section(app_version, multi_baseline_available, use_multi_baseline)
        
        # Reset Button
        if st.button("🔄 Reset All", type="secondary", use_container_width=True, 
                    help="Clear all data and start fresh"):
            _reset_app()
        
        st.markdown("---")
        
        # Statistics
        _render_statistics()
        
        # AI Status
        _render_ai_status()
        
        return {
            'report_type': report_type,
            'admin_key': admin_key,
            'use_multi_baseline': use_multi_baseline,
            **ai_settings
        }


def _show_secret_status():
    """Show GitHub secret configuration status"""
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


def _render_ai_settings():
    """Render AI settings section"""
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox(
        "Enable AI Analysis", 
        value=False, 
        help="Use Groq AI for intelligent failure analysis"
    )
    
    # Advanced AI Features
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
    st.caption(f"Version: {app_version}")
    if multi_baseline_available and use_multi_baseline:
        st.success("✅ Multi-Baseline Active")


def _reset_app():
    """Reset application state"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success("✅ UI Reset! Ready for new uploads.")
    st.rerun()


def _render_statistics():
    """Render upload statistics"""
    st.markdown("### 📊 Upload Statistics")
    if 'upload_stats' in st.session_state:
        st.info(f"**Files Uploaded:** {st.session_state.upload_stats.get('count', 0)}")
        st.info(f"**Total Failures:** {st.session_state.upload_stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {st.session_state.upload_stats.get('new_failures', 0)}")


def _render_ai_status():
    """Render AI configuration status"""
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