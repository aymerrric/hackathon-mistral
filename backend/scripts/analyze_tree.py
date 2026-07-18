#!/usr/bin/env python3
"""CLI tool for analyzing and refining decision trees.

Usage:
    python scripts/analyze_tree.py analyze <tree_json_file> [--spec <spec_file>]
    python scripts/analyze_tree.py refine <tree_json_file> <spec_file> [--iterations N]
    python scripts/analyze_tree.py interact <tree_json_file> [--spec <spec_file>]

Examples:
    # Analyze a tree
    python scripts/analyze_tree.py analyze tree.json --spec spec.txt
    
    # Refine a tree with LLM (requires MISTRAL_API_KEY)
    python scripts/analyze_tree.py refine tree.json spec.txt --iterations 3
    
    # Interactive mode for fixing issues
    python scripts/analyze_tree.py interact tree.json
"""

import argparse
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.tree_analyzer import TreeAnalyzer, analyze_tree, refine_tree
from app.schemas import TreeStructure


def load_json_file(filepath: str) -> dict:
    """Load a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def load_text_file(filepath: str) -> str:
    """Load a text file."""
    with open(filepath, 'r') as f:
        return f.read()


def print_report(report, verbose: bool = False) -> None:
    """Print analysis report in a readable format."""
    print("\n" + "=" * 70)
    print(report.get_summary())
    print("=" * 70)
    
    # Print metrics
    print("\n📊 METRICS:")
    metrics = report.metrics.to_dict()
    for key, value in metrics.items():
        if key != "all_paths":  # Skip paths to avoid clutter
            print(f"   {key}: {value}")
    
    # Print issues grouped by severity
    errors = [i for i in report.issues if i.severity.value == "error"]
    warnings = [i for i in report.issues if i.severity.value == "warning"]
    info = [i for i in report.issues if i.severity.value == "info"]
    
    if errors:
        print("\n❌ ERRORS (must fix):")
        for i, issue in enumerate(errors, 1):
            loc = f"node '{issue.node_id}'" if issue.node_id else "tree"
            if issue.option_index is not None:
                loc += f", option {issue.option_index}"
            print(f"   {i}. [{issue.code}] {loc}: {issue.message}")
            if issue.suggestion:
                print(f"      → {issue.suggestion}")
            if verbose and issue.context:
                print(f"      Context: {issue.context}")
    
    if warnings:
        print("\n⚠️  WARNINGS (should fix):")
        for i, issue in enumerate(warnings, 1):
            loc = f"node '{issue.node_id}'" if issue.node_id else "tree"
            if issue.option_index is not None:
                loc += f", option {issue.option_index}"
            print(f"   {i}. [{issue.code}] {loc}: {issue.message}")
            if issue.suggestion:
                print(f"      → {issue.suggestion}")
    
    if info and verbose:
        print("\nℹ️  INFO:")
        for i, issue in enumerate(info, 1):
            print(f"   {i}. [{issue.code}]: {issue.message}")
    
    # Print suggestions
    if report.suggestions:
        print(f"\n💡 SUGGESTIONS ({len(report.suggestions)}):")
        for i, sug in enumerate(report.suggestions[:5], 1):  # Show top 5
            print(f"   {i}. [{sug.fix_type}] {sug.description} (confidence: {sug.confidence:.0%})")
    
    print()


def cmd_analyze(args) -> None:
    """Analyze a tree file."""
    tree_data = load_json_file(args.tree_file)
    spec_text = load_text_file(args.spec_file) if args.spec_file else None
    
    print(f"\nAnalyzing tree from: {args.tree_file}")
    if spec_text:
        print(f"Spec file: {args.spec_file}")
    
    report = analyze_tree(tree_data, spec_text)
    print_report(report, verbose=args.verbose)
    
    # Optionally save report
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Report saved to: {args.output}")


def cmd_refine(args) -> None:
    """Refine a tree using LLM."""
    if not os.environ.get('MISTRAL_API_KEY'):
        print("ERROR: MISTRAL_API_KEY environment variable not set")
        print("Set it with: export MISTRAL_API_KEY=your_key")
        sys.exit(1)
    
    tree_data = load_json_file(args.tree_file)
    spec_text = load_text_file(args.spec_file)
    
    print(f"\nRefining tree from: {args.tree_file}")
    print(f"Spec file: {args.spec_file}")
    print(f"Max iterations: {args.iterations}")
    
    final_tree, reports = refine_tree(tree_data, spec_text, max_iterations=args.iterations)
    
    # Print each iteration's report
    for i, report in enumerate(reports):
        print(f"\n{'='*70}")
        print(f"ITERATION {i + 1}")
        print(f"{'='*70}")
        print_report(report)
    
    # Save final tree
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(final_tree.model_dump(), f, indent=2)
        print(f"\nFinal tree saved to: {args.output}")
    else:
        print("\nFinal tree (JSON):")
        print(json.dumps(final_tree.model_dump(), indent=2))


def cmd_interact(args) -> None:
    """Interactive mode for fixing tree issues."""
    tree_data = load_json_file(args.tree_file)
    spec_text = load_text_file(args.spec_file) if args.spec_file else None
    
    print(f"\nLoaded tree from: {args.tree_file}")
    if spec_text:
        print(f"Spec file: {args.spec_file}")
    
    analyzer = TreeAnalyzer()
    
    while True:
        print("\n" + "=" * 70)
        report = analyzer.analyze(tree_data, spec_text)
        print_report(report)
        
        # Check if valid
        if report.is_valid:
            print("✅ Tree is valid!")
            if not report.suggestions:
                print("✅ No suggestions for improvement.")
            
            # Ask if user wants to continue
            choice = input("\nTree is valid. Continue editing? (y/n): ").strip().lower()
            if choice != 'y':
                break
            continue
        
        # Show menu
        print("\n🔧 FIX OPTIONS:")
        print("  1. Apply automatic fixes")
        print("  2. Edit tree manually (JSON editor)")
        print("  3. Refine with LLM (requires API key)")
        print("  4. Show detailed issue")
        print("  5. Save and exit")
        print("  6. Exit without saving")
        
        choice = input("\nChoose option (1-6): ").strip()
        
        if choice == '1':
            # Apply automatic fixes
            fixes = analyzer.suggest_fixes(report)
            print(f"\nApplying {len(fixes)} automatic fix(es)...")
            
            # Convert tree to dict for editing
            tree_dict = tree_data if isinstance(tree_data, dict) else tree_data.model_dump()
            
            for fix in fixes:
                if fix.fix_type == "add_node" and fix.target_node_id and fix.new_value:
                    tree_dict["nodes"][fix.target_node_id] = fix.new_value
                    print(f"  ✓ Added node '{fix.target_node_id}'")
                elif fix.fix_type == "remove_node" and fix.target_node_id:
                    if fix.target_node_id in tree_dict["nodes"]:
                        del tree_dict["nodes"][fix.target_node_id]
                        print(f"  ✓ Removed node '{fix.target_node_id}'")
                elif fix.fix_type == "edit_tree" and fix.new_value:
                    for key, value in fix.new_value.items():
                        tree_dict[key] = value
                        print(f"  ✓ Set tree.{key} = {value}")
            
            tree_data = tree_dict
            
        elif choice == '2':
            # Manual JSON editing
            print("\nCurrent tree (JSON):")
            print(json.dumps(tree_data if isinstance(tree_data, dict) else tree_data.model_dump(), indent=2))
            print("\nEnter new tree JSON (or press Enter to keep current):")
            new_json = input(">>> ").strip()
            if new_json:
                try:
                    tree_data = json.loads(new_json)
                    print("✓ Tree updated")
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON: {e}")
        
        elif choice == '3':
            # LLM refinement
            if not os.environ.get('MISTRAL_API_KEY'):
                print("ERROR: MISTRAL_API_KEY not set")
                continue
            
            print("\nRefining with LLM...")
            tree_structure = tree_data if isinstance(tree_data, TreeStructure) else TreeStructure.model_validate(tree_data)
            _, [new_report] = refine_tree(tree_structure, spec_text or "", max_iterations=1)
            tree_data = new_report  # Will be the refined tree from the last report
            print("✓ LLM refinement complete")
        
        elif choice == '4':
            # Show detailed issue
            print("\nEnter issue number to view details:")
            for i, issue in enumerate(report.issues, 1):
                print(f"  {i}. [{issue.severity.value}] {issue.code}: {issue.message}")
            
            try:
                idx = int(input("Issue #: ").strip()) - 1
                issue = report.issues[idx]
                print(f"\nDetails for issue #{idx + 1}:")
                print(f"  Code: {issue.code}")
                print(f"  Severity: {issue.severity.value}")
                print(f"  Message: {issue.message}")
                print(f"  Node: {issue.node_id}")
                if issue.option_index is not None:
                    print(f"  Option: {issue.option_index}")
                print(f"  Suggestion: {issue.suggestion}")
                print(f"  Context: {issue.context}")
            except (ValueError, IndexError):
                print("Invalid issue number")
        
        elif choice == '5':
            # Save and exit
            output_file = args.output or args.tree_file
            with open(output_file, 'w') as f:
                tree_dict = tree_data if isinstance(tree_data, dict) else tree_data.model_dump()
                json.dump(tree_dict, f, indent=2)
            print(f"\n✓ Tree saved to: {output_file}")
            break
        
        elif choice == '6':
            # Exit without saving
            print("\nExiting without saving.")
            break
        
        else:
            print("Invalid choice")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and refine decision trees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_tree.py analyze tree.json --spec spec.txt
  python analyze_tree.py refine tree.json spec.txt --iterations 3
  python analyze_tree.py interact tree.json
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a tree for issues')
    analyze_parser.add_argument('tree_file', help='JSON file containing the tree')
    analyze_parser.add_argument('--spec', dest='spec_file', help='Text file with spec for coverage analysis')
    analyze_parser.add_argument('-v', '--verbose', action='store_true', help='Show verbose output')
    analyze_parser.add_argument('-o', '--output', help='Output file for report')
    
    # Refine command
    refine_parser = subparsers.add_parser('refine', help='Refine a tree using LLM')
    refine_parser.add_argument('tree_file', help='JSON file containing the tree')
    refine_parser.add_argument('spec_file', help='Text file with specification')
    refine_parser.add_argument('-i', '--iterations', type=int, default=3, help='Max iterations (default: 3)')
    refine_parser.add_argument('-o', '--output', help='Output file for refined tree')
    
    # Interact command
    interact_parser = subparsers.add_parser('interact', help='Interactive tree editing')
    interact_parser.add_argument('tree_file', help='JSON file containing the tree')
    interact_parser.add_argument('--spec', dest='spec_file', help='Text file with spec')
    interact_parser.add_argument('-o', '--output', help='Output file (default: overwrite input)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run the appropriate command
    if args.command == 'analyze':
        cmd_analyze(args)
    elif args.command == 'refine':
        cmd_refine(args)
    elif args.command == 'interact':
        cmd_interact(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
