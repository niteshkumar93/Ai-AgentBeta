import json
import os
from typing import List, Dict

KNOWN_PROJECTS = [
    "AutomationAPI_LightningLWC"
]

# Separate baseline directory for AutomationAPI
BASELINE_DIR = "baselines/automation_api"
os.makedirs(BASELINE_DIR, exist_ok=True)


def _get_baseline_path(project_name: str) -> str:
    """Get baseline file path for AutomationAPI project"""
    return os.path.join(BASELINE_DIR, f"{project_name}.json")


def baseline_exists(project_name: str) -> bool:
    """Check if baseline exists for this AutomationAPI project"""
    path = _get_baseline_path(project_name)
    if not os.path.exists(path):
        return False
    
    # Check if file has content
    try:
        baseline = load_baseline(project_name)
        return len(baseline) > 0
    except:
        return False


def load_baseline(project_name: str) -> List[Dict]:
    """Load baseline for AutomationAPI project"""
    path = _get_baseline_path(project_name)
    
    if not os.path.exists(path):
        return []
    
    if os.path.getsize(path) == 0:
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def save_baseline(project_name: str, failures: List[Dict], admin_key: str):
    """Save baseline for AutomationAPI project (admin only)"""
    expected = os.getenv("BASELINE_ADMIN_KEY")
    if not expected:
        raise RuntimeError("❌ BASELINE_ADMIN_KEY not configured")
    
    if admin_key != expected:
        raise PermissionError("❌ Admin key invalid")
    
    # Clean up failures before saving (remove internal flags and metadata)
    clean_failures = []
    for f in failures:
        # Skip metadata-only records
        if f.get("_no_failures"):
            continue
        
        # Create clean failure record with essential fields
        clean_failure = {
            "project": f.get("project"),
            "spec_file": f.get("spec_file"),
            "test_name": f.get("test_name"),
            "error_summary": f.get("error_summary"),
            "error_details": f.get("error_details", ""),  # Include for better matching
            "is_skipped": f.get("is_skipped", False)
        }
        clean_failures.append(clean_failure)
    
    # Save to file
    path = _get_baseline_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_failures, f, indent=2)
    
    print(f"✅ Saved {len(clean_failures)} AutomationAPI baseline failures for {project_name}")


def compare_with_baseline(project_name: str, current_failures: List[Dict]):
    """
    Compare current failures with baseline.
    Returns: (new_failures, existing_failures)
    """
    baseline = load_baseline(project_name)
    
    # If no baseline exists, all failures are new
    if not baseline:
        # Filter out metadata-only records
        real_failures = [f for f in current_failures if not f.get("_no_failures")]
        return real_failures, []
    
    # Create signature for baseline failures
    # Use spec_file + test_name + error_summary for matching
    baseline_sigs = set()
    for b in baseline:
        spec = b.get('spec_file', '')
        test = b.get('test_name', '')
        error = b.get('error_summary', '')
        sig = f"{spec}|{test}|{error}"
        baseline_sigs.add(sig)
    
    new_failures = []
    existing_failures = []
    
    for failure in current_failures:
        # Skip metadata-only records
        if failure.get("_no_failures"):
            continue
        
        # Create signature for current failure
        spec = failure.get('spec_file', '')
        test = failure.get('test_name', '')
        error = failure.get('error_summary', '')
        sig = f"{spec}|{test}|{error}"
        
        if sig in baseline_sigs:
            existing_failures.append(failure)
        else:
            new_failures.append(failure)
    
    return new_failures, existing_failures


def list_available_baselines() -> List[str]:
    """List all available AutomationAPI baselines"""
    if not os.path.exists(BASELINE_DIR):
        return []
    
    return [
        f.replace(".json", "")
        for f in os.listdir(BASELINE_DIR)
        if f.endswith(".json")
    ]


def get_baseline_info(project_name: str) -> Dict:
    """Get information about a baseline"""
    baseline = load_baseline(project_name)
    
    if not baseline:
        return {
            "exists": False,
            "count": 0,
            "specs": []
        }
    
    specs = list(set(f.get('spec_file', 'Unknown') for f in baseline))
    
    return {
        "exists": True,
        "count": len(baseline),
        "specs": specs,
        "real_failures": len([f for f in baseline if not f.get('is_skipped')]),
        "skipped_failures": len([f for f in baseline if f.get('is_skipped')])
    }