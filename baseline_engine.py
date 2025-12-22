import os
import json
from datetime import datetime
from uuid import uuid4

PROJECT_BASELINE_ROOT = "data/baseline"
MAX_BASELINES = 10

os.makedirs(PROJECT_BASELINE_ROOT, exist_ok=True)


def _project_dir(project: str):
    path = os.path.join(PROJECT_BASELINE_ROOT, project)
    os.makedirs(path, exist_ok=True)
    return path


def list_baselines(project: str):
    path = _project_dir(project)
    baselines = []

    for f in os.listdir(path):
        if f.endswith(".json"):
            with open(os.path.join(path, f)) as fh:
                data = json.load(fh)
                baselines.append(data["meta"])

    return sorted(baselines, key=lambda x: x["created_at"], reverse=True)


def get_latest_baseline(project: str):
    baselines = list_baselines(project)
    return baselines[0] if baselines else None


def save_project_baseline(project: str, failures: list, label: str = "Latest", admin_key: str = None):
    if not admin_key:
        raise ValueError("Admin key required")

    path = _project_dir(project)

    existing = list_baselines(project)
    if len(existing) >= MAX_BASELINES:
        raise ValueError("Max baseline limit reached (10)")

    baseline_id = str(uuid4())
    payload = {
        "meta": {
            "id": baseline_id,
            "label": label,
            "created_at": datetime.utcnow().isoformat(),
            "failure_count": len(failures),
        },
        "failures": failures,
    }

    with open(os.path.join(path, f"{baseline_id}.json"), "w") as f:
        json.dump(payload, f, indent=2)

    return baseline_id


def load_project_baseline(project: str, baseline_id: str):
    path = _project_dir(project)
    with open(os.path.join(path, f"{baseline_id}.json")) as f:
        return json.load(f)


def delete_project_baseline(project: str, baseline_id: str, admin_key: str):
    if not admin_key:
        raise ValueError("Admin key required")

    path = _project_dir(project)
    os.remove(os.path.join(path, f"{baseline_id}.json"))


def get_baseline_stats(project: str):
    baselines = list_baselines(project)
    return {
        "count": len(baselines),
        "latest": baselines[0] if baselines else None,
    }
