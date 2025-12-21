import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
from datetime import datetime

from xml_extractor import extract_failed_tests
from ai_reasoner import (
    generate_ai_summary,
    generate_batch_analysis,
    generate_jira_ticket,
    suggest_test_improvements
)
from baseline_manager import save_baseline, compare_with_baseline, load_baseline

# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def format_execution_time(raw_time: str):
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


KNOWN_PROJECTS = [
    "VF_Lightning_Windows", "Regmain-Flexi", "Date_Time",
    "CPQ_Classic", "CPQ_Lightning", "QAM_Lightning", "QAM_Classic",
    "Internationalization_pipeline", "Lightning_Console_LogonAs",
    "DynamicForm", "Classic_Console_LogonAS", "LWC_Pipeline",
    "Regmain_LS_Windows", "Regmain_LC_Windows",
    "Regmain-VF", "FSL", "HYBRID_AUTOMATION_Pipeline",
]

APP_VERSION = "2.2.0"


def safe_extract_failures(uploaded_file):
    try:
        uploaded_file.seek(0)
        return extract_failed_tests(uploaded_file)
    except Exception as e:
        st.error(f"Error parsing {uploaded_file.name}: {str(e)}")
        return []


def detect_project(path: str, filename: str):
    for p in KNOWN_PROJECTS:
        if path and (f"/{p}" in path or f"\\{p}" in path):
            return p
        if p.lower() in filename.lower():
            return p
    return KNOWN_PROJECTS[0]


def shorten_project_cache_path(path):
    if not path:
        return ""
    marker = "Jenkins\\"
    if marker in path:
        return path.split(marker, 1)[1]
    return path.replace("/", "\\").split("\\")[-1]


def render_summary_card(xml_name, new_count, existing_count, total_count):
    status_color = "🟢" if new_count == 0 else "🔴"
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Status", status_color)
    with col2:
        st.metric("New Failures", new_count)
    with col3:
        st.metric("Existing Failures", existing_count)
    with col4:
        st.metric("Total Failures", total_count)


def render_comparison_chart(all_results):
    if not all_results:
        return

    df = pd.DataFrame([
        {
            "File": r["filename"][:30],
            "New": r["new_count"],
            "Existing": r["existing_count"]
        } for r in all_results
    ])

    fig = go.Figure()
    fig.add_bar(name="New Failures", x=df["File"], y=df["New"])
    fig.add_bar(name="Existing Failures", x=df["File"], y=df["Existing"])
    fig.update_layout(barmode="stack", height=400)

    st.plotly_chart(fig, use_container_width=True)


# -----------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------
st.set_page_config("Provar AI - Enhanced XML Analyzer", layout="wide", page_icon="🚀")

st.markdown(
    '<div style="font-size:2.3rem;font-weight:bold;text-align:center;color:#1f77b4;">'
    '🤖 Provar AI Report Analysis and Baseline Tool</div>',
    unsafe_allow_html=True
)

# -----------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configuration")

    analysis_mode = st.radio(
        "🔀 Analysis Mode",
        ["XML Analyzer", "AutomationAPI"],
        index=0
    )

    use_ai = st.checkbox("Enable AI Analysis", value=False)

    with st.expander("🎯 Advanced AI Features"):
        enable_batch_analysis = st.checkbox("Batch Pattern Analysis", True)
        enable_jira_generation = st.checkbox("Jira Ticket Generation", True)
        enable_test_improvements = st.checkbox("Test Improvement Suggestions", False)

    admin_key = st.text_input("🔐 Admin Key", type="password")

    st.markdown("---")
    st.caption(f"Version: {APP_VERSION}")


# ===========================================================
# XML ANALYZER (UNCHANGED LOGIC)
# ===========================================================
if analysis_mode == "XML Analyzer":

    st.markdown("## 📁 Upload XML Reports")

    uploaded_files = st.file_uploader(
        "Choose XML files",
        type=["xml"],
        accept_multiple_files=True
    )

    if uploaded_files:

        if "all_results" not in st.session_state:
            st.session_state.all_results = []

        if st.button("🔍 Analyze All Reports", type="primary"):
            st.session_state.all_results = []

            for xml_file in uploaded_files:
                failures = safe_extract_failures(xml_file)
                if not failures:
                    continue

                project = detect_project(
                    failures[0].get("projectCachePath", ""),
                    xml_file.name
                )

                execution_time = failures[0].get("timestamp", "Unknown")

                normalized = []
                for f in failures:
                    if f.get("name") != "__NO_FAILURES__":
                        normalized.append({
                            "testcase": f["name"],
                            "testcase_path": f.get("testcase_path", ""),
                            "error": f["error"],
                            "details": f["details"],
                            "webBrowserType": f.get("webBrowserType", "Unknown"),
                            "projectCachePath": shorten_project_cache_path(
                                f.get("projectCachePath", "")
                            ),
                        })

                baseline_exists = bool(load_baseline(project))
                if baseline_exists:
                    new_f, existing_f = compare_with_baseline(project, normalized)
                else:
                    new_f, existing_f = normalized, []

                st.session_state.all_results.append({
                    "filename": xml_file.name,
                    "project": project,
                    "execution_time": execution_time,
                    "new_failures": new_f,
                    "existing_failures": existing_f,
                    "new_count": len(new_f),
                    "existing_count": len(existing_f),
                    "total_count": len(normalized),
                    "baseline_exists": baseline_exists
                })

        if st.session_state.get("all_results"):
            render_comparison_chart(st.session_state.all_results)

            for idx, result in enumerate(st.session_state.all_results):
                with st.expander(
                    f"{result['filename']} | "
                    f"{format_execution_time(result['execution_time'])} | "
                    f"{result['project']}"
                ):
                    render_summary_card(
                        result["filename"],
                        result["new_count"],
                        result["existing_count"],
                        result["total_count"]
                    )


# ===========================================================
# AUTOMATION API (PLACEHOLDER ONLY)
# ===========================================================
else:
    st.markdown("## ⚙️ AutomationAPI")

    st.file_uploader(
        "Upload AutomationAPI XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="automation_api_uploader"
    )

    st.info(
        "AutomationAPI mode is enabled.\n\n"
        "Next step:\n"
        "- Custom XML parsing\n"
        "- Separate baseline\n"
        "- API-specific failure logic"
    )
