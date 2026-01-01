"""
GitHub Storage Module for Streamlit App
Automatically saves and loads XML baseline files to/from GitHub
"""

import requests
import base64
import json
from datetime import datetime
from typing import Optional, List, Dict
import xml.etree.ElementTree as ET


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
    
    def save_baseline(self, xml_content: str, filename: str, folder: str = "baselines") -> bool:
        """
        Save XML baseline to GitHub automatically
        
        Args:
            xml_content: XML content as string
            filename: Name of the file (e.g., 'baseline_2024.xml')
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create full path
            file_path = f"{folder}/{filename}" if folder else filename
            url = f"{self.base_url}/{file_path}"
            
            # Encode content to base64
            content_bytes = xml_content.encode('utf-8')
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
            
            # Make request
            response = requests.put(url, headers=self.headers, json=data)
            
            if response.status_code in [200, 201]:
                print(f"✅ Baseline saved successfully: {filename}")
                return True
            else:
                print(f"❌ Error saving baseline: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Exception while saving baseline: {str(e)}")
            return False
    
    def load_baseline(self, filename: str, folder: str = "baselines") -> Optional[str]:
        """
        Load XML baseline from GitHub
        
        Args:
            filename: Name of the file to load
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            XML content as string, or None if not found
        """
        try:
            file_path = f"{folder}/{filename}" if folder else filename
            url = f"{self.base_url}/{file_path}"
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                content_base64 = data['content']
                content = base64.b64decode(content_base64).decode('utf-8')
                print(f"✅ Baseline loaded successfully: {filename}")
                return content
            else:
                print(f"⚠️ Baseline not found: {filename}")
                return None
                
        except Exception as e:
            print(f"❌ Exception while loading baseline: {str(e)}")
            return None
    
    def list_baselines(self, folder: str = "baselines") -> List[Dict[str, str]]:
        """
        List all baseline files in the repository
        
        Args:
            folder: Folder path in repo (default: 'baselines')
        
        Returns:
            List of dictionaries with file information
        """
        try:
            url = f"{self.base_url}/{folder}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                files = response.json()
                baseline_files = []
                
                for file in files:
                    if file['type'] == 'file' and file['name'].endswith('.xml'):
                        baseline_files.append({
                            'name': file['name'],
                            'size': file['size'],
                            'url': file['html_url'],
                            'download_url': file['download_url']
                        })
                
                return baseline_files
            else:
                print(f"⚠️ Could not list baselines: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Exception while listing baselines: {str(e)}")
            return []
    
    def delete_baseline(self, filename: str, folder: str = "baselines") -> bool:
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
                print(f"❌ Error deleting baseline: {response.status_code}")
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
                
        except Exception as e:
            return None


def xml_to_string(xml_element) -> str:
    """
    Convert XML element to string
    
    Args:
        xml_element: XML Element object
    
    Returns:
        XML as string
    """
    return ET.tostring(xml_element, encoding='unicode', method='xml')


def string_to_xml(xml_string: str):
    """
    Convert string to XML element
    
    Args:
        xml_string: XML as string
    
    Returns:
        XML Element object
    """
    return ET.fromstring(xml_string)