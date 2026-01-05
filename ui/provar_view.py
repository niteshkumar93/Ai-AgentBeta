"""
Provar-specific UI components
"""
import streamlit as st
import os
from ui.results_view import (
    format_execution_time,
    render_summary_card,
    render_overall_summary,
    render_failure_details,
    render_export_section,
    render_batch_ai_analysis
)
from baseline_manager import KNOWN_PROJECTS

def render_provar_analysis(analysis_service, ai_service, baseline_service, 
                           sidebar_settings, extract_func, detect_project_func, 
                           shorten_path_func):
    """Render Provar analysis interface"""
    
    st.markdown("## 📁 Upload Provar XML Reports")
    st.markdown("Upload multiple JUnit XML reports from Provar test executions for simultaneous AI-powered analysis")
    
    uploaded_files = st.file_uploader(
        "Choose Provar XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="provar_uploader",
        help="Select one or more XML files to analyze"
    )
    
    if not uploaded_files:
        _render_provar_welcome()
        return
    
    st.success(f"✅ {len(uploaded_files)} Provar file(s) uploaded successfully!")
    
    # Initialize session state
    if 'all_results' not in st.session_state:
        st.session_state.all_results = []
    
    # Global Analysis Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_all = st.button(
            "🔍 Analyze All Provar Reports", 
            type="primary", 
            use_container_width=True
        )
    
    if analyze_all:
        _process_provar_files(
            uploaded_files=uploaded_files,
            analysis_service=analysis_service,
            ai_service=ai_service,
            sidebar_settings=sidebar_settings,
            extract_func=extract_func,
            detect_project_func=detect_project_func,
            shorten_path_func=shorten_path_func
        )
    
    # Display Results
    if st.session_state.all_results:
        _display_provar_results(
            results=st.session_state.all_results,
            ai_service=ai_service,
            baseline_service=baseline_service,
            sidebar_settings=sidebar_settings
        )


def _process_provar_files(uploaded_files, analysis_service, ai_service, 
                         sidebar_settings, extract_func, detect_project_func, 
                         shorten_path_func):
    """Process uploaded Provar files"""
    
    st.session_state.all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def progress_callback(idx, total, filename):
        status_text.text(f"Processing {filename}... ({idx + 1}/{total})")
        progress_bar.progress((idx + 1) / total)
    
    # Analyze files
    results = analysis_service.analyze_batch_provar(
        uploaded_files=uploaded_files,
        extract_func=extract_func,
        detect_project_func=detect_project_func,
        shorten_path_func=shorten_path_func,
        progress_callback=progress_callback
    )
    
    st.session_state.all_results = results
    status_text.text("✅ Analysis complete!")
    progress_bar.empty()
    
    # Update statistics
    total_failures = sum(r['total_count'] for r in results)
    new_failures = sum(r['new_count'] for r in results)
    
    st.session_state.upload_stats = {
        'count': len(uploaded_files),
        'total_failures': total_failures,
        'new_failures': new_failures
    }
    
    # Generate batch analysis if enabled
    if sidebar_settings['use_ai'] and sidebar_settings['enable_batch_analysis']:
        with st.spinner("🧠 Running batch pattern analysis..."):
            all_failures = []
            for result in results:
                all_failures.extend(result['new_failures'])
            
            if all_failures:
                st.session_state.batch_analysis = ai_service.generate_batch_analysis(all_failures)


def _display_provar_results(results, ai_service, baseline_service, sidebar_settings):
    """Display Provar analysis results"""
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # Batch Analysis
    if 'batch_analysis' in st.session_state:
        render_batch_ai_analysis(st.session_state.batch_analysis)
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # Overall Summary
    render_overall_summary(results)
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("## 📋 Detailed Results by File")
    
    # Individual file results
    for idx, result in enumerate(results):
        formatted_time = format_execution_time(result.get("execution_time", "Unknown"))
        
        with st.expander(
            f"📄 {result['filename']} | ⏰ {formatted_time} – Project: {result['project']}",
            expanded=False
        ):
            # Summary card
            render_summary_card(
                result['filename'],
                result['new_count'],
                result['existing_count'],
                result['total_count']
            )
            
            st.markdown("---")
            
            # Tabs for different sections
            tab1, tab2, tab3 = st.tabs(["🆕 New Failures", "♻️ Existing Failures", "⚙️ Actions"])
            
            with tab1:
                _render_new_failures_tab(result, idx, ai_service, sidebar_settings)
            
            with tab2:
                _render_existing_failures_tab(result, idx, ai_service, sidebar_settings)
            
            with tab3:
                _render_actions_tab(result, idx, baseline_service, sidebar_settings)


def _render_new_failures_tab(result, file_idx, ai_service, sidebar_settings):
    """Render new failures tab"""
    if result['new_count'] == 0:
        st.success("✅ No new failures detected!")
    else:
        for i, failure in enumerate(result['new_failures']):
            render_failure_details(
                failure=failure,
                idx=i,
                file_idx=file_idx,
                failure_type='new',
                ai_service=ai_service if sidebar_settings['use_ai'] else None,
                ai_settings=sidebar_settings
            )


def _render_existing_failures_tab(result, file_idx, ai_service, sidebar_settings):
    """Render existing failures tab"""
    if result['existing_count'] == 0:
        st.info("ℹ️ No existing failures found in baseline")
    else:
        st.warning(f"Found {result['existing_count']} known failures")
        for i, failure in enumerate(result['existing_failures']):
            render_failure_details(
                failure=failure,
                idx=i,
                file_idx=file_idx,
                failure_type='existing',
                ai_service=None,  # Don't show AI for existing failures
                ai_settings=None
            )


def _render_actions_tab(result, idx, baseline_service, sidebar_settings):
    """Render actions tab with baseline management"""
    st.markdown("### 🛠️ Baseline Management")
    
    # Project selection
    st.markdown("### 📌 Select Project for Baseline")
    selected_project = result['project']
    
    if result['project'] == "UNKNOWN_PROJECT":
        selected_project = st.selectbox(
            "Choose correct project",
            options=KNOWN_PROJECTS,
            key=f"project_select_{idx}"
        )
    else:
        st.info(f"Detected Project: {result['project']}")
    
    # Save baseline
    col1, col2 = st.columns(2)
    
    with col1:
        baseline_label = st.text_input(
            "Baseline Label",
            value="Auto",
            key=f"label_{idx}",
            help="Custom label for this baseline"
        )
    
    with col2:
        if st.button(f"💾 Save as Baseline", key=f"save_provar_{idx}"):
            _save_provar_baseline(
                result=result,
                selected_project=selected_project,
                baseline_label=baseline_label,
                baseline_service=baseline_service,
                admin_key=sidebar_settings['admin_key']
            )
    
    # Export options
    st.markdown("---")
    render_export_section(result, idx, "provar")


def _save_provar_baseline(result, selected_project, baseline_label, baseline_service, admin_key):
    """Save Provar baseline"""
    if not admin_key:
        st.error("❌ Admin key required!")
        return
    
    expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
    if admin_key != expected_key:
        st.error("❌ Invalid admin key")
        return
    
    if selected_project == "UNKNOWN_PROJECT":
        st.error("Please select a project before saving baseline.")
        return
    
    try:
        all_failures = result['new_failures'] + result['existing_failures']
        baseline_id = baseline_service.save(
            project=selected_project,
            platform="provar",
            failures=all_failures,
            label=baseline_label if baseline_label else None
        )
        st.success(f"✅ Baseline saved! ID: {baseline_id}")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")


def _render_provar_welcome():
    """Render welcome message when no files uploaded"""
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