import json
import os
from typing import List, Dict
import streamlit as st

# -----------------------------------------------------------
# IMPORT GITHUB STORAGE (NEW)
# -----------------------------------------------------------
try:
    from github_storage import GitHubStorage
    GITHUB_STORAGE_AVAILABLE = True
except ImportError:
    GITHUB_STORAGE_AVAILABLE = False
    print("⚠️ GitHub storage module not available")

# -----------------------------------------------------------
# BASELINE LIST (KNOWN PROJECTS)
# -----------------------------------------------------------
KNOWN_PROJECTS = [
    "LightningLWC",
    "Flexi5",
    "Flexi1",
    "Flexi3",
    "ClassicAndMisc",
    "QuickActions",
    "FSL3",
    "FSL2",
    "FSL1",
    "FSL",
    "CPQ",
    "CPQ1",
    "CPQ2",
    "Flexi4",
    "Flexi1",
    "Flexi2",
    "Lightning1",
    "Lightning2",
    "Lightning3",
    "Lightning4",
    "VF",
    "HybridLwc",
    "NonSf1",
    "CQF_SalesLightning",
    "CQF_CPQLightning1",
    "CQF_CPQLightning2"
]

# Separate baseline directory for AutomationAPI
BASELINE_DIR = "baselines/automation_api"
os.makedirs(BASELINE_DIR, exist_ok=True)

# -----------------------------------------------------------
# GITHUB STORAGE HELPER (NEW)
# -----------------------------------------------------------
@st.cache_resource
def _get_github_storage():
    """Initialize GitHub storage from Streamlit secrets"""
    if not GITHUB_STORAGE_AVAILABLE:
        return None
    
    try:
        token = st.secrets.get("GITHUB_TOKEN2", "")
        owner = st.secrets.get("GITHUB_OWNER", "")
        repo = st.secrets.get("GITHUB_REPO", "")
        
        if not all([token, owner, repo]):
            return None
        
        return GitHubStorage(token, owner, repo, "main")
    except Exception as e:
        print(f"GitHub storage init failed: {e}")
        return None

def _get_baseline_path(project_name: str) -> str:
    """Get baseline file path for AutomationAPI project"""
    return os.path.join(BASELINE_DIR, f"{project_name}.json")


def baseline_exists(project_name: str) -> bool:
    """Check if baseline exists for this AutomationAPI project"""
    return os.path.exists(_get_baseline_path(project_name))


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
    
    # Clean up failures before saving (remove internal flags)
    clean_failures = []
    for f in failures:
        if not f.get("_no_failures"):
            clean_failure = {
                "project": f.get("project"),
                "spec_file": f.get("spec_file"),
                "test_name": f.get("test_name"),
                "error_summary": f.get("error_summary"),
                "is_skipped": f.get("is_skipped", False)
            }
            clean_failures.append(clean_failure)
    
    # Save locally (your original code)
    path = _get_baseline_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_failures, f, indent=2)
    
    # NEW: Additional GitHub storage backup
    _save_to_github_storage(project_name, clean_failures)


# -----------------------------------------------------------
# NEW: ADDITIONAL GITHUB STORAGE BACKUP
# -----------------------------------------------------------
def _save_to_github_storage(project_name: str, failures: List[Dict]):
    """
    Additional backup to GitHub using the new storage module
    This is separate from your local baseline storage
    """
    github_storage = _get_github_storage()
    
    if not github_storage:
        # Silently skip if not configured
        return
    
    try:
        from datetime import datetime
        
        # Convert to JSON string
        json_content = json.dumps(failures, indent=2)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project_name}_api_baseline_{timestamp}.json"
        
        # Save to GitHub (in a separate folder)
        success = github_storage.save_baseline(
            json_content, 
            filename, 
            folder="baselines_backup/api"
        )
        
        if success:
            st.success(f"✅ API Backup saved to GitHub: {filename}")
            print(f"✅ GitHub storage backup saved: {filename}")
        else:
            print(f"⚠️ GitHub storage backup failed for {filename}")
    
    except Exception as e:
        # Don't fail if backup fails - original save still works
        print(f"⚠️ GitHub storage backup error: {e}")


def compare_with_baseline(project_name: str, current_failures: List[Dict]):
    """
    Compare current failures with baseline.
    Returns: (new_failures, existing_failures)
    """
    baseline = load_baseline(project_name)
    
    # Create signature for baseline failures (spec + test_name + error)
    baseline_sigs = {
        f"{b.get('spec_file')}|{b.get('test_name')}|{b.get('error_summary', '')}"
        for b in baseline
    }
    
    new_failures = []
    existing_failures = []
    
    for failure in current_failures:
        # Skip metadata-only records
        if failure.get("_no_failures"):
            continue
        
        sig = f"{failure.get('spec_file')}|{failure.get('test_name')}|{failure.get('error_summary', '')}"
        
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


# -----------------------------------------------------------
# NEW: LIST GITHUB STORAGE BACKUPS
# -----------------------------------------------------------
def list_github_baselines(project_name: str = None) -> List[Dict]:
    """
    List all API baseline backups from GitHub storage
    """
    github_storage = _get_github_storage()
    
    if not github_storage:
        return []
    
    try:
        all_baselines = github_storage.list_baselines(folder="baselines_backup/api")
        
        if project_name:
            # Filter by project name
            return [b for b in all_baselines if b['name'].startswith(project_name)]
        
        return all_baselines
    
    except Exception as e:
        print(f"Error listing GitHub baselines: {e}")
        return []


# -----------------------------------------------------------
# NEW: LOAD GITHUB STORAGE BACKUP
# -----------------------------------------------------------
def load_github_baseline(filename: str) -> List[Dict]:
    """
    Load a specific API baseline backup from GitHub storage
    """
    github_storage = _get_github_storage()
    
    if not github_storage:
        return []
    
    try:
        content = github_storage.load_baseline(filename, folder="baselines_backup/api")
        
        if content:
            return json.loads(content)
        
        return []
    
    except Exception as e:
        print(f"Error loading GitHub baseline: {e}")
        return []