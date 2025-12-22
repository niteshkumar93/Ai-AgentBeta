#!/usr/bin/env python3
"""
Test Script for Multi-Baseline Functionality

This script tests all the new multi-baseline features to ensure they work correctly.

Usage:
    python test_multi_baseline.py
"""

import os
import sys
import json
import shutil
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the baseline engine
try:
    from baseline_engine import (
        save_baseline,
        load_baseline,
        list_baselines,
        get_latest_baseline,
        delete_baseline,
        get_baseline_stats,
        compare_with_baseline,
        baseline_exists,
        get_all_projects
    )
    print("✅ Successfully imported baseline_engine")
except ImportError as e:
    print(f"❌ Failed to import baseline_engine: {e}")
    sys.exit(1)

# Test configuration
TEST_PROJECT = "TEST_PROJECT_SAMPLE"
TEST_DIR = "data/baseline"


def cleanup_test_data():
    """Remove test data"""
    test_project_dir = os.path.join(TEST_DIR, TEST_PROJECT)
    if os.path.exists(test_project_dir):
        shutil.rmtree(test_project_dir)
        print(f"🧹 Cleaned up test data: {test_project_dir}")


def create_sample_failures(count: int, prefix: str = "Test"):
    """Create sample failure data"""
    failures = []
    for i in range(count):
        failures.append({
            "testcase": f"{prefix}_TestCase_{i+1}",
            "error": f"Sample error message {i+1}",
            "path": f"/path/to/test/{prefix}_{i+1}",
            "stack_trace": f"Stack trace for test {i+1}"
        })
    return failures


def test_save_baseline():
    """Test saving baselines"""
    print("\n" + "=" * 60)
    print("TEST 1: Save Baseline")
    print("=" * 60)
    
    try:
        # Save first baseline
        failures1 = create_sample_failures(5, "Sprint1")
        baseline_id1 = save_baseline(TEST_PROJECT, failures1, "Sprint 1")
        print(f"✅ Saved baseline 1: {baseline_id1}")
        
        # Save second baseline
        failures2 = create_sample_failures(3, "Sprint2")
        baseline_id2 = save_baseline(TEST_PROJECT, failures2, "Sprint 2")
        print(f"✅ Saved baseline 2: {baseline_id2}")
        
        # Save third baseline
        failures3 = create_sample_failures(7, "Sprint3")
        baseline_id3 = save_baseline(TEST_PROJECT, failures3, "Sprint 3")
        print(f"✅ Saved baseline 3: {baseline_id3}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_list_baselines():
    """Test listing baselines"""
    print("\n" + "=" * 60)
    print("TEST 2: List Baselines")
    print("=" * 60)
    
    try:
        baselines = list_baselines(TEST_PROJECT)
        print(f"📊 Found {len(baselines)} baseline(s)")
        
        if len(baselines) != 3:
            print(f"❌ Expected 3 baselines, found {len(baselines)}")
            return False
        
        for i, baseline in enumerate(baselines):
            print(f"  {i+1}. {baseline['label']} - {baseline['failure_count']} failures - {baseline['created_at']}")
        
        print("✅ List baselines test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_load_baseline():
    """Test loading specific baseline"""
    print("\n" + "=" * 60)
    print("TEST 3: Load Specific Baseline")
    print("=" * 60)
    
    try:
        baselines = list_baselines(TEST_PROJECT)
        if not baselines:
            print("❌ No baselines to test")
            return False
        
        baseline_id = baselines[0]['id']
        loaded = load_baseline(TEST_PROJECT, baseline_id)
        
        if loaded is None:
            print(f"❌ Failed to load baseline {baseline_id}")
            return False
        
        print(f"✅ Loaded baseline: {loaded['label']}")
        print(f"   - ID: {loaded['id']}")
        print(f"   - Failures: {loaded['failure_count']}")
        print(f"   - Created: {loaded['created_at']}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_get_latest_baseline():
    """Test getting latest baseline"""
    print("\n" + "=" * 60)
    print("TEST 4: Get Latest Baseline")
    print("=" * 60)
    
    try:
        latest = get_latest_baseline(TEST_PROJECT)
        
        if latest is None:
            print("❌ No latest baseline found")
            return False
        
        print(f"✅ Latest baseline: {latest['label']}")
        print(f"   - Created: {latest['created_at']}")
        print(f"   - Failures: {latest['failure_count']}")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_baseline_stats():
    """Test baseline statistics"""
    print("\n" + "=" * 60)
    print("TEST 5: Baseline Statistics")
    print("=" * 60)
    
    try:
        stats = get_baseline_stats(TEST_PROJECT)
        
        print(f"📊 Statistics:")
        print(f"   - Count: {stats['count']}")
        print(f"   - Latest: {stats['latest']}")
        print(f"   - Oldest: {stats.get('oldest', 'N/A')}")
        print(f"   - Total Failures: {stats.get('total_failures', 0)}")
        
        if stats['count'] != 3:
            print(f"❌ Expected count=3, got {stats['count']}")
            return False
        
        print("✅ Statistics test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_compare_with_baseline():
    """Test comparing with baseline"""
    print("\n" + "=" * 60)
    print("TEST 6: Compare with Baseline")
    print("=" * 60)
    
    try:
        # Create current failures (mix of old and new)
        current_failures = [
            {"testcase": "Sprint3_TestCase_1", "error": "Sample error message 1"},  # Existing
            {"testcase": "Sprint3_TestCase_2", "error": "Sample error message 2"},  # Existing
            {"testcase": "NEW_TestCase_1", "error": "New error"},  # New
            {"testcase": "NEW_TestCase_2", "error": "New error 2"},  # New
        ]
        
        new_failures, existing_failures = compare_with_baseline(
            TEST_PROJECT,
            current_failures
        )
        
        print(f"📊 Comparison results:")
        print(f"   - New failures: {len(new_failures)}")
        print(f"   - Existing failures: {len(existing_failures)}")
        
        if len(new_failures) != 2:
            print(f"❌ Expected 2 new failures, got {len(new_failures)}")
            return False
        
        if len(existing_failures) != 2:
            print(f"❌ Expected 2 existing failures, got {len(existing_failures)}")
            return False
        
        print("✅ Comparison test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_baseline_limit():
    """Test baseline limit enforcement"""
    print("\n" + "=" * 60)
    print("TEST 7: Baseline Limit (Max 10)")
    print("=" * 60)
    
    try:
        # Save 12 baselines (exceeds limit of 10)
        print("📝 Saving 12 baselines...")
        for i in range(4, 13):  # Already have 3, add 9 more (total 12)
            failures = create_sample_failures(2, f"Sprint{i}")
            baseline_id = save_baseline(TEST_PROJECT, failures, f"Sprint {i}")
            print(f"   Saved: Sprint {i}")
        
        # Check count
        baselines = list_baselines(TEST_PROJECT)
        count = len(baselines)
        
        print(f"📊 Total baselines after saving 12: {count}")
        
        if count > 10:
            print(f"❌ Baseline limit not enforced! Expected ≤10, got {count}")
            return False
        
        if count == 10:
            print("✅ Baseline limit correctly enforced (10 max)")
            return True
        else:
            print(f"⚠️  Warning: Expected exactly 10, got {count}")
            return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_delete_baseline():
    """Test deleting baseline"""
    print("\n" + "=" * 60)
    print("TEST 8: Delete Baseline")
    print("=" * 60)
    
    try:
        # Get current count
        before_count = len(list_baselines(TEST_PROJECT))
        print(f"📊 Baselines before delete: {before_count}")
        
        # Delete oldest baseline
        baselines = list_baselines(TEST_PROJECT)
        if not baselines:
            print("❌ No baselines to delete")
            return False
        
        oldest = baselines[-1]
        baseline_id = oldest['id']
        
        print(f"🗑️  Deleting: {oldest['label']} ({baseline_id})")
        success = delete_baseline(TEST_PROJECT, baseline_id)
        
        if not success:
            print("❌ Delete failed")
            return False
        
        # Check count
        after_count = len(list_baselines(TEST_PROJECT))
        print(f"📊 Baselines after delete: {after_count}")
        
        if after_count != before_count - 1:
            print(f"❌ Count mismatch: expected {before_count - 1}, got {after_count}")
            return False
        
        print("✅ Delete test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_baseline_exists():
    """Test baseline existence check"""
    print("\n" + "=" * 60)
    print("TEST 9: Baseline Exists")
    print("=" * 60)
    
    try:
        # Test existing project
        exists = baseline_exists(TEST_PROJECT)
        print(f"📊 {TEST_PROJECT} exists: {exists}")
        
        if not exists:
            print(f"❌ Expected baseline to exist for {TEST_PROJECT}")
            return False
        
        # Test non-existing project
        fake_exists = baseline_exists("FAKE_PROJECT_XYZ")
        print(f"📊 FAKE_PROJECT_XYZ exists: {fake_exists}")
        
        if fake_exists:
            print("❌ Fake project should not exist")
            return False
        
        print("✅ Exists check test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_get_all_projects():
    """Test getting all projects"""
    print("\n" + "=" * 60)
    print("TEST 10: Get All Projects")
    print("=" * 60)
    
    try:
        projects = get_all_projects()
        print(f"📊 Found {len(projects)} project(s):")
        
        for project in projects:
            print(f"   - {project}")
        
        if TEST_PROJECT not in projects:
            print(f"❌ Test project {TEST_PROJECT} not found in list")
            return False
        
        print("✅ Get all projects test passed")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("MULTI-BASELINE FUNCTIONALITY TEST SUITE")
    print("=" * 80)
    
    # Cleanup before tests
    cleanup_test_data()
    
    # Run tests
    tests = [
        ("Save Baseline", test_save_baseline),
        ("List Baselines", test_list_baselines),
        ("Load Baseline", test_load_baseline),
        ("Get Latest Baseline", test_get_latest_baseline),
        ("Baseline Statistics", test_baseline_stats),
        ("Compare with Baseline", test_compare_with_baseline),
        ("Baseline Limit", test_baseline_limit),
        ("Delete Baseline", test_delete_baseline),
        ("Baseline Exists", test_baseline_exists),
        ("Get All Projects", test_get_all_projects),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total - passed} TEST(S) FAILED")
    
    # Cleanup after tests
    print()
    cleanup_test_data()
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
