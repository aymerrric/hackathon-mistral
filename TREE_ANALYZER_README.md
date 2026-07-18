# Tree Analyzer Tool

A comprehensive tool for analyzing, validating, and refining decision trees produced by the CallTree system.

## Features

### 1. **Deep Analysis**
- **Structural Validation**: Checks all node references, types, and constraints
  - Missing root node detection
  - Invalid next_id references (with "did you mean?" suggestions)
  - Node type validation (question: >=2 options, action: exactly 1, end: 0)
  - Duplicate node IDs
  - Duplicate option labels

- **Path Validation**: Ensures all paths through the tree are valid
  - Cycle detection (with path visualization)
  - Unreachable node detection
  - Path-to-end validation (all paths must terminate at end nodes)
  - Path length analysis

- **Node Quality Checks**: Identifies potential issues with node content
  - Weak/placeholder labels ("TBD", "TODO", etc.)
  - Missing or too-short prompts
  - Duplicate labels across nodes
  - Long labels (>8 words)
  - Weak option labels

- **Tree Metrics**: Calculates quantitative metrics
  - Node counts (total, by type)
  - Edge count
  - Tree depth (average and maximum)
  - Branching factor
  - Path counts and lengths
  - Unreachable node count

- **Spec Coverage Analysis**: Measures how well the tree covers the source specification
  - Keyword-based coverage scoring
  - Identification of missing concepts

### 2. **Automatic Fix Suggestions**
For each identified issue, the tool suggests concrete fixes:
- Create missing nodes
- Remove unreachable nodes
- Rename duplicate IDs
- Fix invalid references (with similar node suggestions)
- Add required options
- Add missing end nodes
- Proactive improvements (metadata, structure, etc.)

### 3. **LLM-Powered Refinement**
- Iterative tree improvement using Mistral LLM
- Multi-stage refinement with analysis feedback
- Maintains tree structure where possible
- Up to N iterations (configurable)
- Returns all intermediate analysis reports

### 4. **Confidence Scoring**
- Overall tree quality score (0-100%)
- Based on error count, warning count, and metrics
- Coverage score for spec-based analysis

## Installation

The tool is part of the backend service. No additional installation required beyond the existing dependencies.

## Usage

### CLI Tool

```bash
# Analyze a tree
python backend/scripts/analyze_tree.py analyze <tree_json_file> [--spec <spec_file>] [--verbose] [--output <report_file>]

# Refine a tree with LLM (requires MISTRAL_API_KEY)
python backend/scripts/analyze_tree.py refine <tree_json_file> <spec_file> [--iterations N] [--output <output_tree>]

# Interactive mode for fixing issues
python backend/scripts/analyze_tree.py interact <tree_json_file> [--spec <spec_file>] [--output <output_tree>]
```

**Examples:**
```bash
# Analyze a valid tree
python backend/scripts/analyze_tree.py analyze test-data/sample_tree_valid.json

# Analyze with spec for coverage
python backend/scripts/analyze_tree.py analyze test-data/sample_tree_valid.json --spec test-data/sample_spec.txt

# Refine an invalid tree
MISTRAL_API_KEY=your_key python backend/scripts/analyze_tree.py refine test-data/sample_tree_invalid.json test-data/sample_spec.txt --iterations 3 --output fixed_tree.json

# Interactive editing
python backend/scripts/analyze_tree.py interact test-data/sample_tree_invalid.json
```

### API Endpoints

All endpoints are under `/api/analysis`:

#### POST `/api/analysis/analyze`
Analyze a tree structure.

**Request:**
```json
{
  "tree": { ... TreeStructure JSON ... },
  "spec_text": "Optional spec text for coverage analysis"
}
```

**Response:**
```json
{
  "tree_id": null,
  "is_valid": true/false,
  "issues": [...],
  "metrics": { ... },
  "suggestions": [...],
  "coverage_score": 0.85,
  "confidence_score": 0.95,
  "summary": "Tree Analysis: ✓ VALID ..."
}
```

#### POST `/api/analysis/analyze/{tree_id}`
Analyze an existing tree from the database.

**Query Params:**
- `spec_id`: Optional spec ID for coverage analysis

#### POST `/api/analysis/refine`
Refine a tree using LLM.

**Request:**
```json
{
  "tree": { ... TreeStructure JSON ... },
  "spec_text": "Source specification text",
  "max_iterations": 3
}
```

**Response:**
```json
{
  "final_tree": { ... refined TreeStructure ... },
  "reports": [ ... analysis reports from each iteration ... ],
  "iteration_count": 3,
  "success": true/false
}
```

#### POST `/api/analysis/refine/{tree_id}`
Refine an existing tree from the database.

#### POST `/api/analysis/validate`
Quick validation - returns only errors.

**Request:**
```json
{ "tree": { ... TreeStructure JSON ... } }
```

**Response:**
```json
{
  "is_valid": true/false,
  "errors": [...],
  "error_count": N
}
```

#### GET `/api/analysis/health`
Health check endpoint.

## Python API

```python
from app.services.tree_analyzer import (
    TreeAnalyzer,
    analyze_tree,
    refine_tree,
    TreeAnalysisReport,
    Severity
)

# Create analyzer (optionally with custom Mistral client)
analyzer = TreeAnalyzer()

# Analyze a tree
tree = { "root_id": "n1", "nodes": { ... } }
report = analyzer.analyze(tree, spec_text="...")

print(report.is_valid)
print(report.get_summary())
for issue in report.issues:
    if issue.severity == Severity.ERROR:
        print(f"ERROR: {issue.message}")

# Get fix suggestions
fixes = analyzer.suggest_fixes(report)

# Refine a tree iteratively
final_tree, reports = analyzer.refine(tree, spec_text, max_iterations=3)
```

## Error Codes

| Code | Severity | Description |
|------|----------|-------------|
| `MISSING_ROOT` | ERROR | Root node doesn't exist in nodes |
| `INVALID_REFERENCE` | ERROR | Option references non-existent node |
| `DUPLICATE_NODE_ID` | ERROR | Node ID appears multiple times |
| `DUPLICATE_OPTION_LABEL` | ERROR | Same option label in one node |
| `QUESTION_NEEDS_OPTIONS` | ERROR | Question node has < 2 options |
| `ACTION_NEEDS_ONE_OPTION` | ERROR | Action node doesn't have exactly 1 option |
| `END_NEEDS_NO_OPTIONS` | ERROR | End node has options |
| `NO_PATHS_TO_END` | ERROR | No valid paths to end nodes |
| `CYCLE_DETECTED` | ERROR | Circular reference detected |
| `WEAK_LABEL` | WARNING | Label is placeholder or unclear |
| `LONG_LABEL` | INFO | Label exceeds recommended length |
| `MISSING_PROMPT` | WARNING | Prompt is missing or too short |
| `DUPLICATE_LABEL` | WARNING | Label duplicated across nodes |
| `WEAK_OPTION_LABEL` | WARNING | Option label is unclear |
| `UNREACHABLE_NODE` | WARNING | Node is not reachable from root |
| `LOW_COVERAGE` | WARNING | Tree doesn't cover spec sufficiently |
| `LONG_PATH` | INFO | Path exceeds recommended length |

## Interactive Mode Features

The interactive CLI provides a menu-driven interface:

1. **Apply automatic fixes** - Automatically apply suggested fixes
2. **Edit tree manually** - Edit the tree JSON directly
3. **Refine with LLM** - Use Mistral LLM to improve the tree (requires API key)
4. **Show detailed issue** - View full details of a specific issue
5. **Save and exit** - Save changes and exit
6. **Exit without saving** - Discard changes and exit

## Files Created

- `backend/app/services/tree_analyzer.py` - Core analysis and refinement service
- `backend/app/routers/tree_analysis.py` - API endpoints
- `backend/scripts/analyze_tree.py` - CLI tool
- `test_tree_analyzer.py` - Test suite
- `test-data/sample_tree_valid.json` - Sample valid tree
- `test-data/sample_tree_invalid.json` - Sample invalid tree
- `test-data/sample_spec.txt` - Sample specification

## Integration with Existing Code

The analyzer integrates seamlessly with the existing tree generation workflow:

```python
from app.services.tree_generator import generate_tree
from app.services.tree_analyzer import refine_tree

# Generate initial tree
spec_text = "..."
tree = generate_tree(spec_text)

# Refine it
final_tree, reports = refine_tree(tree, spec_text, max_iterations=3)

# All reports show the improvement over iterations
for i, report in enumerate(reports):
    print(f"Iteration {i+1}: {report.confidence_score:.0%} confidence")
```

## Configuration

The tool uses the existing `MISTRAL_API_KEY` configuration from `app/config.py`.

## Testing

Run the test suite:
```bash
python test_tree_analyzer.py
```

All 9 tests should pass.
