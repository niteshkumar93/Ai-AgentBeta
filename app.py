"""
Main Entry Point for Provar AI – Multi-Platform Report Analyzer

DO NOT put business logic here.
This file exists only to launch the real Streamlit app.

All features live in:
    streamlit_app.py
"""

import streamlit as st
import runpy
import os
import sys

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ------------------------------------------------------------
# BOOTSTRAP STREAMLIT APPLICATION
# ------------------------------------------------------------
if __name__ == "__main__":
    runpy.run_path(
        os.path.join(PROJECT_ROOT, "streamlit_app.py"),
        run_name="__main__"
    )
