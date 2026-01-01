# baseline_manager.py

import json
import os
import base64
import requests
from typing import List, Dict
import streamlit as st

# -----------------------------------------------------------
# IMPORT GITHUB STORAGE
# -----------------------------------------------------------
try:
    from github_storage import GitHubStorage
    GITHUB_STORAGE_AVAILABLE = True
except ImportError:
    GITHUB_STORAGE_AVAILABLE = False
    print("⚠️ GitHub storage module not available")

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
BASELINE_DIR = "baselines"
GITHUB_REPO = "niteshkumar93/streamlit-baselines"  # Updated to match your repo

# -----------------------------------------------------------
# BASELINE LIST (KNOWN PROJECTS)
# -----------------------------------------------------------
KNOWN_PROJECTS = [
    "VF_Lightning_Windows",
    "Regmain-Flexi",
    "Date_Time",
    "CPQ_Classic",
    "CPQ_Lightning",
    "QAM_Lightning",
    "QAM_Classic",
    "Internationalization_pipeline",
    "Lightning_Console_LogonAs",
    "DynamicForm",
    "Classic_Console_LogonAS",
    "LWC_Pipeline",
    "Regmain_LS_Windows",
    "Regmain_LC_Windows",
    "Regmain-VF",
    "FSL",
    "HYBRID_AUTOMATION_Pipeline",
    "Prerelease-Lightning",
    "Smoke_LC_Windows",
    "Smoke_CC_Windows",
    "Smoke_LS_Windows",
    "Smoke_CS_Windows",
    "DateTime",
    "Prerelease-Classic",
    "AutomationAPI_LightningLWC"
]

# -----------------------------------------------------------
# GITHUB STORAGE HELPER - FIXED VERSION
# -----------------------------------------------------------
@st.cache_resource
def _get_github_storage():
    """Initialize GitHub storage from Streamlit secrets"""
    if not GITHUB_STORAGE_AVAILABLE:
        print("⚠️ GitHub storage module not available")
        return None
    
    try:
        # Get secrets from Streamlit
        token = st.secrets.get("GITHUB_TOKEN", "")
        owner = st.secrets.get("GITHUB_OWNER", "")
        repo = st.secrets.get("GITHUB_REPO", "")
        
        # Validate all required fields
        if not token:
            print("❌ GITHUB_TOKEN not found in secrets")
            return None
        
        if not owner:
            print("❌ GITHUB_OWNER not found in secrets")
            return None
            
        if not repo:
            print("❌ GITHUB_REPO not found in secrets")
            return None
        
        print(f"✅ GitHub storage initialized: {owner}/{repo}")
        return GitHubStorage(token, owner, repo, "main")
    
    except Exception as e:
        print(f"❌ GitHub storage init failed: {e}")
        return None


def _validate_github_config():
    """Validate GitHub configuration and show helpful error messages"""
    storage = _get_github_storage()
    
    if not storage:
        st.sidebar.error("❌ GitHub Storage Not Configured")
        with st.sidebar.expander("🔧 How to Fix"):
            st.markdown("""
            **Add these to Streamlit Secrets:**
            
            1. Go to: ⚙️ Settings → Secrets
            2. Add:
            ```toml
            GITHUB_TOKEN = "ghp_your_token_here"
            GITHUB_OWNER = "niteshkumar93"
            GITHUB_REPO = "streamlit-baselines"
            ```
            
            **Create GitHub Token:**
            1. GitHub → Settings → Developer settings
            2. Personal access tokens → Tokens (classic)
            3. Generate new token
            4. Select: `repo` (all permissions)
            """)
        return False
    
    st.sidebar.success("✅ GitHub Backup Active")
    return True


# -----------------------------------------------------------
# HELPERS
# -----------------------------------------------------------
def _get_baseline_path(project_name: str) -> str:
    os.makedirs(BASELINE_DIR, exist_ok=True)
    return os.path.join(BASELINE_DIR, f"{project_name}.json")


def list_available_baselines() -> List[str]:
    if not os.path.exists(BASELINE_DIR):
        return []
    return [
        f.replace(".json", "")
        for f in os.listdir(BASELINE_DIR)
        if f.endswith(".json")
    ]


def baseline_exists(project_name: str) -> bool:
    """A baseline EXISTS if the file exists, even if it contains an empty list []"""
    return os.path.exists(_get_baseline_path(project_name))


# -----------------------------------------------------------
# LOAD BASELINE (SAFE)
# -----------------------------------------------------------
def load_baseline(project_name: str) -> List[Dict]:
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


# -----------------------------------------------------------
# SAVE BASELINE - FIXED VERSION WITH GITHUB BACKUP
# -----------------------------------------------------------
def save_baseline(project_name: str, failures: List[Dict], admin_key: str):
    """Save baseline locally AND to GitHub"""
    expected = os.getenv("BASELINE_ADMIN_KEY")
    if not expected:
        raise RuntimeError("❌ BASELINE_ADMIN_KEY not configured")

    if admin_key != expected:
        raise PermissionError("❌ Admin key invalid")

    # 1️⃣ Save locally (original behavior)
    path = _get_baseline_path(project_name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(failures or [], f, indent=2)

    # 2️⃣ Commit to GitHub (original method - using GitHub API directly)
    _commit_to_github(project_name, failures or [])
    
    # 3️⃣ FIXED: GitHub Storage backup (using github_storage.py)
    try:
        _save_to_github_storage(project_name, failures or [])
    except Exception as e:
        # Don't fail the entire save if backup fails
        st.warning(f"⚠️ GitHub backup failed (local save succeeded): {str(e)}")
        print(f"⚠️ GitHub storage backup error: {e}")


# -----------------------------------------------------------
# GITHUB COMMIT (ORIGINAL METHOD - UNCHANGED)
# -----------------------------------------------------------
def _commit_to_github(project_name: str, failures: List[Dict]):
    """Original GitHub commit method - commits to baselines/ folder"""
    token = os.getenv("GITHUB_TOKEN") or st.secrets.get("GITHUB_TOKEN", "")
    
    if not token:
        print("⚠️ No GitHub token found for direct commit")
        return

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # Get existing file SHA if it exists
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")

    # Encode content
    content = base64.b64encode(
        json.dumps(failures or [], indent=2).encode("utf-8")
    ).decode("utf-8")

    # Prepare payload
    payload = {
        "message": f"Update baseline for {project_name}",
        "content": content,
    }
    if sha:
        payload["sha"] = sha

    # Commit to GitHub
    response = requests.put(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        print(f"✅ Baseline committed to GitHub: {project_name}")
    else:
        print(f"⚠️ GitHub commit failed: {response.status_code}")


# -----------------------------------------------------------
# GITHUB STORAGE BACKUP - FIXED VERSION
# -----------------------------------------------------------
def _save_to_github_storage(project_name: str, failures: List[Dict]):
    """
    Additional backup to GitHub using github_storage.py module
    This saves timestamped versions in baselines_backup/provar folder
    """
    github_storage = _get_github_storage()
    
    if not github_storage:
        print("⚠️ GitHub storage not configured, skipping backup")
        return
    
    try:
        from datetime import datetime
        
        # Convert to JSON string
        json_content = json.dumps(failures or [], indent=2)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{project_name}_baseline_{timestamp}.json"
        
        # Save to GitHub in separate backup folder
        success = github_storage.save_baseline(
            json_content, 
            filename, 
            folder="baselines_backup/provar"
        )
        
        if success:
            st.success(f"✅ GitHub backup saved: {filename}")
            print(f"✅ GitHub storage backup saved: {filename}")
        else:
            st.warning(f"⚠️ GitHub backup failed for {filename}")
            print(f"⚠️ GitHub storage backup failed for {filename}")
    
    except Exception as e:
        # Don't fail if backup fails - original save still works
        st.warning(f"⚠️ GitHub backup error: {str(e)}")
        print(f"⚠️ GitHub storage backup error: {e}")


# -----------------------------------------------------------
# COMPARE
# -----------------------------------------------------------
def compare_with_baseline(project_name: str, current_failures: List[Dict]):
    baseline = load_baseline(project_name)

    baseline_keys = {
        f"{b.get('testcase')}|{b.get('error')}"
        for b in baseline
    }

    new_failures, existing_failures = [], []

    for f in current_failures:
        key = f"{f.get('testcase')}|{f.get('error')}"
        if key in baseline_keys:
            existing_failures.append(f)
        else:
            new_failures.append(f)

    return new_failures, existing_failures


# -----------------------------------------------------------
# GITHUB BASELINE HISTORY
# -----------------------------------------------------------
def get_baseline_history(project_name: str):
    """Get commit history for a baseline from GitHub"""
    token = os.getenv("GITHUB_TOKEN") or st.secrets.get("GITHUB_TOKEN", "")
    
    if not token:
        return []

    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
    params = {"path": f"{BASELINE_DIR}/{project_name}.json"}
    headers = {"Authorization": f"token {token}"}

    r = requests.get(url, headers=headers, params=params)
    return r.json() if r.status_code == 200 else []


# -----------------------------------------------------------
# ROLLBACK BASELINE
# -----------------------------------------------------------
def rollback_baseline(project_name: str, commit_sha: str, admin_key: str):
    """Rollback baseline to a previous commit"""
    ADMIN_KEY = os.getenv("BASELINE_ADMIN_KEY")

    if not ADMIN_KEY:
        raise RuntimeError("❌ BASELINE_ADMIN_KEY not configured")

    if admin_key != ADMIN_KEY:
        raise PermissionError("❌ Invalid admin key")

    token = os.getenv("GITHUB_TOKEN") or st.secrets.get("GITHUB_TOKEN", "")
    
    if not token:
        raise RuntimeError("❌ GITHUB_TOKEN not found")

    file_path = f"{BASELINE_DIR}/{project_name}.json"
    repo_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Get commit data
    commit_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/commits/{commit_sha}"
    commit_resp = requests.get(commit_url, headers=headers)

    if commit_resp.status_code != 200:
        raise RuntimeError("❌ Unable to fetch commit data")

    tree_sha = commit_resp.json()["tree"]["sha"]

    # Get tree
    tree_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{tree_sha}?recursive=1"
    tree_resp = requests.get(tree_url, headers=headers)

    # Find target file
    target_blob = None
    for item in tree_resp.json()["tree"]:
        if item["path"] == file_path:
            target_blob = item["sha"]
            break

    if not target_blob:
        raise RuntimeError("❌ Baseline file not found in selected commit")

    # Get file content
    blob_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/blobs/{target_blob}"
    blob_resp = requests.get(blob_url, headers=headers)

    content = base64.b64decode(blob_resp.json()["content"]).decode("utf-8")

    # Save locally
    local_path = _get_baseline_path(project_name)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Update on GitHub
    encoded = base64.b64encode(content.encode()).decode()
    current = requests.get(repo_url, headers=headers).json()
    sha = current.get("sha")

    payload = {
        "message": f"Rollback baseline for {project_name}",
        "content": encoded,
        "sha": sha
    }

    requests.put(repo_url, headers=headers, json=payload)


# -----------------------------------------------------------
# LIST GITHUB STORAGE BACKUPS
# -----------------------------------------------------------
def list_github_baselines(project_name: str = None) -> List[Dict]:
    """List all baseline backups from GitHub storage"""
    github_storage = _get_github_storage()
    
    if not github_storage:
        return []
    
    try:
        all_baselines = github_storage.list_baselines(folder="baselines_backup/provar")
        
        if project_name:
            # Filter by project name
            return [b for b in all_baselines if b['name'].startswith(project_name)]
        
        return all_baselines
    
    except Exception as e:
        print(f"Error listing GitHub baselines: {e}")
        return []


# -----------------------------------------------------------
# LOAD GITHUB STORAGE BACKUP
# -----------------------------------------------------------
def load_github_baseline(filename: str) -> List[Dict]:
    """Load a specific baseline backup from GitHub storage"""
    github_storage = _get_github_storage()
    
    if not github_storage:
        return []
    
    try:
        content = github_storage.load_baseline(filename, folder="baselines_backup/provar")
        
        if content:
            return json.loads(content)
        
        return []
    
    except Exception as e:
        print(f"Error loading GitHub baseline: {e}")
        return []