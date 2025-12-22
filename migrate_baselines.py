#!/usr/bin/env python3
"""
Migration Script: Convert Old Single-Baseline Format to New Multi-Baseline Format

This script helps migrate existing baselines from the old format
(baselines/ProjectName.json) to the new multi-baseline format
(data/baseline/ProjectName/baseline_TIMESTAMP.json)

Usage:
    python migrate_baselines.py [--dry-run]

Options:
    --dry-run    Show what would be migrated without making changes
"""

import os
import json
import sys
import shutil
from datetime import datetime
from typing import List, Dict

# Directories
OLD_BASELINE_DIR = "baselines"
NEW_BASELINE_DIR = "data/baseline"

def load_old_baseline(project_name: str) -> List[Dict]:
    """Load baseline from old format"""
    path = os.path.join(OLD_BASELINE_DIR, f"{project_name}.json")
    
    if not os.path.exists(path):
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else None
    except Exception as e:
        print(f"  ❌ Error loading {project_name}: {e}")
        return None


def save_new_baseline(project_name: str, failures: List[Dict], label: str = "Migrated"):
    """Save baseline in new multi-baseline format"""
    # Create project directory
    project_dir = os.path.join(NEW_BASELINE_DIR, project_name)
    os.makedirs(project_dir, exist_ok=True)
    
    # Generate timestamp
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    baseline_id = f"baseline_{ts}"
    
    # Create baseline payload
    payload = {
        "id": baseline_id,
        "project": project_name,
        "label": label,
        "created_at": ts,
        "failure_count": len(failures),
        "failures": failures,
    }
    
    # Save to file
    file_path = os.path.join(project_dir, f"{baseline_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    
    return baseline_id


def get_old_baselines() -> List[str]:
    """Get list of all old baseline files"""
    if not os.path.exists(OLD_BASELINE_DIR):
        return []
    
    return [
        f.replace(".json", "")
        for f in os.listdir(OLD_BASELINE_DIR)
        if f.endswith(".json")
    ]


def migrate_baselines(dry_run: bool = False):
    """
    Migrate all old baselines to new format
    
    Args:
        dry_run: If True, only show what would be done without making changes
    """
    print("=" * 60)
    print("BASELINE MIGRATION UTILITY")
    print("=" * 60)
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()
    
    # Get all old baselines
    old_projects = get_old_baselines()
    
    if not old_projects:
        print("ℹ️  No old baselines found in 'baselines/' directory")
        print("   Nothing to migrate!")
        return
    
    print(f"📊 Found {len(old_projects)} old baseline(s)")
    print()
    
    # Statistics
    migrated = 0
    failed = 0
    skipped = 0
    
    # Process each project
    for project in old_projects:
        print(f"Processing: {project}")
        
        # Check if already migrated
        new_project_dir = os.path.join(NEW_BASELINE_DIR, project)
        if os.path.exists(new_project_dir) and os.listdir(new_project_dir):
            print(f"  ⚠️  Skipped (already has new baselines)")
            skipped += 1
            print()
            continue
        
        # Load old baseline
        failures = load_old_baseline(project)
        
        if failures is None:
            print(f"  ❌ Failed to load old baseline")
            failed += 1
            print()
            continue
        
        if len(failures) == 0:
            print(f"  ⚠️  Empty baseline (no failures)")
            skipped += 1
            print()
            continue
        
        print(f"  📝 {len(failures)} failure(s) found")
        
        if not dry_run:
            try:
                baseline_id = save_new_baseline(
                    project,
                    failures,
                    "Migrated from old system"
                )
                print(f"  ✅ Migrated successfully → {baseline_id}")
                migrated += 1
            except Exception as e:
                print(f"  ❌ Migration failed: {e}")
                failed += 1
        else:
            print(f"  🔍 Would migrate {len(failures)} failure(s)")
            migrated += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully migrated: {migrated}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {len(old_projects)}")
    print()
    
    if dry_run:
        print("🔍 This was a DRY RUN - no changes were made")
        print("   Run without --dry-run to perform actual migration")
    else:
        print("✅ Migration complete!")
        print()
        print("📌 IMPORTANT: Old baseline files have NOT been deleted")
        print("   They remain in 'baselines/' directory for safety")
        print("   You can manually delete them after verifying migration")
    
    print()


def verify_migration():
    """Verify migration by comparing old and new baselines"""
    print("=" * 60)
    print("MIGRATION VERIFICATION")
    print("=" * 60)
    print()
    
    old_projects = get_old_baselines()
    
    if not old_projects:
        print("ℹ️  No old baselines to verify")
        return
    
    print(f"Checking {len(old_projects)} project(s)...")
    print()
    
    all_good = True
    
    for project in old_projects:
        # Load old baseline
        old_failures = load_old_baseline(project)
        if old_failures is None:
            continue
        
        # Check new baseline exists
        new_project_dir = os.path.join(NEW_BASELINE_DIR, project)
        if not os.path.exists(new_project_dir):
            print(f"❌ {project}: No new baseline found")
            all_good = False
            continue
        
        # Load new baselines
        new_files = [f for f in os.listdir(new_project_dir) if f.endswith(".json")]
        if not new_files:
            print(f"❌ {project}: New directory exists but no baselines")
            all_good = False
            continue
        
        # Load first new baseline
        with open(os.path.join(new_project_dir, new_files[0]), "r") as f:
            new_baseline = json.load(f)
        
        new_failures = new_baseline.get("failures", [])
        
        # Compare counts
        if len(old_failures) != len(new_failures):
            print(f"⚠️  {project}: Failure count mismatch (old={len(old_failures)}, new={len(new_failures)})")
            all_good = False
        else:
            print(f"✅ {project}: Verified ({len(old_failures)} failures)")
    
    print()
    if all_good:
        print("✅ All verifications passed!")
    else:
        print("⚠️  Some issues found - please review above")
    print()


def show_usage():
    """Show usage information"""
    print(__doc__)


if __name__ == "__main__":
    # Parse arguments
    dry_run = "--dry-run" in sys.argv
    verify = "--verify" in sys.argv
    help_flag = "--help" in sys.argv or "-h" in sys.argv
    
    if help_flag:
        show_usage()
    elif verify:
        verify_migration()
    else:
        migrate_baselines(dry_run)
