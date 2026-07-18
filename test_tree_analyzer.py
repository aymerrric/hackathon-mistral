#!/usr/bin/env python3
"""Test script for the tree analyzer service.

Run with: python test_tree_analyzer.py
"""

import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.tree_analyzer import (
    TreeAnalyzer, 
    TreeAnalysisReport,
    analyze_tree,
    refine_tree,
    Severity
)
from app.schemas import TreeStructure


# =============================================================================
# Test Trees
# =============================================================================

# Valid tree
VALID_TREE = {
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1",
            "type": "question",
            "label": "Emergency?",
            "prompt": "Is this an emergency?",
            "options": [
                {"label": "Yes", "next_id": "n2"},
                {"label": "No", "next_id": "n3"}
            ]
        },
        "n2": {
            "id": "n2",
            "type": "action",
            "label": "Dispatch",
            "prompt": "Dispatching emergency services.",
            "options": [{"label": "Continue", "next_id": "n4"}]
        },
        "n3": {
            "id": "n3",
            "type": "question",
            "label": "Verify",
            "prompt": "Can you verify your identity?",
            "options": [
                {"label": "Yes", "next_id": "n5"},
                {"label": "No", "next_id": "n6"}
            ]
        },
        "n4": {
            "id": "n4",
            "type": "end",
            "label": "Complete",
            "prompt": "Emergency handled.",
            "options": []
        },
        "n5": {
            "id": "n5",
            "type": "end",
            "label": "Verified",
            "prompt": "Identity verified.",
            "options": []
        },
        "n6": {
            "id": "n6",
            "type": "end",
            "label": "Not verified",
            "prompt": "Cannot proceed.",
            "options": []
        }
    }
}

# Tree with errors
INVALID_TREE = {
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1",
            "type": "question",
            "label": "Start",
            "prompt": "Welcome",
            "options": [
                {"label": "Yes", "next_id": "n2"},
                {"label": "No", "next_id": "n99"}  # n99 doesn't exist
            ]
        },
        "n2": {
            "id": "n2",
            "type": "action",
            "label": "Step",
            "prompt": "Do something",
            "options": []  # Action nodes need exactly 1 option
        },
        "n3": {
            "id": "n3",
            "type": "question",
            "label": "TBD",  # Weak label
            "prompt": "x",  # Too short
            "options": [{"label": "Opt", "next_id": "n1"}]  # Only 1 option for question
        }
    }
}

# Tree with unreachable nodes
TREE_WITH_DEAD_CODE = {
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1",
            "type": "question",
            "label": "Start",
            "prompt": "Begin?",
            "options": [
                {"label": "Yes", "next_id": "n2"},
                {"label": "No", "next_id": "n2"}
            ]
        },
        "n2": {
            "id": "n2",
            "type": "end",
            "label": "End",
            "prompt": "Done.",
            "options": []
        },
        "n3": {
            "id": "n3",
            "type": "action",
            "label": "Unreachable",
            "prompt": "This node is never reached",
            "options": [{"label": "Continue", "next_id": "n2"}]
        }
    }
}

# Tree with cycle
TREE_WITH_CYCLE = {
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1",
            "type": "question",
            "label": "Loop",
            "prompt": "Go in circles?",
            "options": [
                {"label": "Yes", "next_id": "n2"},
                {"label": "No", "next_id": "n3"}
            ]
        },
        "n2": {
            "id": "n2",
            "type": "action",
            "label": "Go back",
            "prompt": "Going back...",
            "options": [{"label": "Continue", "next_id": "n1"}]  # Creates cycle
        },
        "n3": {
            "id": "n3",
            "type": "end",
            "label": "End",
            "prompt": "Done.",
            "options": []
        }
    }
}

# Test spec text
SAMPLE_SPEC = """
Call Center Procedure

1. Greeting
   - Answer: "Thank you for calling. How can I help you?"

2. Emergency Check
   - Ask: "Is this an emergency?"
   - If Yes: Dispatch emergency services immediately
   - If No: Continue to verification

3. Identity Verification
   - Ask: "Can you verify your full name and account number?"
   - If Verified: Proceed with request
   - If Not Verified: End call

4. Request Handling
   - Process customer request
   - Provide solution or escalate

5. Closing
   - Thank customer
   - End call
"""


# =============================================================================
# Tests
# =============================================================================

def test_valid_tree():
    """Test that a valid tree passes analysis."""
    print("\n" + "="*70)
    print("TEST: Valid Tree Analysis")
    print("="*70)
    
    report = analyze_tree(VALID_TREE)
    
    print(report.get_summary())
    
    assert report.is_valid, "Valid tree should pass analysis"
    assert len([i for i in report.issues if i.severity == Severity.ERROR]) == 0
    print("✅ PASSED: Valid tree has no errors")


def test_invalid_tree():
    """Test that invalid tree is detected."""
    print("\n" + "="*70)
    print("TEST: Invalid Tree Analysis")
    print("="*70)
    
    report = analyze_tree(INVALID_TREE)
    
    print(report.get_summary())
    print("\nErrors found:")
    for issue in report.issues:
        if issue.severity == Severity.ERROR:
            print(f"  - {issue.code}: {issue.message}")
    
    assert not report.is_valid, "Invalid tree should fail analysis"
    errors = [i for i in report.issues if i.severity == Severity.ERROR]
    assert len(errors) > 0, "Should have errors"
    
    # Check for specific error types
    error_codes = {e.code for e in errors}
    assert "INVALID_REFERENCE" in error_codes, "Should detect invalid reference"
    assert "ACTION_NEEDS_ONE_OPTION" in error_codes, "Should detect action node error"
    print("✅ PASSED: Invalid tree correctly identified with errors")


def test_unreachable_nodes():
    """Test detection of unreachable nodes."""
    print("\n" + "="*70)
    print("TEST: Unreachable Nodes Detection")
    print("="*70)
    
    report = analyze_tree(TREE_WITH_DEAD_CODE)
    
    print(report.get_summary())
    
    warnings = [i for i in report.issues if i.severity == Severity.WARNING]
    unreachable = [w for w in warnings if w.code == "UNREACHABLE_NODE"]
    
    assert len(unreachable) > 0, "Should detect unreachable nodes"
    assert any("n3" in w.message for w in unreachable), "Should identify n3 as unreachable"
    print("✅ PASSED: Unreachable nodes detected")


def test_cycle_detection():
    """Test detection of cycles in tree."""
    print("\n" + "="*70)
    print("TEST: Cycle Detection")
    print("="*70)
    
    report = analyze_tree(TREE_WITH_CYCLE)
    
    print(report.get_summary())
    
    errors = [i for i in report.issues if i.severity == Severity.ERROR]
    cycle_errors = [e for e in errors if e.code == "CYCLE_DETECTED"]
    
    assert len(cycle_errors) > 0, "Should detect cycle"
    print("✅ PASSED: Cycle detected")


def test_metrics():
    """Test that metrics are calculated correctly."""
    print("\n" + "="*70)
    print("TEST: Metrics Calculation")
    print("="*70)
    
    report = analyze_tree(VALID_TREE)
    
    print(report.get_summary())
    print("\nMetrics:")
    for k, v in report.metrics.to_dict().items():
        print(f"  {k}: {v}")
    
    assert report.metrics.node_count == 6
    assert report.metrics.question_nodes == 2
    assert report.metrics.action_nodes == 1
    assert report.metrics.end_nodes == 3
    assert report.metrics.unreachable_nodes == 0
    assert len(report.metrics.all_paths) >= 2  # At least 2 paths from root
    print("✅ PASSED: Metrics calculated correctly")


def test_coverage_analysis():
    """Test coverage analysis against spec."""
    print("\n" + "="*70)
    print("TEST: Coverage Analysis")
    print("="*70)
    
    report = analyze_tree(VALID_TREE, SAMPLE_SPEC)
    
    print(report.get_summary())
    
    assert report.coverage_score is not None, "Should have coverage score"
    assert 0 <= report.coverage_score <= 1, "Coverage should be between 0 and 1"
    print(f"Coverage score: {report.coverage_score:.2%}")
    print("✅ PASSED: Coverage analysis works")


def test_fix_suggestions():
    """Test that fix suggestions are generated."""
    print("\n" + "="*70)
    print("TEST: Fix Suggestions")
    print("="*70)
    
    report = analyze_tree(INVALID_TREE)
    
    print(report.get_summary())
    print(f"\nSuggestions ({len(report.suggestions)}):")
    for sug in report.suggestions[:5]:
        print(f"  - {sug.description}")
    
    assert len(report.suggestions) > 0, "Should have fix suggestions"
    print("✅ PASSED: Fix suggestions generated")


def test_report_serialization():
    """Test that report can be serialized to JSON."""
    print("\n" + "="*70)
    print("TEST: Report Serialization")
    print("="*70)
    
    report = analyze_tree(VALID_TREE, SAMPLE_SPEC)
    
    # Convert to dict
    report_dict = report.to_dict()
    
    # Serialize to JSON
    json_str = json.dumps(report_dict, indent=2)
    
    print(f"Report serialized to {len(json_str)} bytes")
    
    # Deserialize back
    loaded = json.loads(json_str)
    assert loaded["is_valid"] == report.is_valid
    print("✅ PASSED: Report serializes correctly")


def test_analyzer_class():
    """Test the TreeAnalyzer class directly."""
    print("\n" + "="*70)
    print("TEST: TreeAnalyzer Class")
    print("="*70)
    
    analyzer = TreeAnalyzer()
    
    # Test analyze method
    report = analyzer.analyze(VALID_TREE)
    assert report.is_valid
    print("✅ TreeAnalyzer.analyze() works")
    
    # Test suggest_fixes method
    invalid_report = analyzer.analyze(INVALID_TREE)
    fixes = analyzer.suggest_fixes(invalid_report)
    assert len(fixes) > 0
    print(f"✅ TreeAnalyzer.suggest_fixes() generated {len(fixes)} fixes")
    
    print("✅ PASSED: TreeAnalyzer class works correctly")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("RUNNING ALL TESTS")
    print("="*70)
    
    tests = [
        test_valid_tree,
        test_invalid_tree,
        test_unreachable_nodes,
        test_cycle_detection,
        test_metrics,
        test_coverage_analysis,
        test_fix_suggestions,
        test_report_serialization,
        test_analyzer_class,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {test.__name__}: {e}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
