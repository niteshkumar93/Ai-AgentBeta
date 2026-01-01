"""
GitHub Storage Module - FIXED VERSION
Supports both XML and JSON baseline files
"""

import requests
import base64
import json
from datetime import datetime
from typing import Optional, List, Dict


class GitHubStorage:
    def __init__(self, token: str, repo_owner: str, repo_name: str, branch: str = "main"):
        """
        Initialize GitHub storage
        
        Args:
            token: GitHub personal access token
            repo_owner: GitHub username
            repo_name: Repository name
            branch: Branch name (default: main)
        """
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Validate configuration
        if not token:
            raise ValueError("❌ GitHub token is required")
        if not repo_owner:
            raise ValueError("❌ GitHub repo_owner is required")
        if not repo_name:
            raise ValueError("❌ GitHub repo_name is required")
        
        print(f"✅ GitHubStorage initialized: {repo_owner}/{repo_name}")
    
    def save_baseline(
        self, 
        content: str,  # Can be XML or JSON string
        filename: str, 
        folder: str = "baselines"
    ) -> bool:
        """
        Save baseline file to GitHub (supports XML and JSON)
        
        Args:
            content: File content as string (XML or JSON)
            filename: Name of the file (e.g., 'project_baseline_20240115.json')
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create full path
            file_path = f"{folder}/{filename}" if folder else filename
            url = f"{self.base_url}/{file_path}"
            
            print(f"📤 Attempting to save: {file_path}")
            
            # Encode content to base64
            content_bytes = content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            # Check if file already exists (to get SHA for update)
            sha = self._get_file_sha(file_path)
            
            # Prepare commit message
            commit_message = f"Update baseline: {filename} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Prepare request data
            data = {
                "message": commit_message,
                "content": content_base64,
                "branch": self.branch
            }
            
            # Add SHA if file exists (for update)
            if sha:
                data["sha"] = sha
                print(f"📝 Updating existing file (SHA: {sha[:8]}...)")
            else:
                print(f"📄 Creating new file")
            
            # Make request
            response = requests.put(url, headers=self.headers, json=data)
            
            if response.status_code in [200, 201]:
                print(f"✅ Baseline saved successfully: {filename}")
                return True
            else:
                print(f"❌ Error saving baseline: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                
                # Check for common errors
                if response.status_code == 401:
                    print("❌ Authentication failed - check your GITHUB_TOKEN")
                elif response.status_code == 404:
                    print(f"❌ Repository not found: {self.repo_owner}/{self.repo_name}")
                elif response.status_code == 403:
                    print("❌ Permission denied - check token permissions")
                
                return False
                
        except Exception as e:
            print(f"❌ Exception while saving baseline: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False
    
    def load_baseline(
        self, 
        filename: str, 
        folder: str = "baselines"
    ) -> Optional[str]:
        """
        Load baseline file from GitHub (supports XML and JSON)
        
        Args:
            filename: Name of the file to load
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            File content as string, or None if not found
        """
        try:
            file_path = f"{folder}/{filename}" if folder else filename
            url = f"{self.base_url}/{file_path}"
            
            print(f"📥 Loading baseline: {file_path}")
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                content_base64 = data['content']
                content = base64.b64decode(content_base64).decode('utf-8')
                print(f"✅ Baseline loaded successfully: {filename}")
                return content
            else:
                print(f"⚠️ Baseline not found: {filename} (HTTP {response.status_code})")
                return None
                
        except Exception as e:
            print(f"❌ Exception while loading baseline: {str(e)}")
            return None
    
    def list_baselines(self, folder: str = "baselines") -> List[Dict[str, str]]:
        """
        List all baseline files in the repository (XML and JSON)
        
        Args:
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            List of dictionaries with file information
        """
        try:
            url = f"{self.base_url}/{folder}"
            
            print(f"📋 Listing baselines in: {folder}")
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                files = response.json()
                baseline_files = []
                
                for file in files:
                    # Accept both .xml and .json files
                    if file['type'] == 'file' and (
                        file['name'].endswith('.xml') or 
                        file['name'].endswith('.json')
                    ):
                        baseline_files.append({
                            'name': file['name'],
                            'size': file['size'],
                            'url': file['html_url'],
                            'download_url': file['download_url']
                        })
                
                print(f"✅ Found {len(baseline_files)} baseline(s)")
                return baseline_files
            
            elif response.status_code == 404:
                # Folder doesn't exist yet - this is OK
                print(f"ℹ️ Folder '{folder}' doesn't exist yet (will be created on first save)")
                return []
            
            else:
                print(f"⚠️ Could not list baselines: HTTP {response.status_code}")
                print(f"Response: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Exception while listing baselines: {str(e)}")
            return []
    
    def delete_baseline(
        self, 
        filename: str, 
        folder: str = "baselines"
    ) -> bool:
        """
        Delete a baseline file from GitHub
        
        Args:
            filename: Name of the file to delete
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = f"{folder}/{filename}" if folder else filename
            url = f"{self.base_url}/{file_path}"
            
            print(f"🗑️ Deleting baseline: {file_path}")
            
            # Get SHA (required for deletion)
            sha = self._get_file_sha(file_path)
            
            if not sha:
                print(f"⚠️ File not found: {filename}")
                return False
            
            # Prepare request
            data = {
                "message": f"Delete baseline: {filename}",
                "sha": sha,
                "branch": self.branch
            }
            
            response = requests.delete(url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                print(f"✅ Baseline deleted successfully: {filename}")
                return True
            else:
                print(f"❌ Error deleting baseline: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Exception while deleting baseline: {str(e)}")
            return False
    
    def _get_file_sha(self, file_path: str) -> Optional[str]:
        """
        Get SHA of existing file (needed for updates/deletes)
        
        Args:
            file_path: Full path to file in repo
        
        Returns:
            SHA string or None if file doesn't exist
        """
        try:
            url = f"{self.base_url}/{file_path}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()['sha']
            else:
                return None
                
        except Exception:
            return None
    
    def test_connection(self) -> bool:
        """
        Test if GitHub connection is working
        
        Returns:
            True if connection is OK
        """
        try:
            # Try to list root contents
            response = requests.get(self.base_url, headers=self.headers)
            
            if response.status_code == 200:
                print(f"✅ GitHub connection test passed")
                return True
            else:
                print(f"❌ GitHub connection test failed: HTTP {response.status_code}")
                return False
        
        except Exception as e:
            print(f"❌ GitHub connection test error: {e}")
            return False