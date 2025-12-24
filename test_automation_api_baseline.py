#!/usr/bin/env python3
"""
Test script to verify AutomationAPI baseline save and compare functionality
"""

import os
import sys
import json
import shutil

# Setup test environment
os.environ["BASELINE_ADMIN_KEY"] = "test_admin_key"

# Import the fixed module
try:
    from automation_api_baseline_manager_fixed import (
        save_baseline,
        load_baseline,
        compare_with_baseline,
        baseline_exists,
        get_baseline_info
    )
    print("✅ Successfully imported fixed automation_api_baseline_manager")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


# Sample AutomationAPI failures (simulating what extractor returns)
SAMPLE_FAILURES = [
    {
        "project": "AutomationAPI_LightningLWC",
        "spec_file": "AccountSpec",
        "test_name": "should create new account",
        "error_summary": "Element not found: button[id='save']",
        "error_details": "Failed to locate element with selector: button[id='save']\nStack trace...",
        "is_skipped": False,
        "classname": "AccountSpec",
        "failure_type": "exception",
        "execution_time": "2.5",
        "timestamp": "2025-12-24T10:30:00"
    },
    {
        "project": "AutomationAPI_LightningLWC",
        "spec_file": "AccountSpec",
        "test_name": "should edit account details",
        "error_summary": "Skipping the test case because the previous step has failed",
        "error_details": "Previous step failed with error: Element not found",
        "is_skipped": True,
        "classname": "AccountSpec",
        "failure_type": "exception",
        "execution_time": "0.1",
        "timestamp": "2025-12-24T10:30:00"
    },
    {
        "project": "AutomationAPI_LightningLWC",
        "spec_file": "ContactSpec",
        "test_name": "should create contact",
        "error_summary": "Timeout waiting for element: input[name='firstName']",
        "error_details": "Timeout of 30000ms exceeded\nStack trace...",
        "is_skipped": False,
        "classname": "ContactSpec",
        "failure_type": "timeout",
        "execution_time": "30.5",
        "timestamp": "2025-12-24T10:30:00"
    }
]


def test_save_baseline():
    """Test saving AutomationAPI baseline"""
    print("\n" + "="*60)
    print("TEST 1: Save AutomationAPI Baseline")
    print("="*60)
    
    project = "AutomationAPI_LightningLWC"
    
    try:
        # Save baseline
        save_baseline(project, SAMPLE_FAILURES, "test_admin_key")
        print(f"✅ Saved baseline for {project}")
        
        # Verify baseline exists
        if baseline_exists(project):
            print(f"✅ Baseline exists check passed")
        else:
            print(f"❌ Baseline exists check failed")
            return False
        
        # Verify baseline content
        loaded = load_baseline(project)
        print(f"✅ Loaded {len(loaded)} failures from baseline")
        
        # Check that metadata records were filtered out
        has_metadata = any(f.get("_no_failures") for f in loaded)
        if has_metadata:
            print("❌ Metadata records were not filtered out")
            return False
        else:
            print("✅ Metadata records properly filtered")
        
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_compare_exact_match():
    """Test comparing with exact same failures"""
    print("\n" + "="*60)
    print("TEST 2: Compare with Exact Match (All Existing)")
    print("="*60)
    
    project = "AutomationAPI_LightningLWC"
    
    try:
        # Compare with exact same failures
        new_failures, existing_failures = compare_with_baseline(project, SAMPLE_FAILURES)
        
        print(f"📊 Results:")
        print(f"   New failures: {len(new_failures)}")
        print(f"   Existing failures: {len(existing_failures)}")
        
        # All should be existing (matching baseline)
        if len(new_failures) == 0 and len(existing_failures) == 3:
            print("✅ All failures correctly identified as existing")
            return True
        else:
            print(f"❌ Expected 0 new and 3 existing, got {len(new_failures)} new and {len(existing_failures)} existing")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_compare_with_new_failures():
    """Test comparing with some new failures"""
    print("\n" + "="*60)
    print("TEST 3: Compare with New Failures")
    print("="*60)
    
    project = "AutomationAPI_LightningLWC"
    
    # Create a mix of existing and new failures
    mixed_failures = SAMPLE_FAILURES.copy()
    mixed_failures.append({
        "project": "AutomationAPI_LightningLWC",
        "spec_file": "OpportunitySpec",
        "test_name": "should close opportunity",
        "error_summary": "Element not interactable: button[id='close']",
        "error_details": "Element is not clickable at point (x, y)",
        "is_skipped": False,
        "classname": "OpportunitySpec",
        "failure_type": "exception",
        "execution_time": "1.2",
        "timestamp": "2025-12-24T10:35:00"
    })
    
    try:
        new_failures, existing_failures = compare_with_baseline(project, mixed_failures)
        
        print(f"📊 Results:")
        print(f"   New failures: {len(new_failures)}")
        print(f"   Existing failures: {len(existing_failures)}")
        
        if len(new_failures) == 1 and len(existing_failures) == 3:
            print("✅ Correctly identified 1 new and 3 existing failures")
            print(f"   New failure: {new_failures[0]['test_name']}")
            return True
        else:
            print(f"❌ Expected 1 new and 3 existing, got {len(new_failures)} new and {len(existing_failures)} existing")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_baseline_info():
    """Test getting baseline info"""
    print("\n" + "="*60)
    print("TEST 4: Get Baseline Info")
    print("="*60)
    
    project = "AutomationAPI_LightningLWC"
    
    try:
        info = get_baseline_info(project)
        
        print(f"📊 Baseline Info:")
        print(f"   Exists: {info['exists']}")
        print(f"   Total count: {info['count']}")
        print(f"   Real failures: {info['real_failures']}")
        print(f"   Skipped failures: {info['skipped_failures']}")
        print(f"   Specs: {', '.join(info['specs'])}")
        
        if info['exists'] and info['count'] == 3:
            print("✅ Baseline info correct")
            return True
        else:
            print("❌ Baseline info incorrect")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_metadata_filtering():
    """Test that metadata records are properly filtered"""
    print("\n" + "="*60)
    print("TEST 5: Metadata Filtering")
    print("="*60)
    
    project = "AutomationAPI_TEST_METADATA"
    
    # Create failures with metadata record
    failures_with_metadata = SAMPLE_FAILURES.copy()
    failures_with_metadata.append({
        "project": "AutomationAPI_TEST_METADATA",
        "spec_file": "__NO_FAILURES__",
        "test_name": "All tests passed",
        "error_summary": "",
        "error_details": "",
        "is_skipped": False,
        "_no_failures": True,
        "total_tests": 10,
        "total_failures": 0
    })
    
    try:
        # Save baseline
        save_baseline(project, failures_with_metadata, "test_admin_key")
        
        # Load and check
        loaded = load_baseline(project)
        
        print(f"📊 Results:")
        print(f"   Saved {len(failures_with_metadata)} records (including metadata)")
        print(f"   Loaded {len(loaded)} records (should exclude metadata)")
        
        # Should have filtered out metadata record
        if len(loaded) == 3:
            print("✅ Metadata record properly filtered during save")
            return True
        else:
            print(f"❌ Expected 3 records, got {len(loaded)}")
            return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def cleanup():
    """Clean up test data"""
    test_dir = "baselines/automation_api"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
        print(f"\n🧹 Cleaned up test directory: {test_dir}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("AUTOMATIONAPI BASELINE MANAGER TEST SUITE")
    print("="*80)
    
    # Clean up before tests
    cleanup()
    
    # Run tests
    tests = [
        ("Save Baseline", test_save_baseline),
        ("Compare Exact Match", test_compare_exact_match),
        ("Compare with New Failures", test_compare_with_new_failures),
        ("Get Baseline Info", test_baseline_info),
        ("Metadata Filtering", test_metadata_filtering),
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
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
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
        print("\n📝 Summary of fixes:")
        print("   ✅ Removed orphaned code from save_baseline")
        print("   ✅ Fixed comparison logic to use spec_file + test_name + error_summary")
        print("   ✅ Properly filter metadata records (_no_failures)")
        print("   ✅ Include error_details in baseline for better context")
        print("   ✅ Baseline exists check now verifies content")
    else:
        print(f"⚠️  {total - passed} TEST(S) FAILED")
    
    # Clean up after tests
    cleanup()
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
