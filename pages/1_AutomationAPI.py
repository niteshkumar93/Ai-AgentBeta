import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

# Import the extractors and utilities
from automation_api_extractor import extract_failed_tests_automation_api
from automation_api_baseline import (
    save_automation_api_baseline,
    compare_automation_api_baseline,
    load_automation_api_baseline
)
from ai_reasoner import (
    generate_ai_summary,
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)

# -----------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------
KNOWN_API_PROJECTS = [
    "API_Gateway", "REST_Services", "SOAP_Services",
    "Integration_Tests", "Microservices_API", "GraphQL_API",
    "Authentication_API", "Payment_API", "User_API"
]

APP_VERSION = "2.2.0"

# -----------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------
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

def safe_extract_api_failures(uploaded_file):
    """Safely extract API test failures"""
    try:
        uploaded_file.seek(0)
        return extract_failed_tests_automation_api(uploaded_file)
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {str(e)}")
        return []

def detect_api_project(filename: str):
    """Detect API project from filename"""
    for p in KNOWN_API_PROJECTS:
        if p.lower() in filename.lower():
            return p
    return KNOWN_API_PROJECTS[0]

def render_api_summary_card(xml_name, new_count, existing_count, total_count):
    """Render summary card for API test results"""
    status_color = "🟢" if new_count == 0 else "🔴"
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", status_color)
    with col2:
        st.metric("New API Failures", new_count, delta=None if new_count == 0 else f"+{new_count}", delta_color="inverse")
    with col3:
        st.metric("Existing API Failures", existing_count)
    with col4:
        st.metric("Total API Failures", total_count)

def render_api_comparison_chart(all_results):
    """Create comparison chart for API test results"""
    if not all_results:
        return
    
    df_data = []
    for result in all_results:
        df_data.append({
            'File': result['filename'][:30] + '...' if len(result['filename']) > 30 else result['filename'],
            'New Failures': result['new_count'],
            'Existing Failures': result['existing_count'],
            'Total': result['total_count']
        })
    
    df = pd.DataFrame(df_data)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='New API Failures',
        x=df['File'],
        y=df['New Failures'],
        marker_color='#FF4B4B'
    ))
    fig.add_trace(go.Bar(
        name='Existing API Failures',
        x=df['File'],
        y=df['Existing Failures'],
        marker_color='#FFA500'
    ))
    
    fig.update_layout(
        title='API Failure Comparison Across All Reports',
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
st.set_page_config("AutomationAPI Analyzer", layout="wide", page_icon="🔌")

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
    .api-feature-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🔌 AutomationAPI Test Analysis Tool</div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR CONFIGURATION
# -----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # AI Settings
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=False, help="Use AI for intelligent API failure analysis")
    
    # Advanced AI Features
    with st.expander("🎯 Advanced AI Features"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", value=True, help="Find common patterns across API failures")
        enable_jira_generation = st.checkbox("Jira Ticket Generation", value=True, help="Auto-generate Jira tickets")
        enable_test_improvements = st.checkbox("API Test Improvements", value=False, help="Get suggestions to improve API test stability")
    
    admin_key = st.text_input("🔑 Admin Key", type="password", help="Required for saving baselines")
    
    st.markdown("---")
    
    # Version info
    st.caption(f"Version: {APP_VERSION}")
    
    # Reset Button
    if st.button("🔄 Reset All", type="secondary", use_container_width=True):
        for key in ['api_all_results', 'api_upload_stats', 'api_batch_analysis']:
            if key in st.session_state:
                del st.session_state[key]
        st.success("✅ UI Reset! Ready for new uploads.")
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Upload Statistics")
    if 'api_upload_stats' in st.session_state:
        st.info(f"**Files Uploaded:** {st.session_state.api_upload_stats.get('count', 0)}")
        st.info(f"**Total Failures:** {st.session_state.api_upload_stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {st.session_state.api_upload_stats.get('new_failures', 0)}")
    
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
# FILE UPLOAD SECTION
# -----------------------------------------------------------
st.markdown("## 📁 Upload AutomationAPI XML Reports")
st.markdown("Upload multiple AutomationAPI XML test reports for AI-powered analysis")

uploaded_files = st.file_uploader(
    "Choose AutomationAPI XML files",
    type=["xml"],
    accept_multiple_files=True,
    help="Select one or more AutomationAPI XML files to analyze"
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} API test file(s) uploaded successfully!")
    
    # Initialize session state
    if 'api_all_results' not in st.session_state:
        st.session_state.api_all_results = []
    
    # -----------------------------------------------------------
    # GLOBAL ANALYSIS BUTTON
    # -----------------------------------------------------------
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_all = st.button("🔍 Analyze All API Reports with AI", type="primary", use_container_width=True)
    
    if analyze_all:
        st.session_state.api_all_results = []
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, xml_file in enumerate(uploaded_files):
            status_text.text(f"Processing {xml_file.name}... ({idx + 1}/{len(uploaded_files)})")
            
            failures = safe_extract_api_failures(xml_file)
            
            if failures:
                detected_project = detect_api_project(xml_file.name)
                
                # Capture timestamp from first failure
                execution_time = failures[0].get("timestamp", "Unknown")
                
                # Compare with baseline
                baseline_exists = bool(load_automation_api_baseline(detected_project))
                if baseline_exists:
                    new_f, existing_f = compare_automation_api_baseline(detected_project, failures)
                else:
                    new_f, existing_f = failures, []
                
                st.session_state.api_all_results.append({
                    'filename': xml_file.name,
                    'project': detected_project,
                    'new_failures': new_f,
                    'existing_failures': existing_f,
                    'new_count': len(new_f),
                    'existing_count': len(existing_f),
                    'total_count': len(failures),
                    'baseline_exists': baseline_exists,
                    'execution_time': execution_time
                })
            
            progress_bar.progress((idx + 1) / len(uploaded_files))
        
        status_text.text("✅ Analysis complete!")
        progress_bar.empty()
        
        # Update statistics
        total_failures = sum(r['total_count'] for r in st.session_state.api_all_results)
        new_failures = sum(r['new_count'] for r in st.session_state.api_all_results)
        
        st.session_state.api_upload_stats = {
            'count': len(uploaded_files),
            'total_failures': total_failures,
            'new_failures': new_failures
        }
        
        # Generate batch analysis if enabled
        if use_ai and enable_batch_analysis:
            with st.spinner("🧠 Running batch pattern analysis..."):
                all_failures = []
                for result in st.session_state.api_all_results:
                    all_failures.extend(result['new_failures'])
                
                if all_failures:
                    st.session_state.api_batch_analysis = generate_batch_analysis(all_failures)
    
    # -----------------------------------------------------------
    # DISPLAY RESULTS
    # -----------------------------------------------------------
    if st.session_state.api_all_results:
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        # Batch Analysis
        if 'api_batch_analysis' in st.session_state and st.session_state.api_batch_analysis:
            st.markdown('<div class="api-feature-box">', unsafe_allow_html=True)
            st.markdown("## 🧠 AI Batch Pattern Analysis")
            st.markdown("AI has analyzed all API failures together to identify patterns and priorities.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown(st.session_state.api_batch_analysis)
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        st.markdown("## 📊 Overall Summary")
        
        # Overall statistics
        total_new = sum(r['new_count'] for r in st.session_state.api_all_results)
        total_existing = sum(r['existing_count'] for r in st.session_state.api_all_results)
        total_all = sum(r['total_count'] for r in st.session_state.api_all_results)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📄 Total Files", len(st.session_state.api_all_results))
        with col2:
            st.metric("🆕 Total New API Failures", total_new, delta=f"+{total_new}" if total_new > 0 else "0", delta_color="inverse")
        with col3:
            st.metric("♻️ Total Existing API Failures", total_existing)
        with col4:
            st.metric("📈 Total All API Failures", total_all)
        
        # Comparison chart
        render_api_comparison_chart(st.session_state.api_all_results)
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("## 📋 Detailed API Results by File")
        
        # Individual file results
        for idx, result in enumerate(st.session_state.api_all_results):
            formatted_time = format_execution_time(result.get("execution_time", "Unknown"))

            with st.expander(
                f"📄 {result['filename']} | ⏰ {formatted_time} — Project: {result['project']}",
                expanded=False
            ):
                
                # Summary card
                render_api_summary_card(
                    result['filename'],
                    result['new_count'],
                    result['existing_count'],
                    result['total_count']
                )
                
                st.markdown("---")
                
                # Tabs for different failure types
                tab1, tab2, tab3 = st.tabs(["🆕 New API Failures", "♻️ Existing API Failures", "⚙️ Actions"])
                
                with tab1:
                    if result['new_count'] == 0:
                        st.success("✅ No new API failures detected!")
                    else:
                        for i, f in enumerate(result['new_failures']):
                            with st.expander(f"🆕 {i+1}. {f['testcase']}", expanded=False):
                                # API specific details
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.write("**Endpoint:**", f.get('apiEndpoint', 'Unknown'))
                                with col2:
                                    st.write("**Method:**", f.get('httpMethod', 'Unknown'))
                                with col3:
                                    st.write("**Status Code:**", f.get('statusCode', 'Unknown'))

                                # Test path
                                st.markdown("**Test Path:**")
                                st.code(f.get('testcase_path', ''), language="text")

                                # Error summary
                                st.error(f"Error: {f['error']}")

                                # Error details
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
                                        
                                        # Basic AI Analysis
                                        with ai_tab_objects[0]:
                                            with st.spinner("Analyzing API failure..."):
                                                ai_analysis = generate_ai_summary(f['testcase'], f['error'], f['details'])
                                                st.info(ai_analysis)
                                        
                                        # Jira Ticket Generation
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
                                                        file_name=f"jira_api_{f['testcase'][:30]}.txt",
                                                        key=f"jira_{idx}_{i}"
                                                    )
                                        
                                        # Test Improvements
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
                        st.info("ℹ️ No existing API failures found in baseline")
                    else:
                        st.warning(f"Found {result['existing_count']} known API failures")
                        for i, f in enumerate(result['existing_failures']):
                            with st.expander(f"♻️ {i+1}. {f['testcase']}", expanded=False):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.write("**Endpoint:**", f.get('apiEndpoint', 'Unknown'))
                                with col2:
                                    st.write("**Method:**", f.get('httpMethod', 'Unknown'))
                                with col3:
                                    st.write("**Status Code:**", f.get('statusCode', 'Unknown'))
                                
                                st.markdown("**Test Path:**")
                                st.code(f.get('testcase_path', ''), language="text")
                                st.error(f"Error: {f['error']}")
                                st.markdown("**Error Details:**")
                                st.code(f['details'], language="text")
                                st.markdown("---")
                
                with tab3:
                    st.markdown("### 🛠️ Baseline Management")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"💾 Save as Baseline", key=f"save_{idx}"):
                            if not admin_key:
                                st.error("❌ Admin key required!")
                            else:
                                try:
                                    all_failures = result['new_failures'] + result['existing_failures']
                                    save_automation_api_baseline(result['project'], all_failures, admin_key)
                                    st.success("✅ API Baseline saved successfully!")
                                except Exception as e:
                                    st.error(f"❌ Error: {str(e)}")
                    
                    with col2:
                        if result['baseline_exists']:
                            st.success("✅ Baseline exists for this API project")
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
                            file_name=f"{result['filename']}_api_failures.csv",
                            mime="text/csv",
                            key=f"export_{idx}"
                        )

else:
    # Welcome message
    st.info("👆 Upload one or more AutomationAPI XML files to begin AI-powered analysis")
    
    st.markdown("### 🎯 AutomationAPI Features")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**📊 Multi-File Analysis**")
        st.write("Upload and analyze multiple API test reports simultaneously")
    with col2:
        st.markdown("**🤖 AI-Powered Insights**")
        st.write("Get intelligent API failure analysis")
    with col3:
        st.markdown("**📈 Baseline Tracking**")
        st.write("Compare API results against historical baselines")
    
    st.markdown("---")
    
    st.markdown("### 🔌 API-Specific Analysis")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**🌐 Endpoint Tracking**")
        st.write("Track failures by API endpoint")
    with col2:
        st.markdown("**📊 HTTP Method Analysis**")
        st.write("Analyze failures by HTTP method (GET, POST, etc.)")
    with col3:
        st.markdown("**🔢 Status Code Monitoring**")
        st.write("Monitor and track API response status codes")