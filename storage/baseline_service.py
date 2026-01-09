"""
Enhanced Baseline Service - Fast Session State Cache + GitHub Backup
This version uses st.session_state for in-memory caching (survives reruns)
Falls back to GitHub only when cache misses occur
"""

import json
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional


class BaselineService:
    """
    Hybrid baseline service with intelligent caching:
    - Primary: st.session_state (instant, survives reruns)
    - Backup: GitHub (persistent, slower)
    
    Data flow:
    1. Save → both session_state + GitHub
    2. Load → session_state first, GitHub fallback
    3. List → session_state (synced from GitHub)
    """
    
    def __init__(self, github_storage):
        """
        Initialize with GitHub storage
        
        Args:
            github_storage: GitHubStorage instance
        """
        self.github = github_storage
        self._init_cache()
    
    def _init_cache(self):
        """Initialize in-memory cache in session_state"""
        if 'baseline_cache' not in st.session_state:
            st.session_state.baseline_cache = {
                'provar': {},           # {filename: baseline_data}
                'automation_api': {},   # {filename: baseline_data}
                'metadata': {
                    'last_sync': None,
                    'is_synced': False,
                    'sync_count': 0
                }
            }
            print("🆕 Initialized baseline cache in session_state")
    
    def _get_cache(self, platform: str) -> Dict:
        """Get cache for specific platform"""
        return st.session_state.baseline_cache.get(platform, {})
    
    def _set_cache(self, platform: str, filename: str, data: Dict):
        """Store data in cache"""
        st.session_state.baseline_cache[platform][filename] = data
        print(f"💾 Cached: {filename}")
    
    def _update_metadata(self, **kwargs):
        """Update cache metadata"""
        st.session_state.baseline_cache['metadata'].update(kwargs)
    
    # ====================================================================
    # SAVE - Dual Storage (Session State + GitHub)
    # ====================================================================
    
    def save(
        self, 
        project: str, 
        platform: str,  # "provar" or "automation_api"
        failures: List[Dict],
        label: Optional[str] = None
    ) -> str:
        """
        Save baseline to BOTH session_state AND GitHub
        
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
        
        # 1️⃣ SAVE TO SESSION STATE (INSTANT)
        try:
            self._set_cache(platform, filename, payload)
            print(f"✅ Saved to cache: {filename}")
        except Exception as e:
            print(f"⚠️ Cache save failed: {e}")
        
        # 2️⃣ SAVE TO GITHUB (PERSISTENT BACKUP)
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
        
        return baseline_id
    
    # ====================================================================
    # LOAD - Cache First, GitHub Fallback
    # ====================================================================
    
    def load(
        self,
        filename: str,
        platform: str
    ) -> Optional[Dict]:
        """
        Load baseline from CACHE first, GitHub if cache miss
        
        Args:
            filename: Name of the baseline file
            platform: "provar" or "automation_api"
        
        Returns:
            Baseline data or None
        """
        # 1️⃣ TRY CACHE FIRST (INSTANT!)
        cache = self._get_cache(platform)
        if filename in cache:
            print(f"⚡ Cache hit: {filename}")
            return cache[filename]
        
        # 2️⃣ FALLBACK TO GITHUB (slower)
        print(f"🌐 Cache miss, loading from GitHub: {filename}")
        folder = f"baselines/{platform}"
        
        try:
            content = self.github.load_baseline(filename, folder=folder)
            
            if content:
                data = json.loads(content)
                # Cache it for next time
                self._set_cache(platform, filename, data)
                return data
            
            return None
        
        except Exception as e:
            print(f"❌ Failed to load baseline: {e}")
            return None
    
    # ====================================================================
    # LIST - From Cache (Fast!)
    # ====================================================================
    
    def list(
        self,
        platform: Optional[str] = None,
        project: Optional[str] = None
    ) -> List[Dict]:
        """
        List all baselines from CACHE (instant!)
        
        Args:
            platform: Filter by platform ("provar" or "automation_api")
            project: Filter by project name
        
        Returns:
            List of baseline metadata
        """
        results = []
        
        # Determine which platforms to check
        platforms = [platform] if platform else ['provar', 'automation_api']
        
        for plat in platforms:
            cache = self._get_cache(plat)
            
            for filename, data in cache.items():
                # Filter by project if specified
                if project and data.get('project') != project:
                    continue
                
                results.append({
                    'name': filename,
                    'project': data.get('project'),
                    'created_at': data.get('created_at'),
                    'failure_count': data.get('failure_count', 0),
                    'label': data.get('label', 'Auto'),
                    'platform': plat
                })
        
        # Sort by created_at (newest first)
        results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        print(f"📋 Listed {len(results)} baselines from cache")
        return results
    
    # ====================================================================
    # DELETE - Both Cache and GitHub
    # ====================================================================
    
    def delete(
        self,
        filename: str,
        platform: str
    ) -> bool:
        """
        Delete baseline from BOTH cache AND GitHub
        
        Args:
            filename: Name of the baseline file
            platform: "provar" or "automation_api"
        
        Returns:
            True if successful
        """
        # 1️⃣ DELETE FROM CACHE
        cache = self._get_cache(platform)
        if filename in cache:
            del cache[filename]
            print(f"✅ Deleted from cache: {filename}")
        
        # 2️⃣ DELETE FROM GITHUB
        folder = f"baselines/{platform}"
        
        try:
            success = self.github.delete_baseline(filename, folder=folder)
            
            if success:
                print(f"✅ Deleted from GitHub: {folder}/{filename}")
            
            return success
        
        except Exception as e:
            print(f"❌ Failed to delete baseline: {e}")
            return False
    
    # ====================================================================
    # SYNC - GitHub → Cache (Manual Restore)
    # ====================================================================
    
    def sync_from_github(self, platform: Optional[str] = None) -> int:
        """
        Sync baselines from GitHub to session_state cache
        This is the "Restore from GitHub" button functionality
        
        Args:
            platform: Sync specific platform, or None for all
        
        Returns:
            Number of baselines synced
        """
        synced = 0
        
        # Determine which platforms to sync
        platforms = [platform] if platform else ["provar", "automation_api"]
        
        for plat in platforms:
            try:
                folder = f"baselines/{plat}"
                
                # Get list of files from GitHub
                files = self.github.list_baselines(folder=folder)
                
                print(f"🔄 Syncing {len(files)} files from GitHub/{plat}")
                
                for file_info in files:
                    filename = file_info['name']
                    
                    try:
                        # Load from GitHub
                        content = self.github.load_baseline(filename, folder=folder)
                        
                        if content:
                            data = json.loads(content)
                            
                            # Store in cache
                            self._set_cache(plat, filename, data)
                            synced += 1
                    
                    except Exception as e:
                        print(f"⚠️ Failed to sync {filename}: {e}")
                        continue
            
            except Exception as e:
                print(f"⚠️ Failed to sync {plat} baselines: {e}")
        
        # Update metadata
        self._update_metadata(
            last_sync=datetime.now().isoformat(),
            is_synced=True,
            sync_count=st.session_state.baseline_cache['metadata'].get('sync_count', 0) + 1
        )
        
        print(f"✅ Sync complete: {synced} baselines loaded into cache")
        return synced
    
    # ====================================================================
    # AUTO-SYNC - Intelligent First Load
    # ====================================================================
    
    def ensure_synced(self) -> bool:
        """
        Auto-sync from GitHub if cache is empty (first load only)
        
        Returns:
            True if sync was performed
        """
        metadata = st.session_state.baseline_cache['metadata']
        
        # Check if already synced
        if metadata.get('is_synced', False):
            print("✓ Cache already synced, skipping auto-sync")
            return False
        
        # Check if cache is empty
        provar_count = len(self._get_cache('provar'))
        api_count = len(self._get_cache('automation_api'))
        
        if provar_count == 0 and api_count == 0:
            print("🚀 First load detected, auto-syncing from GitHub...")
            synced = self.sync_from_github()
            return synced > 0
        
        return False
    
    # ====================================================================
    # STATS & UTILITIES
    # ====================================================================
    
    def get_sync_status(self) -> Dict:
        """Get cache status and statistics"""
        metadata = st.session_state.baseline_cache['metadata']
        
        return {
            'is_synced': metadata.get('is_synced', False),
            'last_sync': metadata.get('last_sync'),
            'sync_count': metadata.get('sync_count', 0),
            'cache_count': {
                'provar': len(self._get_cache('provar')),
                'automation_api': len(self._get_cache('automation_api'))
            },
            'total_cached': len(self._get_cache('provar')) + len(self._get_cache('automation_api'))
        }
    
    def clear_cache(self, platform: Optional[str] = None):
        """
        Clear cache (useful for testing or forcing re-sync)
        
        Args:
            platform: Clear specific platform, or None for all
        """
        if platform:
            st.session_state.baseline_cache[platform] = {}
            print(f"🗑️ Cleared {platform} cache")
        else:
            st.session_state.baseline_cache = {
                'provar': {},
                'automation_api': {},
                'metadata': {
                    'last_sync': None,
                    'is_synced': False,
                    'sync_count': 0
                }
            }
            print("🗑️ Cleared all caches")
    
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
        
        # Calculate total failures
        total_failures = sum(b.get('failure_count', 0) for b in baselines)
        
        return {
            "count": len(baselines),
            "latest": baselines[0]['name'] if baselines else None,
            "oldest": baselines[-1]['name'] if baselines else None,
            "total_failures": total_failures
        }
    
    def get_github_count(self, platform: str) -> int:
        """
        Get count of baselines in GitHub (for comparison)
        
        Args:
            platform: "provar" or "automation_api"
        
        Returns:
            Number of files in GitHub
        """
        try:
            folder = f"baselines/{platform}"
            files = self.github.list_baselines(folder=folder)
            return len(files)
        except:
            return 0