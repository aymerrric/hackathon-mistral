"""Tree analysis and refinement service.

Provides deep analysis of generated decision trees with:
- Structural validation (beyond basic schema)
- Semantic quality checks
- Coverage analysis against spec
- LLM-powered fix suggestions
- Iterative refinement workflow
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mistralai.client import MistralClient

from app.config import settings
from app.schemas import TreeStructure, TreeNode, TreeOption, NodeType


# =============================================================================
# Data Classes for Analysis Results
# =============================================================================

class Severity(Enum):
    ERROR = "error"      # Must fix, tree is invalid
    WARNING = "warning"  # Should fix, potential issue
    INFO = "info"        # Informational, best practice
    SUGGESTION = "suggestion"  # Optional improvement


@dataclass
class Issue:
    """A single issue found in the tree."""
    severity: Severity
    code: str           # e.g., "MISSING_NODE", "INVALID_REFERENCE"
    message: str
    node_id: str | None = None
    option_index: int | None = None
    suggestion: str | None = None
    context: dict = field(default_factory=dict)  # Additional info for fixes
    
    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "node_id": self.node_id,
            "option_index": self.option_index,
            "suggestion": self.suggestion,
            "context": self.context
        }


@dataclass 
class FixSuggestion:
    """A suggested fix for an issue."""
    issue_code: str
    description: str
    fix_type: str  # "edit_node", "add_node", "remove_node", "reorder", "merge"
    target_node_id: str | None = None
    new_value: dict | None = None  # For edit operations
    old_value: Any | None = None
    confidence: float = 1.0  # 0-1, how confident in this fix
    
    def to_dict(self) -> dict:
        return {
            "issue_code": self.issue_code,
            "description": self.description,
            "fix_type": self.fix_type,
            "target_node_id": self.target_node_id,
            "new_value": self.new_value,
            "old_value": self.old_value,
            "confidence": self.confidence
        }


@dataclass
class TreeMetrics:
    """Quantitative metrics about the tree."""
    node_count: int = 0
    edge_count: int = 0
    depth: int = 0
    max_depth: int = 0
    avg_branching_factor: float = 0.0
    question_nodes: int = 0
    action_nodes: int = 0
    end_nodes: int = 0
    unreachable_nodes: int = 0
    longest_path_length: int = 0
    all_paths: list[list[str]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "depth": self.depth,
            "max_depth": self.max_depth,
            "avg_branching_factor": round(self.avg_branching_factor, 2),
            "question_nodes": self.question_nodes,
            "action_nodes": self.action_nodes,
            "end_nodes": self.end_nodes,
            "unreachable_nodes": self.unreachable_nodes,
            "longest_path_length": self.longest_path_length,
            "path_count": len(self.all_paths)
        }


@dataclass
class TreeAnalysisReport:
    """Complete analysis report for a tree."""
    tree_id: str | None = None
    is_valid: bool = False
    issues: list[Issue] = field(default_factory=list)
    metrics: TreeMetrics = field(default_factory=TreeMetrics)
    suggestions: list[FixSuggestion] = field(default_factory=list)
    coverage_score: float | None = None  # 0-1, if spec text provided
    confidence_score: float | None = None  # 0-1, overall tree quality
    
    def to_dict(self) -> dict:
        return {
            "tree_id": self.tree_id,
            "is_valid": self.is_valid,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics.to_dict(),
            "suggestions": [s.to_dict() for s in self.suggestions],
            "coverage_score": self.coverage_score,
            "confidence_score": self.confidence_score,
            "summary": self.get_summary()
        }
    
    def get_summary(self) -> str:
        """Generate a human-readable summary."""
        error_count = len([i for i in self.issues if i.severity == Severity.ERROR])
        warning_count = len([i for i in self.issues if i.severity == Severity.WARNING])
        suggestion_count = len(self.suggestions)
        
        lines = [
            f"Tree Analysis: {'✓ VALID' if self.is_valid else '✗ INVALID'}",
            f"  Nodes: {self.metrics.node_count} ({self.metrics.question_nodes} questions, "
            f"{self.metrics.action_nodes} actions, {self.metrics.end_nodes} ends)",
            f"  Depth: {self.metrics.depth} (max: {self.metrics.max_depth})",
            f"  Paths: {len(self.metrics.all_paths)} total, longest: {self.metrics.longest_path_length}"
        ]
        
        if error_count > 0:
            lines.append(f"  ❌ {error_count} error(s) must be fixed")
        if warning_count > 0:
            lines.append(f"  ⚠️  {warning_count} warning(s)")
        if suggestion_count > 0:
            lines.append(f"  💡 {suggestion_count} improvement(s) suggested")
        
        if self.coverage_score is not None:
            lines.append(f"  📊 Coverage: {self.coverage_score:.1%}")
        if self.confidence_score is not None:
            lines.append(f"  🎯 Confidence: {self.confidence_score:.1%}")
            
        return "\n".join(lines)
    
    def get_formatted_errors(self) -> str:
        """Return formatted error messages for LLM consumption."""
        errors = [i for i in self.issues if i.severity == Severity.ERROR]
        if not errors:
            return "No errors found."
        
        lines = [f"Found {len(errors)} error(s) in the tree:"]
        for i, issue in enumerate(errors, 1):
            location = f"node '{issue.node_id}'" 
            if issue.option_index is not None:
                location += f", option {issue.option_index}"
            lines.append(f"{i}. [{issue.code}] {location}: {issue.message}")
            if issue.suggestion:
                lines.append(f"   Suggestion: {issue.suggestion}")
        return "\n".join(lines)


# =============================================================================
# Tree Analyzer Class
# =============================================================================

class TreeAnalyzer:
    """Analyzes decision trees for structural and semantic issues."""
    
    def __init__(self, mistral_client: MistralClient | None = None):
        self.client = mistral_client or (MistralClient(api_key=settings.mistral_api_key) 
                                          if settings.mistral_api_key else None)
    
    # -------------------------------------------------------------------------
    # Main Analysis Methods
    # -------------------------------------------------------------------------
    
    def analyze(self, tree: TreeStructure | dict, spec_text: str | None = None) -> TreeAnalysisReport:
        """Perform complete analysis of a tree.
        
        Args:
            tree: TreeStructure instance or raw dict
            spec_text: Optional source spec for coverage analysis
            
        Returns:
            TreeAnalysisReport with all issues, metrics, and suggestions
        """
        # Convert dict to TreeStructure if needed
        if isinstance(tree, dict):
            try:
                tree = TreeStructure.model_validate(tree)
            except Exception as e:
                return TreeAnalysisReport(
                    tree_id=None,
                    is_valid=False,
                    issues=[Issue(
                        severity=Severity.ERROR,
                        code="INVALID_SCHEMA",
                        message=f"Tree does not conform to schema: {str(e)}"
                    )]
                )
        
        report = TreeAnalysisReport(tree_id=getattr(tree, 'id', None))
        
        # Run all analysis checks
        self._check_structural_validity(tree, report)
        self._check_node_quality(tree, report)
        self._check_path_validity(tree, report)
        self._calculate_metrics(tree, report)
        self._generate_suggestions(tree, report)
        
        if spec_text:
            self._check_spec_coverage(tree, spec_text, report)
        
        # Determine overall validity
        report.is_valid = not any(
            i.severity == Severity.ERROR for i in report.issues
        )
        
        # Calculate confidence score (0-1)
        report.confidence_score = self._calculate_confidence_score(report)
        
        return report
    
    def refine(self, tree: TreeStructure | dict, spec_text: str, 
               max_iterations: int = 3) -> tuple[TreeStructure, list[TreeAnalysisReport]]:
        """Iteratively refine a tree using LLM feedback.
        
        Args:
            tree: Initial tree (dict or TreeStructure)
            spec_text: Source specification text
            max_iterations: Maximum refinement iterations
            
        Returns:
            Tuple of (final_tree, list_of_reports_from_each_iteration)
        """
        if isinstance(tree, dict):
            tree = TreeStructure.model_validate(tree)
        
        reports: list[TreeAnalysisReport] = []
        
        for iteration in range(max_iterations):
            # Analyze current tree
            report = self.analyze(tree, spec_text)
            reports.append(report)
            
            # Check if we're done
            if report.is_valid and not report.suggestions:
                break
            
            # If no LLM client, we can't refine further
            if self.client is None:
                break
            
            # Use LLM to fix issues
            tree = self._refine_with_llm(tree, report, spec_text, iteration)
        
        return tree, reports
    
    def suggest_fixes(self, report: TreeAnalysisReport) -> list[FixSuggestion]:
        """Generate fix suggestions for issues in a report.
        
        Args:
            report: Analysis report with issues
            
        Returns:
            List of suggested fixes
        """
        suggestions: list[FixSuggestion] = []
        
        for issue in report.issues:
            suggestions.extend(self._generate_fix_for_issue(issue, report))
        
        # Also generate proactive suggestions
        suggestions.extend(self._generate_proactive_suggestions(report))
        
        return suggestions
    
    # -------------------------------------------------------------------------
    # Structural Validation Checks
    # -------------------------------------------------------------------------
    
    def _check_structural_validity(self, tree: TreeStructure, report: TreeAnalysisReport) -> None:
        """Check basic structural integrity."""
        nodes = tree.nodes
        root_id = tree.root_id
        
        # Check root exists
        if root_id not in nodes:
            report.issues.append(Issue(
                severity=Severity.ERROR,
                code="MISSING_ROOT",
                message=f"Root node '{root_id}' does not exist in nodes",
                suggestion=f"Create a node with id '{root_id}' or change root_id to an existing node"
            ))
            return  # Can't check further without root
        
        # Check all node IDs are unique
        seen_ids = set()
        for node_id in nodes:
            if node_id in seen_ids:
                report.issues.append(Issue(
                    severity=Severity.ERROR,
                    code="DUPLICATE_NODE_ID",
                    message=f"Node ID '{node_id}' appears multiple times",
                    node_id=node_id,
                    suggestion="Use unique IDs for each node"
                ))
            seen_ids.add(node_id)
        
        # Check all option next_ids reference existing nodes
        for node_id, node in nodes.items():
            for opt_idx, option in enumerate(node.options):
                if option.next_id not in nodes:
                    # Find similar node IDs for suggestion
                    similar = self._find_similar_ids(option.next_id, list(nodes.keys()))
                    suggestion = f"Did you mean: {', '.join(similar[:3])}" if similar else \
                                "Create the referenced node or correct the next_id"
                    report.issues.append(Issue(
                        severity=Severity.ERROR,
                        code="INVALID_REFERENCE",
                        message=f"Option references non-existent node '{option.next_id}'",
                        node_id=node_id,
                        option_index=opt_idx,
                        suggestion=suggestion,
                        context={"referenced_id": option.next_id, "available_ids": list(nodes.keys())}
                    ))
        
        # Check node type constraints
        for node_id, node in nodes.items():
            if node.type == "question" and len(node.options) < 2:
                report.issues.append(Issue(
                    severity=Severity.ERROR,
                    code="QUESTION_NEEDS_OPTIONS",
                    message=f"Question node '{node_id}' must have >= 2 options (has {len(node.options)})",
                    node_id=node_id,
                    suggestion="Add more options or change node type to 'action' or 'end'"
                ))
            elif node.type == "action" and len(node.options) != 1:
                report.issues.append(Issue(
                    severity=Severity.ERROR,
                    code="ACTION_NEEDS_ONE_OPTION",
                    message=f"Action node '{node_id}' must have exactly 1 option (has {len(node.options)})",
                    node_id=node_id,
                    suggestion="Add exactly one 'Continue' option or change node type"
                ))
            elif node.type == "action" and node.options and node.options[0].label != "Continue":
                report.issues.append(Issue(
                    severity=Severity.WARNING,
                    code="ACTION_OPTION_LABEL",
                    message=f"Action node '{node_id}' option should be labeled 'Continue' (is '{node.options[0].label}')",
                    node_id=node_id,
                    suggestion="Change option label to 'Continue' for consistency"
                ))
            elif node.type == "end" and len(node.options) != 0:
                report.issues.append(Issue(
                    severity=Severity.ERROR,
                    code="END_NEEDS_NO_OPTIONS",
                    message=f"End node '{node_id}' must have 0 options (has {len(node.options)})",
                    node_id=node_id,
                    suggestion="Remove all options from end node"
                ))
    
    def _check_node_quality(self, tree: TreeStructure, report: TreeAnalysisReport) -> None:
        """Check for quality issues in individual nodes."""
        nodes = tree.nodes
        
        for node_id, node in nodes.items():
            # Check for empty or placeholder labels
            if not node.label or node.label.lower() in ['tbd', 'todo', 'fixme', 'untitled', 'node']:
                report.issues.append(Issue(
                    severity=Severity.WARNING,
                    code="WEAK_LABEL",
                    message=f"Node '{node_id}' has weak/unclear label: '{node.label}'",
                    node_id=node_id,
                    suggestion="Use a descriptive label (2-8 words)"
                ))
            
            # Check label length
            if node.label and len(node.label.split()) > 8:
                report.issues.append(Issue(
                    severity=Severity.INFO,
                    code="LONG_LABEL",
                    message=f"Node '{node_id}' label is long ({len(node.label.split())} words)",
                    node_id=node_id,
                    suggestion="Keep labels to 2-8 words"
                ))
            
            # Check prompt exists and is meaningful
            if not node.prompt or len(node.prompt.strip()) < 10:
                report.issues.append(Issue(
                    severity=Severity.WARNING,
                    code="MISSING_PROMPT",
                    message=f"Node '{node_id}' has missing or very short prompt",
                    node_id=node_id,
                    suggestion="Add a clear, actionable prompt for the agent"
                ))
            
            # Check for duplicate labels
            label_counts = {}
            for nid, n in nodes.items():
                label = n.label.lower()
                label_counts[label] = label_counts.get(label, 0) + 1
            
            if label_counts.get(node.label.lower(), 0) > 1:
                report.issues.append(Issue(
                    severity=Severity.WARNING,
                    code="DUPLICATE_LABEL",
                    message=f"Node '{node_id}' has duplicate label '{node.label}'",
                    node_id=node_id,
                    suggestion="Use unique, descriptive labels for each node"
                ))
            
            # Check option labels
            for opt_idx, option in enumerate(node.options):
                if not option.label or option.label.lower() in ['tbd', 'todo', 'fixme', 'option']:
                    report.issues.append(Issue(
                        severity=Severity.WARNING,
                        code="WEAK_OPTION_LABEL",
                        message=f"Node '{node_id}' option {opt_idx} has weak label: '{option.label}'",
                        node_id=node_id,
                        option_index=opt_idx,
                        suggestion="Use clear, actionable option labels"
                    ))
                
                # Check for duplicate option labels in same node
                option_labels = [o.label for o in node.options]
                if option_labels.count(option.label) > 1:
                    report.issues.append(Issue(
                        severity=Severity.ERROR,
                        code="DUPLICATE_OPTION_LABEL",
                        message=f"Node '{node_id}' has duplicate option label '{option.label}'",
                        node_id=node_id,
                        option_index=opt_idx,
                        suggestion="Each option in a node must have a unique label"
                    ))
    
    def _check_path_validity(self, tree: TreeStructure, report: TreeAnalysisReport) -> None:
        """Check that all paths through the tree are valid."""
        nodes = tree.nodes
        root_id = tree.root_id
        
        if root_id not in nodes:
            return
        
        # Find all paths from root to end nodes
        visited = set()
        path_count = 0
        max_path_length = 0
        paths_to_end = []
        
        def dfs(node_id: str, current_path: list[str], path_visited: set, depth: int = 0):
            nonlocal path_count, max_path_length, paths_to_end, visited
            
            # Safety check for recursion depth
            if depth > 100:
                return
            
            # Check for cycles in current path
            if node_id in path_visited:
                cycle_start_idx = list(current_path).index(node_id)
                cycle = current_path[cycle_start_idx:]
                report.issues.append(Issue(
                    severity=Severity.ERROR,
                    code="CYCLE_DETECTED",
                    message=f"Cycle detected: {' -> '.join(cycle)}",
                    node_id=node_id,
                    suggestion=f"Break the cycle by changing a next_id in one of these nodes: {', '.join(cycle)}"
                ))
                return
            
            new_path_visited = path_visited | {node_id}
            new_current_path = current_path + [node_id]
            visited.add(node_id)
            
            node = nodes[node_id]
            
            # If end node, record path
            if node.type == "end":
                path_count += 1
                paths_to_end.append(new_current_path)
                max_path_length = max(max_path_length, len(new_current_path))
            else:
                # Continue DFS with new copies
                for option in node.options:
                    if option.next_id in nodes:
                        dfs(option.next_id, new_current_path, new_path_visited, depth + 1)
        
        dfs(root_id, [], set(), 0)
        
        # Check if any paths exist
        if path_count == 0 and root_id in nodes:
            report.issues.append(Issue(
                severity=Severity.ERROR,
                code="NO_PATHS_TO_END",
                message="No valid paths from root to end nodes exist",
                node_id=root_id,
                suggestion="Ensure all paths eventually reach an end node"
            ))
        
        # Check for unreachable nodes
        reachable = visited
        unreachable = set(nodes.keys()) - reachable
        for node_id in unreachable:
            report.issues.append(Issue(
                severity=Severity.WARNING,
                code="UNREACHABLE_NODE",
                message=f"Node '{node_id}' is unreachable from root",
                node_id=node_id,
                suggestion="Remove this node or add a path to it from the root"
            ))
        
        # Check for very long paths (potential issue)
        if max_path_length > 15:
            report.issues.append(Issue(
                severity=Severity.INFO,
                code="LONG_PATH",
                message=f"Longest path has {max_path_length} nodes (recommend < 15)",
                suggestion="Consider simplifying or breaking up long paths"
            ))
        
        # Store paths for metrics
        report.metrics.all_paths = paths_to_end
    
    def _check_spec_coverage(self, tree: TreeStructure, spec_text: str, 
                              report: TreeAnalysisReport) -> None:
        """Check if the tree covers the specification document."""
        if not spec_text:
            return
        
        # Simple keyword-based coverage check
        # Extract key terms from spec
        spec_keywords = self._extract_keywords(spec_text)
        tree_text = self._tree_to_text(tree)
        tree_keywords = self._extract_keywords(tree_text)
        
        # Calculate coverage
        covered = set(spec_keywords) & set(tree_keywords)
        coverage = len(covered) / len(spec_keywords) if spec_keywords else 1.0
        report.coverage_score = coverage
        
        # Find important spec terms not in tree
        missing_important = [kw for kw in spec_keywords if kw not in tree_keywords and len(kw) > 4]
        if missing_important and len(missing_important) <= 10:
            report.issues.append(Issue(
                severity=Severity.WARNING,
                code="LOW_COVERAGE",
                message=f"Spec coverage is low ({coverage:.0%}). Missing terms: {', '.join(missing_important[:5])}",
                suggestion="Add nodes to cover these specification concepts"
            ))
    
    # -------------------------------------------------------------------------
    # Metrics Calculation
    # -------------------------------------------------------------------------
    
    def _calculate_metrics(self, tree: TreeStructure, report: TreeAnalysisReport) -> None:
        """Calculate quantitative metrics for the tree."""
        nodes = tree.nodes
        
        report.metrics.node_count = len(nodes)
        report.metrics.question_nodes = sum(1 for n in nodes.values() if n.type == "question")
        report.metrics.action_nodes = sum(1 for n in nodes.values() if n.type == "action")
        report.metrics.end_nodes = sum(1 for n in nodes.values() if n.type == "end")
        
        # Calculate edges
        edge_count = sum(len(n.options) for n in nodes.values())
        report.metrics.edge_count = edge_count
        
        # Calculate depth and max depth
        if tree.root_id in nodes:
            depths = {}
            visited_depth = set()
            
            def calculate_depth(node_id: str, depth: int):
                if node_id in visited_depth:
                    return
                visited_depth.add(node_id)
                depths[node_id] = depth
                node = nodes[node_id]
                for option in node.options:
                    if option.next_id in nodes:
                        calculate_depth(option.next_id, depth + 1)
            
            calculate_depth(tree.root_id, 0)
            
            if depths:
                report.metrics.depth = sum(depths.values()) / len(depths)
                report.metrics.max_depth = max(depths.values())
        
        # Calculate longest path
        if report.metrics.all_paths:
            report.metrics.longest_path_length = max(len(p) for p in report.metrics.all_paths)
        
        # Average branching factor
        if report.metrics.node_count > 0:
            report.metrics.avg_branching_factor = edge_count / report.metrics.node_count
        
        # Unreachable nodes (already counted in _check_path_validity)
        reachable = set()
        if tree.root_id in nodes:
            stack = [tree.root_id]
            while stack:
                node_id = stack.pop()
                if node_id in reachable:
                    continue
                reachable.add(node_id)
                node = nodes[node_id]
                for option in node.options:
                    if option.next_id in nodes:
                        stack.append(option.next_id)
        
        report.metrics.unreachable_nodes = len(nodes) - len(reachable)
    
    # -------------------------------------------------------------------------
    # Fix Suggestions
    # -------------------------------------------------------------------------
    
    def _generate_suggestions(self, tree: TreeStructure, report: TreeAnalysisReport) -> None:
        """Generate automatic fix suggestions."""
        suggestions: list[FixSuggestion] = []
        
        for issue in report.issues:
            suggestions.extend(self._generate_fix_for_issue(issue, report))
        
        # Proactive suggestions
        suggestions.extend(self._generate_proactive_suggestions(report))
        
        report.suggestions = suggestions
    
    def _generate_fix_for_issue(self, issue: Issue, report: TreeAnalysisReport) -> list[FixSuggestion]:
        """Generate fix suggestions for a specific issue."""
        suggestions = []
        
        if issue.code == "INVALID_REFERENCE" and issue.context.get("referenced_id"):
            # Suggest creating the missing node
            missing_id = issue.context["referenced_id"]
            suggestions.append(FixSuggestion(
                issue_code=issue.code,
                description=f"Create missing node '{missing_id}'",
                fix_type="add_node",
                target_node_id=missing_id,
                new_value={
                    "id": missing_id,
                    "type": "end",
                    "label": "New Node",
                    "prompt": "To be defined",
                    "options": []
                },
                confidence=0.8
            ))
            
            # Also suggest similar existing nodes
            # Get all node IDs from context or from the tree structure
            available_ids = issue.context.get("available_ids", [])
            if available_ids:
                similar = self._find_similar_ids(missing_id, available_ids)
                for sim_id in similar:
                    suggestions.append(FixSuggestion(
                        issue_code=issue.code,
                        description=f"Change reference to existing node '{sim_id}'",
                        fix_type="edit_node",
                        target_node_id=issue.node_id,
                        old_value=missing_id,
                        new_value={"next_id": sim_id},
                        confidence=0.9
                    ))
        
        elif issue.code == "MISSING_ROOT":
            # Suggest using first available node or creating root
            available = list(report.metrics.all_paths[0]) if report.metrics.all_paths else []
            if available:
                suggestions.append(FixSuggestion(
                    issue_code=issue.code,
                    description=f"Set root_id to existing node '{available[0]}'",
                    fix_type="edit_tree",
                    new_value={"root_id": available[0]},
                    confidence=1.0
                ))
        
        elif issue.code == "DUPLICATE_NODE_ID":
            # Suggest renaming duplicate
            suggestions.append(FixSuggestion(
                issue_code=issue.code,
                description=f"Rename duplicate node '{issue.node_id}'",
                fix_type="edit_node",
                target_node_id=issue.node_id,
                new_value={"id": f"{issue.node_id}_copy"},
                confidence=1.0
            ))
        
        elif issue.code == "UNREACHABLE_NODE":
            suggestions.append(FixSuggestion(
                issue_code=issue.code,
                description=f"Remove unreachable node '{issue.node_id}'",
                fix_type="remove_node",
                target_node_id=issue.node_id,
                confidence=0.9
            ))
        
        return suggestions
    
    def _generate_proactive_suggestions(self, report: TreeAnalysisReport) -> list[FixSuggestion]:
        """Generate suggestions even when there are no errors."""
        suggestions = []
        
        # Suggest adding common nodes if missing
        if report.metrics.end_nodes == 0:
            suggestions.append(FixSuggestion(
                issue_code="MISSING_END",
                description="Add at least one end node",
                fix_type="add_node",
                target_node_id="end_1",
                new_value={
                    "id": "end_1",
                    "type": "end",
                    "label": "Call Complete",
                    "prompt": "Thank you for calling. Have a great day.",
                    "options": []
                },
                confidence=0.7
            ))
        
        # Suggest balancing if tree is too deep
        if report.metrics.max_depth > 10:
            suggestions.append(FixSuggestion(
                issue_code="DEEP_TREE",
                description=f"Tree is deep ({report.metrics.max_depth} levels). Consider flattening.",
                fix_type="restructure",
                confidence=0.6
            ))
        
        # Suggest adding description metadata
        if report.metrics.node_count > 0:
            suggestions.append(FixSuggestion(
                issue_code="ADD_METADATA",
                description="Add description field to nodes for better documentation",
                fix_type="edit_schema",
                confidence=0.5
            ))
        
        return suggestions
    
    # -------------------------------------------------------------------------
    # LLM Refinement
    # -------------------------------------------------------------------------
    
    def _refine_with_llm(self, tree: TreeStructure, report: TreeAnalysisReport, 
                         spec_text: str, iteration: int) -> TreeStructure:
        """Use LLM to refine the tree based on analysis report."""
        if not self.client:
            return tree
        
        # Build refinement prompt
        prompt = self._build_refinement_prompt(tree, report, spec_text, iteration)
        
        try:
            response = self.client.chat(
                model=settings.mistral_chat_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,  # Slightly higher for creativity in fixes
                max_tokens=8000,
            )
            
            if response.choices and response.choices[0].message.content:
                json_str = response.choices[0].message.content
                refined_tree = TreeStructure.model_validate_json(json_str)
                return refined_tree
            else:
                return tree
                
        except Exception as e:
            print(f"LLM refinement failed: {e}")
            return tree
    
    def _build_refinement_prompt(self, tree: TreeStructure, report: TreeAnalysisReport,
                                  spec_text: str, iteration: int) -> str:
        """Build a prompt for the LLM to refine the tree."""
        errors = report.get_formatted_errors()
        warnings = "\n".join(
            f"- {i.message}" 
            for i in report.issues 
            if i.severity == Severity.WARNING
        )
        
        suggestions = "\n".join(
            f"- {s.description}" 
            for s in report.suggestions[:5]  # Limit to top 5
        )
        
        tree_json = json.dumps(tree.model_dump(), indent=2)
        
        return f"""You are an expert at fixing and improving decision trees for call-center agents.

TASK: Fix the issues in the following tree and improve its quality.

=== CURRENT TREE (iteration {iteration + 1}) ===
{tree_json}

=== ANALYSIS REPORT ===
{report.summary}

{errors}

{"WARNINGS:\n" + warnings if warnings else ""}

{"SUGGESTIONS:\n" + suggestions if suggestions else ""}

=== SPECIFICATION (for reference) ===
{spec_text[:4000]}...{f"\n\n[TRUNCATED: spec was {len(spec_text)} chars]" if len(spec_text) > 4000 else ""}

=== INSTRUCTIONS ===
1. Fix ALL errors listed above (they are marked as ERROR/❌)
2. Address warnings if they improve quality
3. Maintain the existing tree structure where possible
4. Keep node IDs consistent - only add new nodes, don't rename existing ones unless necessary
5. Ensure the tree still follows all rules:
   - root_id exists in nodes
   - All next_id references are valid
   - question nodes: >= 2 options
   - action nodes: exactly 1 option with label "Continue"
   - end nodes: 0 options
   - All paths terminate at end nodes
6. Return ONLY the corrected JSON tree. Do not include any explanation or text.
7. Use response_format={{type: "json_object"}}
"""
    
    def _calculate_confidence_score(self, report: TreeAnalysisReport) -> float:
        """Calculate an overall confidence score (0-1) for the tree."""
        if not report.metrics.node_count:
            return 0.0
        
        score = 1.0
        
        # Deduct for errors
        errors = [i for i in report.issues if i.severity == Severity.ERROR]
        warnings = [i for i in report.issues if i.severity == Severity.WARNING]
        
        score -= len(errors) * 0.2  # Each error reduces score by 20%
        score -= len(warnings) * 0.05  # Each warning reduces by 5%
        
        # Bonus for good metrics
        if report.metrics.end_nodes > 0:
            score += 0.05
        if report.metrics.max_depth <= 10:
            score += 0.05
        if report.coverage_score and report.coverage_score > 0.8:
            score += 0.1
        
        # Clamp to 0-1
        return max(0.0, min(1.0, score))
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def _find_similar_ids(self, target: str, candidates: list[str], max_results: int = 3) -> list[str]:
        """Find node IDs similar to target (edit distance)."""
        import difflib
        return difflib.get_close_matches(target, candidates, n=max_results, cutoff=0.6)
    
    def _extract_keywords(self, text: str) -> list[str]:
        """Extract significant keywords from text."""
        # Remove common words and extract nouns/verbs
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 
                     'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that'}
        
        words = re.findall(r'\b[a-z]{4,}\b', text.lower())
        return [w for w in words if w not in stopwords]
    
    def _tree_to_text(self, tree: TreeStructure) -> str:
        """Convert tree to plain text for analysis."""
        parts = []
        for node_id, node in tree.nodes.items():
            parts.append(node.label)
            parts.append(node.prompt)
            for opt in node.options:
                parts.append(opt.label)
        return " ".join(parts)


# =============================================================================
# Convenience Functions
# =============================================================================

analyzer = TreeAnalyzer()


def analyze_tree(tree: TreeStructure | dict, spec_text: str | None = None) -> TreeAnalysisReport:
    """Convenience function to analyze a tree."""
    return analyzer.analyze(tree, spec_text)


def refine_tree(tree: TreeStructure | dict, spec_text: str, 
                max_iterations: int = 3) -> tuple[TreeStructure, list[TreeAnalysisReport]]:
    """Convenience function to refine a tree."""
    return analyzer.refine(tree, spec_text, max_iterations)
