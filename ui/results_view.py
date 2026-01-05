"""
Results view components for displaying analysis results
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict, Any
from datetime import datetime

def format_execution_time(raw_time: str) -> str:
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


def render_summary_card(xml_name: str, new_count: int, existing_count: int, total_count: int):
    """Render a summary card for each XML file"""
    status_color = "🟢" if new_count == 0 else "🔴"
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", status_color)
    with col2:
        st.metric("New Failures", new_count, 
                 delta=None if new_count == 0 else f"+{new_count}", 
                 delta_color="inverse")
    with col3:
        st.metric("Existing Failures", existing_count)
    with col4:
        st.metric("Total Failures", total_count)


def render_comparison_chart(all_results: List[Dict[str, Any]]):
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


def render_overall_summary(results: List[Dict[str, Any]]):
    """Render overall summary statistics"""
    st.markdown("## 📊 Overall Summary")
    
    total_new = sum(r['new_count'] for r in results)
    total_existing = sum(r['existing_count'] for r in results)
    total_all = sum(r['total_count'] for r in results)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Total Files", len(results))
    with col2:
        st.metric("🆕 Total New Failures", total_new, 
                 delta=f"+{total_new}" if total_new > 0 else "0", 
                 delta_color="inverse")
    with col3:
        st.metric("♻️ Total Existing Failures", total_existing)
    with col4:
        st.metric("📈 Total All Failures", total_all)
    
    render_comparison_chart(results)


def render_failure_details(failure: Dict[str, Any], idx: int, file_idx: int, 
                          failure_type: str, ai_service=None, ai_settings: Dict = None):
    """
    Render detailed failure information
    
    Args:
        failure: Failure dictionary
        idx: Failure index
        file_idx: File index
        failure_type: 'new' or 'existing'
        ai_service: Optional AIService instance
        ai_settings: Optional AI settings dictionary
    """
    icon = "🆕" if failure_type == "new" else "♻️"
    
    with st.expander(f"{icon} {idx+1}. {failure['testcase']}", expanded=False):
        st.write("**Browser:**", failure.get('webBrowserType', 'Unknown'))
        st.markdown("**Path:**")
        st.code(failure.get('testcase_path', ''), language="text")
        st.error(f"Error: {failure['error']}")
        st.markdown("**Error Details (click copy icon):**")
        st.code(failure['details'], language="text")
        
        # AI Features
        if ai_service and ai_settings and ai_settings.get('use_ai'):
            _render_ai_features(
                failure, 
                idx, 
                file_idx, 
                ai_service, 
                ai_settings,
                failure_type
            )


def _render_ai_features(failure: Dict, idx: int, file_idx: int, 
                       ai_service, ai_settings: Dict, failure_type: str):
    """Render AI analysis features for a failure"""
    ai_tabs = []
    if True:  # Always show AI analysis if enabled
        ai_tabs.append("🤖 AI Analysis")
    if ai_settings.get('enable_jira_generation'):
        ai_tabs.append("📝 Jira Ticket")
    if ai_settings.get('enable_test_improvements'):
        ai_tabs.append("💡 Improvements")
    
    if len(ai_tabs) > 0:
        ai_tab_objects = st.tabs(ai_tabs)
        
        # AI Analysis Tab
        with ai_tab_objects[0]:
            with st.spinner("Analyzing..."):
                ai_analysis = ai_service.generate_summary(
                    failure['testcase'], 
                    failure['error'], 
                    failure['details']
                )
                st.info(ai_analysis)
        
        # Jira Generation Tab
        if ai_settings.get('enable_jira_generation') and len(ai_tab_objects) > 1:
            with ai_tab_objects[1]:
                with st.spinner("Generating Jira ticket..."):
                    jira_content = ai_service.generate_jira_ticket(
                        failure['testcase'], 
                        failure['error'], 
                        failure['details'],
                        ai_analysis if 'ai_analysis' in locals() else ""
                    )
                    st.markdown(jira_content)
                    st.download_button(
                        "📥 Download Jira Content",
                        jira_content,
                        file_name=f"jira_{failure['testcase'][:30]}.txt",
                        key=f"jira_{failure_type}_{file_idx}_{idx}"
                    )
        
        # Improvements Tab
        if ai_settings.get('enable_test_improvements') and len(ai_tab_objects) > 2:
            with ai_tab_objects[-1]:
                with st.spinner("Generating improvement suggestions..."):
                    improvements = ai_service.suggest_improvements(
                        failure['testcase'],
                        failure['error'],
                        failure['details']
                    )
                    st.success(improvements)


def render_export_section(result: Dict[str, Any], idx: int, platform: str = "provar"):
    """Render export options for results"""
    st.markdown("### 📤 Export Options")
    
    all_failures = result.get('new_failures', []) + result.get('existing_failures', [])
    if platform == "automation_api":
        all_failures = result.get('all_failures', [])
    
    if all_failures:
        export_data = pd.DataFrame(all_failures)
        csv = export_data.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"{result['filename']}_failures.csv",
            mime="text/csv",
            key=f"export_{platform}_{idx}"
        )


def render_batch_ai_analysis(batch_analysis: str):
    """Render batch AI pattern analysis"""
    if not batch_analysis:
        return
    
    st.markdown('<div class="ai-feature-box">', unsafe_allow_html=True)
    st.markdown("## 🧠 AI Batch Pattern Analysis")
    st.markdown("AI has analyzed all failures together to identify patterns and priorities.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(batch_analysis)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)