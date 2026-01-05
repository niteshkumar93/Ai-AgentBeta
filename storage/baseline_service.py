"""
Baseline Service - Unified baseline management with GitHub storage
This service ensures ALL baselines are saved to GitHub automatically
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class BaselineService:
    """
    Unified baseline service that ALWAYS saves to GitHub
    Supports both Provar and AutomationAPI baselines
    """
    
    def __init__(self, github_storage):
        """
        Initialize with GitHub storage
        
        Args:
            github_storage: GitHubStorage instance
        """
        self.github = github_storage
        self.local_cache_dir = "data/baseline_cache"
        os.makedirs(self.local_cache_dir, exist_ok=True)
    
    def save(
        self, 
        project: str, 
        platform: str,  # "provar" or "automation_api"
        failures: List[Dict],
        label: Optional[str] = None
    ) -> str:
        """
        Save baseline to GitHub (PRIMARY) and local cache (BACKUP)
        
        Returns:
            baseline_id: Unique identifier for this baseline
        """
        # Generate timestamp-based ID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        baseline_id = f"baseline_{timestamp}"
        
        # Create baseline payload
        payload = {
            "id": baseline_id,
            "project": project,
            "platform": platform,
            "label": label or "Auto",
            "created_at": timestamp,
            "failure_count": len(failures),
            "failures": failures
        }
        
        # Convert to JSON
        json_content = json.dumps(payload, indent=2)
        
        # Determine folder based on platform
        folder = f"baselines/{platform}"
        
        # Create filename
        filename = f"{project}_{platform}_{baseline_id}.json"
        
        # 1️⃣ SAVE TO GITHUB (PRIMARY)
        try:
            success = self.github.save_baseline(
                json_content,
                filename,
                folder=folder
            )
            
            if not success:
                raise Exception("GitHub save returned False")
            
            print(f"✅ Saved to GitHub: {folder}/{filename}")
        
        except Exception as e:
            print(f"❌ GitHub save failed: {e}")
            raise Exception(f"Failed to save baseline to GitHub: {str(e)}")
        
        # 2️⃣ SAVE TO LOCAL CACHE (BACKUP)
        try:
            cache_dir = os.path.join(self.local_cache_dir, platform, project)
            os.makedirs(cache_dir, exist_ok=True)
            
            cache_file = os.path.join(cache_dir, f"{baseline_id}.json")
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(json_content)
            
            print(f"✅ Saved to local cache: {cache_file}")
        
        except Exception as e:
            # Local cache failure is not critical
            print(f"⚠️ Local cache save failed: {e}")
        
        return baseline_id
    
    def load(
        self,
        filename: str,
        platform: str
    ) -> Optional[Dict]:
        """
        Load baseline from GitHub
        
        Args:
            filename: Name of the baseline file
            platform: "provar" or "automation_api"
        
        Returns:
            Baseline data or None
        """
        folder = f"baselines/{platform}"
        
        try:
            content = self.github.load_baseline(filename, folder=folder)
            
            if content:
                return json.loads(content)
            
            return None
        
        except Exception as e:
            print(f"❌ Failed to load baseline: {e}")
            return None
    
    def list(
        self,
        platform: Optional[str] = None,
        project: Optional[str] = None
    ) -> List[Dict]:
        """
        List all baselines from GitHub
        
        Args:
            platform: Filter by platform ("provar" or "automation_api")
            project: Filter by project name
        
        Returns:
            List of baseline metadata
        """
        try:
            if platform:
                folder = f"baselines/{platform}"
                all_files = self.github.list_baselines(folder=folder)
            else:
                # Get both platforms
                provar_files = self.github.list_baselines(folder="baselines/provar")
                api_files = self.github.list_baselines(folder="baselines/automation_api")
                all_files = provar_files + api_files
            
            # Filter by project if specified
            if project:
                all_files = [
                    f for f in all_files 
                    if f['name'].startswith(project)
                ]
            
            return all_files
        
        except Exception as e:
            print(f"❌ Failed to list baselines: {e}")
            return []
    
    def delete(
        self,
        filename: str,
        platform: str
    ) -> bool:
        """
        Delete baseline from GitHub
        
        Args:
            filename: Name of the baseline file
            platform: "provar" or "automation_api"
        
        Returns:
            True if successful
        """
        folder = f"baselines/{platform}"
        
        try:
            success = self.github.delete_baseline(filename, folder=folder)
            
            if success:
                print(f"✅ Deleted from GitHub: {folder}/{filename}")
            
            return success
        
        except Exception as e:
            print(f"❌ Failed to delete baseline: {e}")
            return False
    
    def sync_from_github(self) -> int:
        """
        Sync all baselines from GitHub to local cache
        Useful for app startup
        
        Returns:
            Number of baselines synced
        """
        synced = 0
        
        for platform in ["provar", "automation_api"]:
            try:
                folder = f"baselines/{platform}"
                files = self.github.list_baselines(folder=folder)
                
                for file_info in files:
                    filename = file_info['name']
                    
                    # Load from GitHub
                    content = self.github.load_baseline(filename, folder=folder)
                    
                    if content:
                        # Save to local cache
                        try:
                            data = json.loads(content)
                            project = data.get('project', 'unknown')
                            baseline_id = data.get('id', 'unknown')
                            
                            cache_dir = os.path.join(
                                self.local_cache_dir, 
                                platform, 
                                project
                            )
                            os.makedirs(cache_dir, exist_ok=True)
                            
                            cache_file = os.path.join(cache_dir, f"{baseline_id}.json")
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            synced += 1
                        
                        except Exception as e:
                            print(f"⚠️ Failed to cache {filename}: {e}")
            
            except Exception as e:
                print(f"⚠️ Failed to sync {platform} baselines: {e}")
        
        return synced
    
    def get_stats(self, project: str, platform: str) -> Dict:
        """
        Get statistics about baselines for a project
        
        Args:
            project: Project name
            platform: "provar" or "automation_api"
        
        Returns:
            Statistics dictionary
        """
        baselines = self.list(platform=platform, project=project)
        
        if not baselines:
            return {
                "count": 0,
                "latest": None,
                "oldest": None,
                "total_failures": 0
            }
        
        # Sort by name (which contains timestamp)
        baselines_sorted = sorted(baselines, key=lambda x: x['name'], reverse=True)
        
        # Load and analyze
        total_failures = 0
        for baseline_info in baselines_sorted:
            baseline_data = self.load(baseline_info['name'], platform)
            if baseline_data:
                total_failures += baseline_data.get('failure_count', 0)
        
        return {
            "count": len(baselines),
            "latest": baselines_sorted[0]['name'] if baselines_sorted else None,
            "oldest": baselines_sorted[-1]['name'] if baselines_sorted else None,
            "total_failures": total_failures
        }