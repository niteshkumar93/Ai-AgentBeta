import os
import json
from datetime import datetime

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


# -------------------------------------------------
# Core APIs - Multi-Baseline Support
# -------------------------------------------------
def save_baseline(project: str, failures: list, label: str | None = None):
    """
    Save a new baseline for a project.
    Returns the baseline_id of the saved baseline.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    baseline_id = f"baseline_{ts}"

    payload = {
        "id": baseline_id,
        "project": project,
        "label": label or "Auto",
        "created_at": ts,
        "failure_count": len(failures),
        "failures": failures,
    }

    path = _baseline_path(project, baseline_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    _enforce_limit(project)
    return baseline_id


def load_baseline(project: str, baseline_id: str):
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


def list_baselines(project: str):
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
                    # Ensure all required fields exist
                    if "id" in baseline and "created_at" in baseline:
                        baselines.append(baseline)
            except Exception as e:
                print(f"Error loading baseline file {f}: {e}")
                continue

    return sorted(baselines, key=lambda x: x["created_at"], reverse=True)


def get_latest_baseline(project: str):
    """Get the most recent baseline for a project"""
    baselines = list_baselines(project)
    return baselines[0] if baselines else None


def delete_baseline(project: str, baseline_id: str):
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


def get_baseline_stats(project: str):
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
    Returns (new_failures, existing_failures)
    """
    if baseline_id:
        baseline = load_baseline(project, baseline_id)
    else:
        baseline = get_latest_baseline(project)
    
    if not baseline:
        return current_failures, []
    
    baseline_failures = baseline.get("failures", [])
    
    # Create keys for comparison (testcase + error)
    baseline_keys = {
        f"{f.get('testcase', '')}|{f.get('error', '')}"
        for f in baseline_failures
    }
    
    new_failures = []
    existing_failures = []
    
    for failure in current_failures:
        key = f"{failure.get('testcase', '')}|{failure.get('error', '')}"
        if key in baseline_keys:
            existing_failures.append(failure)
        else:
            new_failures.append(failure)
    
    return new_failures, existing_failures


def get_all_projects():
    """Get list of all projects that have baselines"""
    if not os.path.exists(BASELINE_DIR):
        return []
    
    projects = []
    for item in os.listdir(BASELINE_DIR):
        path = os.path.join(BASELINE_DIR, item)
        if os.path.isdir(path):
            projects.append(item)
    
    return sorted(projects)


def baseline_exists(project: str):
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