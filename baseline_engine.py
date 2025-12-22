import os
import json
from datetime import datetime

BASELINE_DIR = "data/baseline"
os.makedirs(BASELINE_DIR, exist_ok=True)

MAX_BASELINES_PER_PROJECT = 10


def _project_file(project):
    return os.path.join(BASELINE_DIR, f"{project}.json")


def load_project_baselines(project):
    path = _project_file(project)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def save_project_baseline(project, failures, label=None):
    baselines = load_project_baselines(project)

    baseline_entry = {
        "id": datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "created_at": datetime.utcnow().isoformat(),
        "label": label or "Auto Baseline",
        "failures": failures
    }

    baselines.insert(0, baseline_entry)
    baselines = baselines[:MAX_BASELINES_PER_PROJECT]

    with open(_project_file(project), "w") as f:
        json.dump(baselines, f, indent=2)


def delete_baseline(project, baseline_id):
    baselines = load_project_baselines(project)
    baselines = [b for b in baselines if b["id"] != baseline_id]

    with open(_project_file(project), "w") as f:
        json.dump(baselines, f, indent=2)


def get_latest_baseline(project):
    baselines = load_project_baselines(project)
    return baselines[0] if baselines else None


def compare_failures(current, baseline):
    baseline_keys = {
        f["testcase"] + f["error"] for f in baseline["failures"]
    }

    new_failures = []
    existing_failures = []

    for f in current:
        key = f["testcase"] + f["error"]
        if key in baseline_keys:
            existing_failures.append(f)
        else:
            new_failures.append(f)

    return new_failures, existing_failures
