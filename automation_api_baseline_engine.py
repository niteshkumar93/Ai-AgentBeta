# automation_api_baseline_engine.py
"""
Multi-Baseline Engine for AutomationAPI Reports
Separate from Provar baselines, stores up to 10 baselines per project
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional


def automation_failure_signature(failure: dict) -> str:
    interaction = failure.get("interaction", {}) or {}

    return "|".join([
        failure.get("spec_file", ""),
        failure.get("test_name", ""),
        failure.get("error_summary", ""),
        str(interaction.get("ActualValue", "")),
        str(interaction.get("ExpectedValue", "")),
    ])

# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------
BASELINE_DIR = "data/baseline_automation_api"
os.makedirs(BASELINE_DIR, exist_ok=True)

MAX_BASELINES_PER_PROJECT = 10

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _project_dir(project: str):
    """Get or create project directory"""
    path = os.path.join(BASELINE_DIR, project)
    os.makedirs(path, exist_ok=True)
    return path


def _baseline_path(project: str, baseline_id: str):
    """Get path to a specific baseline file"""
    return os.path.join(_project_dir(project), f"{baseline_id}.json")


def _format_timestamp(ts: str):
    """Format timestamp for display"""
    try:
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return ts


# -------------------------------------------------
# Core APIs - Multi-Baseline Support
# -------------------------------------------------
def save_baseline(project: str, failures: list, label: str = None):
    """
    Save a new baseline for an AutomationAPI project.
    Returns the baseline_id of the saved baseline.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    baseline_id = f"baseline_{ts}"
    
    # Clean up failures before saving
    clean_failures = []
    for f in failures:
        # Skip metadata-only records
        if f.get("_no_failures"):
            continue
        
        # Create clean failure record
        clean_failure = {
            "project": f.get("project"),
            "spec_file": f.get("spec_file"),
            "test_name": f.get("test_name"),
            "error_summary": f.get("error_summary"),
            "error_details": f.get("error_details", ""),
            "is_skipped": f.get("is_skipped", False),
            "failure_type": f.get("failure_type", ""),
            "execution_time": f.get("execution_time", "0")
        }
        clean_failures.append(clean_failure)
    
    payload = {
        "id": baseline_id,
        "project": project,
        "label": label or "Auto",
        "created_at": ts,
        "failure_count": len(clean_failures),
        "failures": clean_failures,
    }

    path = _baseline_path(project, baseline_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    _enforce_limit(project)
    return baseline_id


def load_baseline(project: str, baseline_id: str) -> Optional[Dict]:
    """Load a specific baseline by ID"""
    path = _baseline_path(project, baseline_id)
    if not os.path.exists(path):
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading baseline {baseline_id} for {project}: {e}")
        return None


def list_baselines(project: str) -> List[Dict]:
    """
    Returns list of all baselines for a project, sorted newest → oldest
    """
    path = _project_dir(project)
    baselines = []

    if not os.path.exists(path):
        return []

    for f in os.listdir(path):
        if f.endswith(".json"):
            try:
                with open(os.path.join(path, f), encoding="utf-8") as jf:
                    baseline = json.load(jf)
                    if "id" in baseline and "created_at" in baseline:
                        baselines.append(baseline)
            except Exception as e:
                print(f"Error loading baseline file {f}: {e}")
                continue

    return sorted(baselines, key=lambda x: x["created_at"], reverse=True)


def get_latest_baseline(project: str) -> Optional[Dict]:
    """Get the most recent baseline for a project"""
    baselines = list_baselines(project)
    return baselines[0] if baselines else None


def delete_baseline(project: str, baseline_id: str) -> bool:
    """Delete a specific baseline"""
    path = _baseline_path(project, baseline_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except Exception as e:
            print(f"Error deleting baseline {baseline_id}: {e}")
            return False
    return False


def get_baseline_stats(project: str) -> Dict:
    """Get statistics about baselines for a project"""
    baselines = list_baselines(project)
    return {
        "count": len(baselines),
        "latest": baselines[0]["created_at"] if baselines else None,
        "oldest": baselines[-1]["created_at"] if baselines else None,
        "total_failures": sum(b.get("failure_count", 0) for b in baselines),
    }


def compare_with_baseline(project: str, current_failures: list, baseline_id: str = None):
    """
    Compare current failures with a baseline (latest if not specified).
    Uses: spec_file|test_name|error_summary for matching
    Returns (new_failures, existing_failures)
    """
    if baseline_id:
        baseline = load_baseline(project, baseline_id)
    else:
        baseline = get_latest_baseline(project)
    
    if not baseline:
        # Filter out metadata records
        real_failures = [f for f in current_failures if not f.get("_no_failures")]
        return real_failures, []
    
    baseline_failures = baseline.get("failures", [])
    
    # Create keys for comparison (spec_file|test_name|error_summary)
    baseline_keys = set()
    for f in baseline_failures:
        spec = f.get('spec_file', '')
        test = f.get('test_name', '')
        error = f.get('error_summary', '')
        sig = f"{spec}|{test}|{error}"
        baseline_keys.add(sig)
    
    new_failures = []
    existing_failures = []
    
    for failure in current_failures:
        # Skip metadata records
        if failure.get("_no_failures"):
            continue
        
        spec = failure.get('spec_file', '')
        test = failure.get('test_name', '')
        error = failure.get('error_summary', '')
        sig = f"{spec}|{test}|{error}"
        
        if sig in baseline_keys:
            existing_failures.append(failure)
        else:
            new_failures.append(failure)
    
    return new_failures, existing_failures


def get_all_projects() -> List[str]:
    """Get list of all AutomationAPI projects that have baselines"""
    if not os.path.exists(BASELINE_DIR):
        return []
    
    projects = []
    for item in os.listdir(BASELINE_DIR):
        path = os.path.join(BASELINE_DIR, item)
        if os.path.isdir(path):
            projects.append(item)
    
    return sorted(projects)


def baseline_exists(project: str) -> bool:
    """Check if any baseline exists for a project"""
    baselines = list_baselines(project)
    return len(baselines) > 0


# -------------------------------------------------
# Safety - Enforce baseline limit
# -------------------------------------------------
def _enforce_limit(project: str):
    """
    Ensure no more than MAX_BASELINES_PER_PROJECT baselines exist.
    Deletes oldest baselines if limit exceeded.
    """
    baselines = list_baselines(project)
    if len(baselines) <= MAX_BASELINES_PER_PROJECT:
        return

    # Delete oldest baselines
    for b in baselines[MAX_BASELINES_PER_PROJECT:]:
        delete_baseline(project, b["id"])
        print(f"Deleted old baseline {b['id']} for project {project}")