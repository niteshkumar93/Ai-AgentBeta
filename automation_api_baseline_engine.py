import os
import json
from datetime import datetime
from typing import List, Dict

# -------------------------------------------------
# CONFIGURATION
# -------------------------------------------------
BASELINE_DIR = "data/baseline"
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


def _create_failure_signature(failure: Dict) -> str:
    """
    Create unique signature for AutomationAPI failure comparison.
    Uses: spec_file + test_name + error_summary
    """
    spec = failure.get('spec_file', '')
    test = failure.get('test_name', '')
    error = failure.get('error_summary', '')
    return f"{spec}|{test}|{error}"


# -------------------------------------------------
# Core APIs - Multi-Baseline Support for AutomationAPI
# -------------------------------------------------
def save_baseline(project: str, failures: list, label: str | None = None):
    """
    Save a new AutomationAPI baseline for a project.
    Returns the baseline_id of the saved baseline.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    baseline_id = f"baseline_{ts}"

    # Clean failures - remove metadata records and internal flags
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
        "type": "AutomationAPI"  # Mark as AutomationAPI baseline
    }

    path = _baseline_path(project, baseline_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    _enforce_limit(project)
    return baseline_id


def load_baseline(project: str, baseline_id: str):
    """Load a specific AutomationAPI baseline by ID"""
    path = _baseline_path(project, baseline_id)
    if not os.path.exists(path):
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading baseline {baseline_id} for {project}: {e}")
        return None


def list_baselines(project: str):
    """
    Returns list of all AutomationAPI baselines for a project, sorted newest → oldest
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
                    # Ensure all required fields exist
                    if "id" in baseline and "created_at" in baseline:
                        baselines.append(baseline)
            except Exception as e:
                print(f"Error loading baseline file {f}: {e}")
                continue

    return sorted(baselines, key=lambda x: x["created_at"], reverse=True)


def get_latest_baseline(project: str):
    """Get the most recent AutomationAPI baseline for a project"""
    baselines = list_baselines(project)
    return baselines[0] if baselines else None


def delete_baseline(project: str, baseline_id: str):
    """Delete a specific AutomationAPI baseline"""
    path = _baseline_path(project, baseline_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except Exception as e:
            print(f"Error deleting baseline {baseline_id}: {e}")
            return False
    return False


def get_baseline_stats(project: str):
    """Get statistics about AutomationAPI baselines for a project"""
    baselines = list_baselines(project)
    return {
        "count": len(baselines),
        "latest": baselines[0]["created_at"] if baselines else None,
        "oldest": baselines[-1]["created_at"] if baselines else None,
        "total_failures": sum(b.get("failure_count", 0) for b in baselines),
    }


def compare_with_baseline(project: str, current_failures: list, baseline_id: str = None):
    """
    Compare current AutomationAPI failures with a baseline (latest if not specified).
    Returns (new_failures, existing_failures)
    """
    # Load baseline
    if baseline_id:
        baseline = load_baseline(project, baseline_id)
    else:
        baseline = get_latest_baseline(project)
    
    if not baseline:
        # Filter out metadata records
        real_failures = [f for f in current_failures if not f.get("_no_failures")]
        return real_failures, []
    
    baseline_failures = baseline.get("failures", [])
    
    # Create signature set for baseline
    baseline_sigs = {
        _create_failure_signature(f)
        for f in baseline_failures
    }
    
    new_failures = []
    existing_failures = []
    
    for failure in current_failures:
        # Skip metadata records
        if failure.get("_no_failures"):
            continue
        
        sig = _create_failure_signature(failure)
        
        if sig in baseline_sigs:
            existing_failures.append(failure)
        else:
            new_failures.append(failure)
    
    return new_failures, existing_failures


def baseline_exists(project: str):
    """Check if any AutomationAPI baseline exists for a project"""
    baselines = list_baselines(project)
    return len(baselines) > 0


def get_all_projects():
    """Get list of all AutomationAPI projects that have baselines"""
    if not os.path.exists(BASELINE_DIR):
        return []
    
    projects = []
    for item in os.listdir(BASELINE_DIR):
        path = os.path.join(BASELINE_DIR, item)
        if os.path.isdir(path):
            # Check if it's an AutomationAPI project by looking at baseline type
            for file in os.listdir(path):
                if file.endswith(".json"):
                    try:
                        with open(os.path.join(path, file), "r") as f:
                            baseline = json.load(f)
                            if baseline.get("type") == "AutomationAPI":
                                projects.append(item)
                                break
                    except:
                        continue
    
    return sorted(projects)


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
        print(f"Deleted old AutomationAPI baseline {b['id']} for project {project}")