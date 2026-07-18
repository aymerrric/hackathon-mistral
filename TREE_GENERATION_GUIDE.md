# Guide: PDF to Decision Tree Generation

This document explains the implementation of the **PDF to Decision Tree** workflow for the CallTree project.

## Overview

The system transforms call center procedure documents (PDF, text, markdown) into structured decision trees that can be:
- **Visualized** in an interactive interface
- **Used for guidance** during live calls
- **Used for auditing** recorded calls against the expected flow

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   PDF/Text      │────▶│ Extract Text     │────▶│ Generate Tree    │
│   Document      │     │ (pypdf, UTF-8)    │     │ (Mistral LLM)    │
└─────────────────┘     └──────────────────┘     └──────────────────┘
                                                          │
                                                          ▼
                     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
                     │ Validate &       │────▶│ Store in DB      │────▶│ Visualize       │
                     │ Post-process     │     │ (PostgreSQL)      │     │ (SVG/HTML)       │
                     └──────────────────┘     └──────────────────┘     └──────────────────┘
```

## Components Implemented

### 1. Backend Service (`backend/app/services/tree_generator.py`)

The core service that:
- Takes plain text from spec documents
- Builds a structured prompt for Mistral LLM
- Calls Mistral with `response_format={"type": "json_object"}`
- Parses and validates the JSON response
- Post-validates the tree structure (checks references, removes orphan nodes, ensures all paths terminate)
- Implements retry logic with error feedback

**Key Functions:**
- `generate_tree(spec_text: str) -> TreeStructure` - Main entry point
- `_build_prompt(spec_text: str) -> str` - Constructs the LLM prompt
- `_validate_tree_structure(tree: TreeStructure) -> TreeStructure` - Post-processing validation
- `_truncate_spec_text(text: str, max_length: int) -> str` - Handles large documents

### 2. API Endpoints

#### Specs Router (`backend/app/routers/specs.py`)
- `POST /api/specs` - Upload a spec document (PDF, txt, md) and extract text
- `GET /api/specs` - List all uploaded specs
- `POST /api/specs/{spec_id}/generate-tree` - Generate a decision tree from a spec

#### Trees Router (`backend/app/routers/trees.py`)
- `GET /api/trees` - List all generated trees
- `GET /api/trees/{tree_id}` - Get a specific tree
- `PUT /api/trees/{tree_id}` - Save a manually corrected tree as a new version

### 3. Data Models

**TreeStructure (from `backend/app/schemas.py`):**
```python
{
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1",
            "type": "question" | "action" | "end",  # Node type
            "label": "Short title",                   # Display label
            "prompt": "Exact wording to say/ask",     # Agent script
            "options": [                              # Branches
                {"label": "Option text", "next_id": "n2"},
                ...
            ]
        },
        ...
    }
}
```

**Rules:**
- `question` nodes: >= 2 options
- `action` nodes: exactly 1 option (label should be "Continue")
- `end` nodes: 0 options
- All `next_id` must reference existing nodes
- All paths must terminate at an `end` node
- No cycles allowed

### 4. Visualization (`visualize_tree.html`)

A standalone HTML/JavaScript visualizer that:
- Loads tree JSON files
- Displays an example tree based on the call center rule set
- Supports two layout modes: **Hierarchical** (tree structure) and **Force-directed** (organic layout)
- Shows node details on click
- Color-codes nodes by type (blue=question, green=action, red=end)
- Allows toggling between layouts

## Usage

### 1. Set Up Environment

```bash
# Install dependencies
cd backend
poetry install

# Set your Mistral API key
cp .env.example .env
# Edit .env and add your MISTRAL_API_KEY
```

### 2. Start Services

```bash
# Start database
docker compose up -d db

# Start backend
poetry run uvicorn app.main:app --reload --port 8000
```

### 3. Upload and Generate

```bash
# Upload a spec document
curl -X POST -F "name=Call Center Rules" -F "file=@../../test-data/Inbound Call Center — Agent Rule Set.pdf" \
  http://localhost:8000/api/specs

# Generate tree from spec (use the returned spec_id)
curl -X POST http://localhost:8000/api/specs/{spec_id}/generate-tree
```

### 4. Visualize the Tree

Open `visualize_tree.html` in a browser:
- Click "Load Example Tree" to see a sample call center workflow
- Or upload your own tree JSON file
- Toggle between hierarchical and force-directed layouts
- Click on nodes to see full details

### 5. Test the Flow

Run the test script to verify the complete pipeline:

```bash
# Test PDF extraction and prompt generation (no API call needed)
python test_tree_generation.py
```

This will:
- Extract text from the test PDF
- Show the prompt structure
- Display example validation rules
- Show the expected output format

## Prompt Engineering

The prompt sent to Mistral includes:

1. **Role Definition**: "You are an expert at converting call-handling procedure documents into strict decision trees..."

2. **JSON Contract**: The exact TreeStructure schema with all required fields

3. **Rules**:
   - Node ID format (n1, n2, ...)
   - root_id must exist in nodes
   - question nodes: >= 2 options
   - action nodes: exactly 1 option
   - end nodes: 0 options
   - All next_id must reference existing nodes
   - All paths must terminate
   - Prompt fields must use exact wording from the spec
   - Aim for 10-40 nodes

4. **Example**: A complete, valid tree example

5. **Document**: The spec text to convert

6. **Instructions**: "Return ONLY the JSON object..."

## Post-Processing Validation

The service performs comprehensive validation:

1. **Root Check**: Verifies root_id exists in nodes
2. **Reference Check**: Ensures all next_id point to existing nodes
3. **Reachability**: Removes unreachable nodes (orphans)
4. **Node Type Rules**: Validates option counts based on type
5. **Cycle Detection**: DFS to detect and prevent cycles
6. **Termination Check**: Ensures all paths reach an end node

## Example Output

See `example_tree_output.json` for a manually-created tree based on the call center rule set. This demonstrates:

- The complete call flow from greeting to close
- Identity verification branch
- Issue categorization (6 different issue types)
- Escalation paths for each issue type
- De-escalation framework for complaints
- Legal/security immediate escalation
- Proper termination at end nodes

## Visualization Features

The `visualize_tree.html` provides:

- **Hierarchical Layout**: Traditional tree view with nodes arranged by level
- **Force-Directed Layout**: Organic layout using physics simulation
- **Node Details Panel**: Shows full node information on click
- **Node Highlighting**: Selected node is highlighted in blue
- **Color Coding**:
  - Blue: Question nodes (decision points)
  - Green: Action nodes (agent actions)
  - Red: End nodes (termination points)
- **Interactive**: Click on any node to see its details

## Integration with Frontend

The frontend (Next.js) can:

1. Upload spec documents via `/api/specs`
2. Trigger tree generation via `/api/specs/{id}/generate-tree`
3. Display the generated tree using the TreeStructure JSON
4. Render the tree using a component similar to the visualization logic
5. Guide agents through the tree during calls (sessions)
6. Audit recorded calls against the tree (analysis)

## Dependencies

- `mistralai` - Mistral API client
- `pypdf` - PDF text extraction
- `pydantic` - Data validation
- `fastapi` - Web framework
- `sqlalchemy` - Database ORM

## Performance Considerations

- Documents are truncated to ~30,000 characters
- Mistral API calls take ~10-30 seconds
- Generation is synchronous (hackathon constraint)
- Frontend should show a loading spinner during generation
- For production, consider async generation with task queue

## Error Handling

- First attempt: Generate tree with original prompt
- On failure: Retry with error message fed back to LLM
- Second failure: Raise ValueError with combined error messages
- Router maps ValueError to HTTP 502 (Bad Gateway)

## Future Enhancements

1. **Better PDF Extraction**: Handle complex layouts, tables, images
2. **Chunking**: Process very large documents in chunks
3. **Caching**: Cache generated trees to avoid regeneration
4. **Fine-tuning**: Use a fine-tuned model for better tree generation
5. **Interactive Editing**: Allow editing trees in the UI
6. **Version Comparison**: Visual diff between tree versions
7. **Metrics**: Track tree generation quality and success rates
8. **Fallback**: Use rule-based generation if LLM fails

## Testing

The system can be tested at multiple levels:

1. **Unit Tests**: Test individual functions (prompt building, validation)
2. **Integration Tests**: Test the complete flow from PDF to tree
3. **Manual Testing**: Use the provided HTML visualizer
4. **API Testing**: Use curl or Postman to test endpoints

Example test cases:
- Simple linear flow
- Complex branching tree
- Invalid PDF (empty, corrupted)
- Large document (>30k characters)
- Document with cycles (should be detected and rejected)
