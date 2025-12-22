import os
import json
from datetime import datetime

BASELINE_DIR = "data/baseline"
MAX_BASELINES_PER_PROJECT = 10

os.makedirs(BASELINE_DIR, exist_ok=True)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _project_dir(project: str) -> str:
    path = os.path.join(BASELINE_DIR, project)
    os.makedirs(path, exist_ok=True)
    return path

def _baseline_path(project: str, baseline_id: str) -> str:
    return os.path.join(_project_dir(project), f"{baseline_id}.json")

# -------------------------------------------------
# Core APIs (USED BY UI)
# -------------------------------------------------
def list_baselines(project: str):
    """Return list of baselines (latest first)"""
    path = _project_dir(project)
    baselines = []

    for f in os.listdir(path):
        if f.endswith(".json"):
            with open(os.path.join(path, f), "r") as fp:
                data = json.load(fp)
                baselines.append(data)

    baselines.sort(key=lambda x: x["created_at"], reverse=True)
    return baselines

def get_latest_baseline(project: str):
    baselines = list_baselines(project)
    return baselines[0] if baselines else None

def save_baseline(project: str, failures: list, label: str = "", admin_key: str = None):
    if not admin_key:
        raise PermissionError("Admin key required")

    existing = list_baselines(project)
    if len(existing) >= MAX_BASELINES_PER_PROJECT:
        raise ValueError("Maximum 10 baselines allowed per project")

    baseline_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    data = {
        "baseline_id": baseline_id,
        "project": project,
        "label": label or "Auto baseline",
        "created_at": datetime.utcnow().isoformat(),
        "failure_count": len(failures),
        "failures": failures,
    }

    with open(_baseline_path(project, baseline_id), "w") as f:
        json.dump(data, f, indent=2)

    return data

def delete_baseline(project: str, baseline_id: str, admin_key: str = None):
    if not admin_key:
        raise PermissionError("Admin key required")

    path = _baseline_path(project, baseline_id)
    if os.path.exists(path):
        os.remove(path)

def compare_with_baseline(baseline_data: dict, current_failures: list):
    baseline_keys = {f["testcase"]: f for f in baseline_data["failures"]}
    current_keys = {f["testcase"]: f for f in current_failures}

    new_failures = [
        f for k, f in current_keys.items() if k not in baseline_keys
    ]

    existing_failures = [
        f for k, f in current_keys.items() if k in baseline_keys
    ]

    fixed_failures = [
        f for k, f in baseline_keys.items() if k not in current_keys
    ]

    return new_failures, existing_failures, fixed_failures
