"""
AutomationAPI-specific UI components
"""
import streamlit as st
import os
from ui.results_view import render_export_section

def render_api_analysis(analysis_service, ai_service, baseline_service,
                        sidebar_settings, extract_func, group_func, stats_func):
    """Render AutomationAPI analysis interface"""
    
    st.markdown("## 🔧 Upload AutomationAPI XML Reports")
    st.markdown("Upload XML reports from AutomationAPI test executions (e.g., Jasmine/Selenium tests)")
    
    uploaded_api_files = st.file_uploader(
        "Choose AutomationAPI XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="api_uploader",
        help="Upload XML reports from AutomationAPI workspace"
    )
    
    if not uploaded_api_files:
        _render_api_welcome()
        return
    
    st.success(f"✅ {len(uploaded_api_files)} AutomationAPI file(s) uploaded!")
    
    # Initialize session state
    if 'api_results' not in st.session_state:
        st.session_state.api_results = []
    
    # Analysis Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_api = st.button(
            "🔍 Analyze AutomationAPI Reports",
            type="primary",
            use_container_width=True
        )
    
    if analyze_api:
        _process_api_files(
            uploaded_files=uploaded_api_files,
            analysis_service=analysis_service,
            extract_func=extract_func,
            group_func=group_func,
            stats_func=stats_func
        )
    
    # Display Results
    if st.session_state.api_results:
        _display_api_results(
            results=st.session_state.api_results,
            ai_service=ai_service,
            baseline_service=baseline_service,
            sidebar_settings=sidebar_settings
        )


def _process_api_files(uploaded_files, analysis_service, extract_func, 
                      group_func, stats_func):
    """Process uploaded AutomationAPI files"""
    
    st.session_state.api_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def progress_callback(idx, total, filename):
        status_text.text(f"Processing {filename}... ({idx + 1}/{total})")
        progress_bar.progress((idx + 1) / total)
    
    # Analyze files
    results = analysis_service.analyze_batch_api(
        uploaded_files=uploaded_files,
        extract_func=extract_func,
        group_func=group_func,
        stats_func=stats_func,
        progress_callback=progress_callback
    )
    
    st.session_state.api_results = results
    status_text.text("✅ Analysis complete!")
    progress_bar.empty()
    
    # Update statistics
    total_failures = sum(r['stats']['total_failures'] for r in results)
    new_failures = sum(len(r['new_failures']) for r in results)
    
    st.session_state.upload_stats = {
        'count': len(uploaded_files),
        'total_failures': total_failures,
        'new_failures': new_failures
    }


def _display_api_results(results, ai_service, baseline_service, sidebar_settings):
    """Display AutomationAPI analysis results"""
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown("## 📊 AutomationAPI Analysis Results")
    
    # Overall statistics
    _render_api_summary(results)
    
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    # Individual file results
    for idx, result in enumerate(results):
        with st.expander(
            f"📄 {result['filename']} — Project: {result['project']} | "
            f"⏰ {result['timestamp']} | "
            f"Failures: {result['stats']['total_failures']}",
            expanded=False
        ):
            _render_api_file_result(
                result=result,
                idx=idx,
                ai_service=ai_service,
                baseline_service=baseline_service,
                sidebar_settings=sidebar_settings
            )


def _render_api_summary(results):
    """Render overall API statistics"""
    total_real = sum(r['stats']['real_failures'] for r in results)
    total_skipped = sum(r['stats']['skipped_failures'] for r in results)
    total_all = sum(r['stats']['total_failures'] for r in results)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📄 Total Files", len(results))
    with col2:
        st.metric("🔴 Real Failures", total_real)
    with col3:
        st.metric("🟡 Skipped Failures", total_skipped)
    with col4:
        st.metric("📈 Total Failures", total_all)


def _render_api_file_result(result, idx, ai_service, baseline_service, sidebar_settings):
    """Render individual API file result"""
    
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
    
    # Baseline Comparison Summary
    if result['baseline_exists'] and (result['new_failures'] or result['existing_failures']):
        _render_baseline_comparison_summary(result)
        st.markdown("---")
    elif result['baseline_exists']:
        st.success("✅ No failures detected! All tests passed.")
    else:
        st.info("ℹ️ No baseline found. All failures are considered new. Save a baseline to track changes.")
    
    st.markdown("---")
    
    # Display failures grouped by spec
    _render_spec_failures(result, idx, ai_service, sidebar_settings)
    
    # Baseline Management
    _render_api_baseline_management(result, idx, baseline_service, sidebar_settings)
    
    # Export options
    st.markdown("---")
    render_export_section(result, idx, "automation_api")


def _render_baseline_comparison_summary(result):
    """Render baseline comparison summary for API results"""
    st.markdown("### 📊 Baseline Comparison Summary")
    
    # Separate failures by spec
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
    
    # Categorize specs
    all_specs = set(new_by_spec.keys()) | set(existing_by_spec.keys())
    new_specs = [s for s in new_by_spec.keys() if s not in existing_by_spec]
    mixed_specs = [s for s in all_specs if s in new_by_spec and s in existing_by_spec]
    existing_only_specs = [s for s in existing_by_spec.keys() if s not in new_by_spec]
    
    # Display summary cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🆕 New Spec Files", len(new_specs), 
                 help="Spec files that are completely new (not in baseline)")
    with col2:
        st.metric("📊 Specs with New Tests", len(mixed_specs),
                 help="Spec files with mix of new and existing failures")
    with col3:
        st.metric("♻️ Specs with Known Failures", len(existing_only_specs),
                 help="Spec files with only existing (baseline) failures")
    
    # Display spec details (collapsed by default)
    if new_specs or mixed_specs:
        with st.expander("👁️ View Spec Breakdown", expanded=False):
            if new_specs:
                st.markdown("**🆕 New Spec Files:**")
                for spec in sorted(new_specs):
                    st.markdown(f"- {spec} ({len(new_by_spec[spec])} failures)")
            
            if mixed_specs:
                st.markdown("**📊 Mixed Spec Files:**")
                for spec in sorted(mixed_specs):
                    st.markdown(f"- {spec} ({len(new_by_spec[spec])} new, {len(existing_by_spec[spec])} existing)")


def _render_spec_failures(result, file_idx, ai_service, sidebar_settings):
    """Render failures grouped by spec"""
    if not result['grouped_failures']:
        return
    
    for spec_name, spec_failures in result['grouped_failures'].items():
        st.markdown(f"### 📋 Spec: `{spec_name}`")
        st.caption(f"{len(spec_failures)} failure(s) in this spec")
        
        for i, failure in enumerate(spec_failures):
            icon = "🟡" if failure['is_skipped'] else "🔴"
            failure_class = "skipped-failure" if failure['is_skipped'] else "real-failure"
            
            with st.expander(
                f"{icon} {i+1}. {failure['test_name']} ({failure['execution_time']}s)",
                expanded=False
            ):
                st.markdown(f"<div class='{failure_class}'>", unsafe_allow_html=True)
                
                if failure['is_skipped']:
                    st.warning("⚠️ Skipped due to previous failure")
                
                st.write("**Test:**", failure['test_name'])
                st.write("**Type:**", failure['failure_type'])
                st.error(f"**Error:** {failure['error_summary']}")
                
                with st.expander("📋 Full Error Details"):
                    st.code(failure['error_details'], language="text")
                
                if failure['full_stack_trace']:
                    with st.expander("🔍 Stack Trace"):
                        st.code(failure['full_stack_trace'], language="text")
                
                # AI Features (only for real failures)
                if sidebar_settings['use_ai'] and not failure['is_skipped']:
                    _render_api_ai_features(failure, file_idx, i, ai_service, sidebar_settings)
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("---")


def _render_api_ai_features(failure, file_idx, idx, ai_service, sidebar_settings):
    """Render AI features for API failures"""
    st.markdown("---")
    ai_tabs = ["🤖 AI Analysis"]
    
    if sidebar_settings.get('enable_jira_generation'):
        ai_tabs.append("📝 Jira Ticket")
    if sidebar_settings.get('enable_test_improvements'):
        ai_tabs.append("💡 Improvements")
    
    ai_tab_objects = st.tabs(ai_tabs)
    
    with ai_tab_objects[0]:
        with st.spinner("Analyzing..."):
            ai_analysis = ai_service.generate_summary(
                failure['test_name'],
                failure['error_summary'],
                failure['error_details']
            )
            st.info(ai_analysis)
    
    if sidebar_settings.get('enable_jira_generation') and len(ai_tab_objects) > 1:
        with ai_tab_objects[1]:
            with st.spinner("Generating Jira ticket..."):
                jira_content = ai_service.generate_jira_ticket(
                    failure['test_name'],
                    failure['error_summary'],
                    failure['error_details']
                )
                st.markdown(jira_content)
                st.download_button(
                    "📥 Download Jira Content",
                    jira_content,
                    file_name=f"jira_{failure['test_name'][:30]}.txt",
                    key=f"jira_api_{file_idx}_{idx}"
                )
    
    if sidebar_settings.get('enable_test_improvements') and len(ai_tab_objects) > 2:
        with ai_tab_objects[-1]:
            with st.spinner("Generating improvement suggestions..."):
                improvements = ai_service.suggest_improvements(
                    failure['test_name'],
                    failure['error_summary'],
                    failure['error_details']
                )
                st.success(improvements)


def _render_api_baseline_management(result, idx, baseline_service, sidebar_settings):
    """Render baseline management for API results"""
    st.markdown("### 🛠️ Baseline Management")
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
            _save_api_baseline(
                result=result,
                baseline_label=baseline_label,
                baseline_service=baseline_service,
                admin_key=sidebar_settings['admin_key']
            )


def _save_api_baseline(result, baseline_label, baseline_service, admin_key):
    """Save AutomationAPI baseline"""
    if not admin_key:
        st.error("❌ Admin key required!")
        return
    
    expected_key = os.getenv("BASELINE_ADMIN_KEY", "admin123")
    if admin_key != expected_key:
        st.error("❌ Invalid admin key")
        return
    
    try:
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


def _render_api_welcome():
    """Render welcome message for API analysis"""
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