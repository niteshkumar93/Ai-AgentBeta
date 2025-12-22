import os
import json
from datetime import datetime

BASELINE_DIR = "data/baseline"
os.makedirs(BASELINE_DIR, exist_ok=True)

MAX_BASELINES_PER_PROJECT = 10


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _project_dir(project: str):
    path = os.path.join(BASELINE_DIR, project)
    os.makedirs(path, exist_ok=True)
    return path


def _baseline_path(project: str, baseline_id: str):
    return os.path.join(_project_dir(project), f"{baseline_id}.json")


# -------------------------------------------------
# Core APIs (BACKWARD COMPATIBLE)
# -------------------------------------------------
def save_baseline(project: str, failures: list, label: str | None = None):
    """
    Save a new baseline for a project.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    baseline_id = f"baseline_{ts}"

    payload = {
        "id": baseline_id,
        "project": project,
        "label": label or "Auto",
        "created_at": ts,
        "total_failures": len(failures),
        "failures": failures,
    }

    path = _baseline_path(project, baseline_id)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    _enforce_limit(project)
    return baseline_id


def load_baseline(project: str, baseline_id: str):
    path = _baseline_path(project, baseline_id)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


# -------------------------------------------------
# Multi-baseline APIs (NEW)
# -------------------------------------------------
def list_baselines(project: str):
    """
    Returns baselines sorted newest → oldest
    """
    path = _project_dir(project)
    baselines = []

    for f in os.listdir(path):
        if f.endswith(".json"):
            with open(os.path.join(path, f)) as jf:
                baselines.append(json.load(jf))

    return sorted(baselines, key=lambda x: x["created_at"], reverse=True)


def get_latest_baseline(project: str):
    baselines = list_baselines(project)
    return baselines[0] if baselines else None


def delete_baseline(project: str, baseline_id: str):
    path = _baseline_path(project, baseline_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def get_baseline_stats(project: str):
    baselines = list_baselines(project)
    return {
        "count": len(baselines),
        "latest": baselines[0]["created_at"] if baselines else None,
    }


# -------------------------------------------------
# Safety
# -------------------------------------------------
def _enforce_limit(project: str):
    baselines = list_baselines(project)
    if len(baselines) <= MAX_BASELINES_PER_PROJECT:
        return

    # delete oldest
    for b in baselines[MAX_BASELINES_PER_PROJECT:]:
        delete_baseline(project, b["id"])
