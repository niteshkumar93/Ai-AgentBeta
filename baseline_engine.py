import os
import json
from datetime import datetime

BASELINE_DIR = "data/baseline"
os.makedirs(BASELINE_DIR, exist_ok=True)

MAX_BASELINES = 10


# -----------------------------
# Internal helpers
# -----------------------------
def _project_file(project: str) -> str:
    safe_project = project.replace(" ", "_")
    return os.path.join(BASELINE_DIR, f"{safe_project}.json")


def _load_project_data(project: str) -> dict:
    path = _project_file(project)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {"baselines": []}


def _save_project_data(project: str, data: dict):
    with open(_project_file(project), "w") as f:
        json.dump(data, f, indent=2)


# -----------------------------
# PUBLIC API (USED BY APP/UI)
# -----------------------------

def list_projects():
    return [
        f.replace(".json", "")
        for f in os.listdir(BASELINE_DIR)
        if f.endswith(".json")
    ]


def list_baselines(project: str):
    data = _load_project_data(project)
    return data.get("baselines", [])


def save_baseline(
    project: str,
    failures: list,
    label: str | None = None,
):
    data = _load_project_data(project)

    baseline = {
        "id": datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.utcnow().isoformat(),
        "label": label or "Unnamed baseline",
        "total_failures": len(failures),
        "failures": failures,
    }

    data["baselines"].append(baseline)

    # Keep only last N baselines
    data["baselines"] = data["baselines"][-MAX_BASELINES :]

    _save_project_data(project, data)


def delete_baseline(project: str, baseline_id: str):
    data = _load_project_data(project)
    data["baselines"] = [
        b for b in data["baselines"] if b["id"] != baseline_id
    ]
    _save_project_data(project, data)


def get_latest_baseline(project: str):
    baselines = list_baselines(project)
    return baselines[-1] if baselines else None


def compare_with_baseline(project: str, new_failures: list):
    """
    Default comparison → latest baseline only
    """
    baseline = get_latest_baseline(project)
    if not baseline:
        return new_failures, []

    old_set = {
        (f["testcase"], f["error"])
        for f in baseline["failures"]
    }

    new_set = {
        (f["testcase"], f["error"])
        for f in new_failures
    }

    new_only = [
        f for f in new_failures
        if (f["testcase"], f["error"]) not in old_set
    ]

    existing = [
        f for f in new_failures
        if (f["testcase"], f["error"]) in old_set
    ]

    return new_only, existing
