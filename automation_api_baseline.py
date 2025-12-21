# automation_api_baseline.py

import os
import json
from typing import List, Dict

BASELINE_DIR = "automation_api_baselines"


def _baseline_path(project: str) -> str:
    os.makedirs(BASELINE_DIR, exist_ok=True)
    return os.path.join(BASELINE_DIR, f"{project}_automation_api_baseline.json")


def save_automation_api_baseline(project: str, failures: List[Dict], admin_key: str):
    """
    Save AutomationAPI baseline failures for a project.
    """
    path = _baseline_path(project)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)


def load_automation_api_baseline(project: str) -> List[Dict]:
    """
    Load AutomationAPI baseline failures for a project.
    """
    path = _baseline_path(project)
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_automation_api_baseline(
    project: str,
    current_failures: List[Dict]
):
    """
    Compare current AutomationAPI failures against baseline.
    """

    baseline = load_automation_api_baseline(project)

    baseline_keys = {
        _failure_key(f) for f in baseline
    }

    new_failures = []
    existing_failures = []

    for failure in current_failures:
        if _failure_key(failure) in baseline_keys:
            existing_failures.append(failure)
        else:
            new_failures.append(failure)

    return new_failures, existing_failures


def _failure_key(failure: Dict) -> str:
    """
    Unique identifier for an AutomationAPI failure.
    This can be changed later without UI changes.
    """
    return "|".join([
        failure.get("testcase", ""),
        failure.get("apiEndpoint", ""),
        failure.get("httpMethod", ""),
    ])
