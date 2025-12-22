import os
import json
from datetime import datetime
from typing import List, Dict

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
BASELINE_DIR = "data/baseline"
MAX_BASELINES_PER_PROJECT = 10

os.makedirs(BASELINE_DIR, exist_ok=True)

# -------------------------------------------------
# INTERNAL HELPERS
# -------------------------------------------------
def _project_file(project: str) -> str:
    safe = project.replace(" ", "_")
    return os.path.join(BASELINE_DIR, f"{safe}.json")


# -------------------------------------------------
# EXISTING FUNCTIONS (DO NOT BREAK)
# -------------------------------------------------
def load_baseline(project: str = None):
    """
    Backward compatible:
    - If project provided → return latest baseline
    - Else → return empty dict
    """
    if not project:
        return {}

    file = _project_file(project)
    if not os.path.exists(file):
        return {}

    with open(file, "r") as f:
        data = json.load(f)

    baselines = data.get("baselines", [])
    return baselines[-1]["failures"] if baselines else {}


def save_baseline(project: str, failures: list, admin_key: str, label: str = ""):
    """
    Save a new baseline for a project
    """
    file = _project_file(project)

    if os.path.exists(file):
        with open(file, "r") as f:
            data = json.load(f)
    else:
        data = {"project": project, "baselines": []}

    baselines = data["baselines"]

    # Enforce max baseline limit
    if len(baselines) >= MAX_BASELINES_PER_PROJECT:
        baselines.pop(0)

    baselines.append({
        "id": f"{project}-{len(baselines)+1}",
        "created_at": datetime.utcnow().isoformat(),
        "label": label or "Auto",
        "failures": failures
    })

    with open(file, "w") as f:
        json.dump(data, f, indent=2)


# -------------------------------------------------
# NEW FUNCTIONS (STEP 2 & STEP 3 REQUIRE THESE)
# -------------------------------------------------
def list_projects() -> List[str]:
    return [
        f.replace(".json", "")
        for f in os.listdir(BASELINE_DIR)
        if f.endswith(".json")
    ]


def list_baselines(project: str) -> List[Dict]:
    file = _project_file(project)
    if not os.path.exists(file):
        return []

    with open(file, "r") as f:
        return json.load(f).get("baselines", [])


def load_baseline_by_id(project: str, baseline_id: str) -> Dict:
    baselines = list_baselines(project)
    for b in baselines:
        if b["id"] == baseline_id:
            return b
    return {}


def delete_baseline(project: str, baseline_id: str):
    file = _project_file(project)
    if not os.path.exists(file):
        return

    with open(file, "r") as f:
        data = json.load(f)

    data["baselines"] = [
        b for b in data.get("baselines", [])
        if b["id"] != baseline_id
    ]

    with open(file, "w") as f:
        json.dump(data, f, indent=2)
