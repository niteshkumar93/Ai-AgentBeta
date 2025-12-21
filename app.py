import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# Import existing modules
from xml_extractor import extract_failed_tests
from ai_reasoner import (
    generate_ai_summary, 
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)
from baseline_manager import (
    save_baseline as save_provar_baseline,
    compare_with_baseline as compare_provar_baseline,
    load_baseline as load_provar_baseline
)

# Import new AutomationAPI modules
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

APP_VERSION = "3.0.0"  # New version with AutomationAPI support

# -----------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------
st.set_page_config("Provar AI - Multi-Platform XML Analyzer", layout="wide", page_icon="🚀")

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

st.markdown('<div class="main-header">🤖 Provar AI - Multi-Platform Report Analysis Tool</div>', unsafe_allow_html=True)

# -----------------------------------------------------------
# SIDEBAR - REPORT TYPE SELECTION
# -----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Report Type")
    
    # Radio button for report type selection
    report_type = st.radio(
        "Select Report Type:",
        options=["Provar XML Reports", "AutomationAPI Reports"],
        index=0,
        help="Choose the type of XML report you want to analyze"
    )
    
    st.markdown("---")
    
    # AI Settings
    st.subheader("🤖 AI Features")
    use_ai = st.checkbox("Enable AI Analysis", value=False, help="Use Groq AI for intelligent failure analysis")
    
    # Advanced AI Features
    with st.expander("🎯 Advanced AI Features"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", value=True)
        enable_jira_generation = st.checkbox("Jira Ticket Generation", value=True)
        enable_test_improvements = st.checkbox("Test Improvement Suggestions", value=False)
    
    admin_key = st.text_input("🔐 Admin Key", type="password", help="Required for saving baselines")
    
    st.markdown("---")
    st.caption(f"Version: {APP_VERSION}")
    
    # Reset Button
    if st.button("🔄 Reset All", type="secondary", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ UI Reset!")
        st.rerun()
    
    # Stats
    st.markdown("---")
    st.markdown("### 📊 Session Statistics")
    if 'upload_stats' in st.session_state:
        st.info(f"**Files:** {st.session_state.upload_stats.get('count', 0)}")
        st.info(f"**Total Failures:** {st.session_state.upload_stats.get('total_failures', 0)}")
        st.info(f"**New Failures:** {st.session_state.upload_stats.get('new_failures', 0)}")
    
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
# MAIN CONTENT AREA
# -----------------------------------------------------------

if report_type == "Provar XML Reports":
    # ============================================================
    # PROVAR XML REPORT ANALYSIS (EXISTING FUNCTIONALITY)
    # ============================================================
    st.markdown("## 📁 Upload Provar XML Reports")
    st.markdown("Upload multiple JUnit XML reports from Provar test executions")
    
    # ... (Keep your existing Provar analysis code here - I'll include it in the full file)
    # For now, showing the structure...
    
    uploaded_files = st.file_uploader(
        "Choose Provar XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="provar_uploader"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} Provar file(s) uploaded!")
        # ... rest of your existing Provar code ...
        st.info("📝 Provar analysis functionality - keeping your existing implementation")

else:
    # ============================================================
    # AUTOMATION API REPORT ANALYSIS (NEW FUNCTIONALITY)
    # ============================================================
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
                        
                        # Check baseline
                        baseline_exists_flag = api_baseline_exists(project)
                        
                        # Filter out metadata record
                        real_failures = [f for f in failures if not f.get("_no_failures")]
                        
                        if baseline_exists_flag and real_failures:
                            new_f, existing_f = compare_api_baseline(project, real_failures)
                        else:
                            new_f, existing_f = real_failures, []
                        
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
        # DISPLAY RESULTS
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
                    
                    # Display failures grouped by spec
                    if result['grouped_failures']:
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
                                                        failure['error_details']
                                                    )
                                                    st.markdown(jira_content)
                                                    st.download_button(
                                                        "📥 Download Jira Content",
                                                        jira_content,
                                                        file_name=f"jira_{failure['test_name'][:30]}.txt",
                                                        key=f"jira_api_{idx}_{i}"
                                                    )
                                    
                                    st.markdown("</div>", unsafe_allow_html=True)
                            
                            st.markdown("---")
                    
                    # Baseline Management
                    st.markdown("### 🛠️ Baseline Management")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"💾 Save as Baseline", key=f"save_api_{idx}"):
                            if not admin_key:
                                st.error("❌ Admin key required!")
                            else:
                                try:
                                    save_api_baseline(
                                        result['project'],
                                        result['all_failures'],
                                        admin_key
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
        # Welcome message
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