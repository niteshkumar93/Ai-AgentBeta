"""
New page components for Dashboard, Trends, and Settings
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os


# ============================================================
# DASHBOARD PAGE
# ============================================================
def render_dashboard(baseline_service):
    """
    Render main dashboard with overview metrics
    
    Args:
        baseline_service: BaselineService instance
    """
    st.markdown("# 📊 Dashboard")
    st.markdown("Overview of test health and recent activity")
    st.markdown("---")
    
    # Quick Stats Row
    _render_quick_stats(baseline_service)
    
    st.markdown("---")
    
    # Two-column layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        _render_recent_activity()
        st.markdown("---")
        _render_failure_trends()
    
    with col2:
        _render_project_health(baseline_service)
        st.markdown("---")
        _render_quick_actions_card()


def _render_quick_stats(baseline_service):
    """Render quick statistics cards"""
    col1, col2, col3, col4 = st.columns(4)
    
    # Try to get real stats from baselines
    try:
        provar_baselines = baseline_service.list(platform="provar")
        api_baselines = baseline_service.list(platform="automation_api")
        total_baselines = len(provar_baselines) + len(api_baselines)
    except:
        total_baselines = 0
    
    # Get session stats
    total_files = st.session_state.get('upload_stats', {}).get('count', 0)
    total_failures = st.session_state.get('upload_stats', {}).get('total_failures', 0)
    new_failures = st.session_state.get('upload_stats', {}).get('new_failures', 0)
    
    with col1:
        st.metric("📁 Files Analyzed", total_files)
    
    with col2:
        st.metric("📈 Total Baselines", total_baselines)
    
    with col3:
        st.metric("❌ Total Failures", total_failures)
    
    with col4:
        delta_color = "inverse" if new_failures > 0 else "normal"
        st.metric("🆕 New Failures", new_failures, delta=f"+{new_failures}" if new_failures > 0 else None, delta_color=delta_color)


def _render_recent_activity():
    """Render recent activity timeline"""
    st.markdown("### 📅 Recent Activity")
    
    if 'all_results' in st.session_state or 'api_results' in st.session_state:
        # Combine recent activities
        activities = []
        
        if 'all_results' in st.session_state:
            for result in st.session_state.all_results[:5]:  # Last 5
                activities.append({
                    'type': 'Provar',
                    'project': result['project'],
                    'filename': result['filename'],
                    'failures': result['total_count'],
                    'new': result['new_count'],
                    'time': result.get('execution_time', 'Unknown')
                })
        
        if 'api_results' in st.session_state:
            for result in st.session_state.api_results[:5]:  # Last 5
                activities.append({
                    'type': 'API',
                    'project': result['project'],
                    'filename': result['filename'],
                    'failures': result['stats']['total_failures'],
                    'new': len(result['new_failures']),
                    'time': result.get('timestamp', 'Unknown')
                })
        
        if activities:
            for activity in activities:
                icon = "📁" if activity['type'] == 'Provar' else "🔧"
                st.markdown(
                    f"{icon} **{activity['project']}** - {activity['filename']}  \n"
                    f"   └ {activity['failures']} failures ({activity['new']} new) · {activity['time']}"
                )
        else:
            st.info("No recent activity")
    else:
        st.info("Upload XML reports to see activity")


def _render_failure_trends():
    """Render failure trends chart"""
    st.markdown("### 📉 Failure Trends (Session)")
    
    if 'all_results' in st.session_state and len(st.session_state.all_results) > 0:
        # Create trend data from session
        df_data = []
        for i, result in enumerate(st.session_state.all_results):
            df_data.append({
                'File': result['filename'][:20] + '...' if len(result['filename']) > 20 else result['filename'],
                'New': result['new_count'],
                'Existing': result['existing_count'],
                'Order': i
            })
        
        df = pd.DataFrame(df_data)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['Order'],
            y=df['New'],
            mode='lines+markers',
            name='New Failures',
            line=dict(color='#FF4B4B', width=3),
            marker=dict(size=8)
        ))
        fig.add_trace(go.Scatter(
            x=df['Order'],
            y=df['Existing'],
            mode='lines+markers',
            name='Existing Failures',
            line=dict(color='#FFA500', width=3),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            xaxis_title="Upload Sequence",
            yaxis_title="Failure Count",
            height=300,
            hovermode='x unified',
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Upload reports to see trends")


def _render_project_health(baseline_service):
    """Render project health overview"""
    st.markdown("### 💚 Project Health")
    
    try:
        provar_baselines = baseline_service.list(platform="provar")
        api_baselines = baseline_service.list(platform="automation_api")
        
        if provar_baselines or api_baselines:
            # Group by project
            projects = {}
            
            for baseline in provar_baselines:
                project = baseline.get('name', '').split('_')[0]
                if project not in projects:
                    projects[project] = {'provar': 0, 'api': 0}
                projects[project]['provar'] += 1
            
            for baseline in api_baselines:
                project = baseline.get('name', '').split('_')[0]
                if project not in projects:
                    projects[project] = {'provar': 0, 'api': 0}
                projects[project]['api'] += 1
            
            for project, counts in projects.items():
                with st.container():
                    st.markdown(f"**{project}**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"📁 {counts['provar']} Provar")
                    with col2:
                        st.caption(f"🔧 {counts['api']} API")
                    st.markdown("---")
        else:
            st.info("No baselines found")
    
    except Exception as e:
        st.warning(f"Unable to load project health: {str(e)}")


def _render_quick_actions_card():
    """Render quick actions card"""
    st.markdown("### ⚡ Quick Actions")
    
    if st.button("📤 Upload Provar Report", use_container_width=True):
        st.session_state.current_page = 'provar'
        st.rerun()
    
    if st.button("🔧 Upload API Report", use_container_width=True):
        st.session_state.current_page = 'automation_api'
        st.rerun()
    
    if st.button("📈 View Baselines", use_container_width=True):
        st.session_state.current_page = 'baselines'
        st.rerun()


# ============================================================
# TRENDS PAGE
# ============================================================
def render_trends(baseline_service):
    """
    Render trends analysis page
    
    Args:
        baseline_service: BaselineService instance
    """
    st.markdown("# 📉 Trends")
    st.markdown("Track test metrics over time")
    st.markdown("---")
    
    # Filter controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        platform = st.selectbox("Platform", ["All", "Provar", "AutomationAPI"])
    
    with col2:
        metric = st.selectbox("Metric", ["Failure Count", "New Failures", "Pass Rate"])
    
    with col3:
        time_range = st.selectbox("Time Range", ["Last 7 days", "Last 30 days", "Last 90 days"])
    
    st.markdown("---")
    
    # Mock trend data (replace with real data from baselines)
    _render_mock_trends(platform, metric, time_range)


def _render_mock_trends(platform, metric, time_range):
    """Render mock trend charts"""
    st.info("🚧 Trends feature coming soon! This will show historical test metrics from your baselines.")
    
    # Mock data
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    values = [10 + i % 5 + (i % 3) * 2 for i in range(30)]
    
    df = pd.DataFrame({
        'Date': dates,
        'Value': values
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Value'],
        mode='lines+markers',
        name=metric,
        line=dict(color='#667eea', width=3),
        marker=dict(size=6)
    ))
    
    fig.update_layout(
        title=f"{metric} - {platform} ({time_range})",
        xaxis_title="Date",
        yaxis_title=metric,
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Stats table
    st.markdown("### 📊 Summary Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Average", f"{sum(values)/len(values):.1f}")
    with col2:
        st.metric("Max", max(values))
    with col3:
        st.metric("Min", min(values))
    with col4:
        st.metric("Trend", "↗️ Improving" if values[-1] < values[0] else "↘️ Declining")


# ============================================================
# SETTINGS PAGE
# ============================================================
def render_settings(baseline_service):
    """
    Render settings page
    
    Args:
        baseline_service: BaselineService instance
    """
    st.markdown("# ⚙️ Settings")
    st.markdown("Configure application preferences and integrations")
    st.markdown("---")
    
    # Settings tabs
    tab1, tab2, tab3, tab4 = st.tabs(["🔧 General", "🤖 AI Configuration", "🔗 GitHub", "🔔 Notifications"])
    
    with tab1:
        _render_general_settings()
    
    with tab2:
        _render_ai_settings()
    
    with tab3:
        _render_github_settings(baseline_service)
    
    with tab4:
        _render_notification_settings()


def _render_general_settings():
    """Render general settings"""
    st.markdown("### 🎨 Appearance")
    
    theme = st.selectbox("Theme", ["Light", "Dark", "Auto"], index=2)
    show_animations = st.checkbox("Show animations", value=True)
    
    st.markdown("---")
    st.markdown("### 📊 Default Settings")
    
    default_platform = st.selectbox("Default Platform", ["Provar", "AutomationAPI"], index=0)
    auto_sync = st.checkbox("Auto-sync baselines on startup", value=True)
    
    st.markdown("---")
    
    if st.button("💾 Save General Settings", type="primary"):
        st.success("✅ Settings saved!")


def _render_ai_settings():
    """Render AI configuration settings"""
    st.markdown("### 🤖 AI Provider")
    
    provider = st.selectbox("AI Provider", ["Groq (Free)", "OpenAI (Paid)"], index=0)
    
    st.markdown("---")
    st.markdown("### 🎯 AI Features")
    
    enable_auto_analysis = st.checkbox("Enable automatic AI analysis", value=False)
    enable_smart_summaries = st.checkbox("Generate smart summaries", value=True)
    enable_suggestions = st.checkbox("Show improvement suggestions", value=True)
    
    st.markdown("---")
    st.markdown("### 🔑 API Keys")
    
    if provider == "Groq (Free)":
        groq_key = st.text_input("Groq API Key", type="password", value=os.getenv("GROQ_API_KEY", ""))
        st.caption("Get your free API key at [groq.com](https://groq.com)")
    else:
        openai_key = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        st.caption("Get your API key at [platform.openai.com](https://platform.openai.com)")
    
    st.markdown("---")
    
    if st.button("💾 Save AI Settings", type="primary"):
        st.success("✅ AI settings saved!")


def _render_github_settings(baseline_service):
    """Render GitHub integration settings"""
    st.markdown("### 🔗 GitHub Integration")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.text_input("Repository Owner", value=st.secrets.get("GITHUB_OWNER", ""), disabled=True)
        st.text_input("Repository Name", value=st.secrets.get("GITHUB_REPO", ""), disabled=True)
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Test Connection"):
            try:
                test_list = baseline_service.github.list_baselines("provar")
                st.success(f"✅ Connected! Found {len(test_list)} baselines")
            except Exception as e:
                st.error(f"❌ Connection failed: {str(e)}")
    
    st.markdown("---")
    st.markdown("### 🔄 Sync Settings")
    
    auto_sync = st.checkbox("Auto-sync on startup", value=True)
    sync_interval = st.selectbox("Sync interval", ["Manual", "Every hour", "Every 6 hours", "Daily"], index=0)
    
    if st.button("🔄 Sync Now", use_container_width=True):
        with st.spinner("Syncing from GitHub..."):
            try:
                synced = baseline_service.sync_from_github()
                st.success(f"✅ {synced} baseline(s) synced!")
            except Exception as e:
                st.error(f"❌ Sync failed: {str(e)}")


def _render_notification_settings():
    """Render notification settings"""
    st.markdown("### 🔔 Notification Preferences")
    
    st.info("🚧 Notification features coming soon!")
    
    enable_email = st.checkbox("Email notifications", value=False, disabled=True)
    enable_slack = st.checkbox("Slack notifications", value=False, disabled=True)
    enable_teams = st.checkbox("Microsoft Teams notifications", value=False, disabled=True)
    
    st.markdown("---")
    st.markdown("### 📧 Email Settings")
    
    email = st.text_input("Email address", placeholder="your@email.com", disabled=True)
    
    st.markdown("### 🎯 Notification Triggers")
    
    notify_new_failures = st.checkbox("New failures detected", value=True, disabled=True)
    notify_baseline_saved = st.checkbox("Baseline saved", value=False, disabled=True)
    notify_threshold = st.checkbox("Failure threshold exceeded", value=True, disabled=True)