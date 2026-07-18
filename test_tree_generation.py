#!/usr/bin/env python3
"""
Test script for tree generation from PDF.

This script tests the complete flow:
1. Extract text from PDF
2. Generate tree using Mistral LLM
3. Validate and display the tree

Note: This requires a Mistral API key to be set in the environment.
"""

import json
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Set up environment
os.environ['MISTRAL_API_KEY'] = os.getenv('MISTRAL_API_KEY', '')

from app.services.tree_generator import generate_tree


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pypdf."""
    from pypdf import PdfReader
    import io
    
    with open(pdf_path, 'rb') as f:
        content = f.read()
    
    reader = PdfReader(io.BytesIO(content))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n\n"
    return text.strip()


def main():
    pdf_path = 'test-data/Inbound Call Center — Agent Rule Set.pdf'
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found at: {pdf_path}")
        print("Please run from the repo root directory.")
        sys.exit(1)
    
    print("=" * 60)
    print("Testing Tree Generation from PDF")
    print("=" * 60)
    
    # Step 1: Extract text from PDF
    print("\n[1] Extracting text from PDF...")
    try:
        spec_text = extract_text_from_pdf(pdf_path)
        print(f"    Extracted {len(spec_text)} characters")
        print(f"    First 200 chars: {spec_text[:200]}...")
    except Exception as e:
        print(f"    ERROR: Failed to extract text: {e}")
        sys.exit(1)
    
    # Check if Mistral API key is available
    if not os.environ.get('MISTRAL_API_KEY'):
        print("\n[2] Mistral API key not found in environment.")
        print("    To test tree generation, set MISTRAL_API_KEY environment variable.")
        print("    For now, we'll just show what the service would do.")
        print("\n    The generate_tree function is ready and will:")
        print("    - Build a prompt for Mistral LLM")
        print("    - Call Mistral with response_format={'type': 'json_object'}")
        print("    - Parse and validate the JSON response")
        print("    - Post-validate the tree structure")
        print("    - Return a validated TreeStructure")
        print("\n[3] Example prompt structure:")
        from app.services.tree_generator import _build_prompt, _truncate_spec_text
        truncated = _truncate_spec_text(spec_text, 1000)
        prompt = _build_prompt(truncated)
        print(f"    Prompt length: {len(prompt)} characters")
        print(f"    First 500 chars: {prompt[:500]}...")
        
        print("\n[4] Example validation would check:")
        print("    - All node IDs are unique")
        print("    - root_id exists in nodes")
        print("    - All next_id references are valid")
        print("    - question nodes have >= 2 options")
        print("    - action nodes have exactly 1 option")
        print("    - end nodes have 0 options")
        print("    - All paths terminate at end nodes")
        print("    - No unreachable nodes")
        
        print("\n[5] Expected output format (TreeStructure):")
        print(json.dumps({
            "root_id": "n1",
            "nodes": {
                "n1": {
                    "id": "n1",
                    "type": "question",
                    "label": "Example question",
                    "prompt": "Ask: '...'",
                    "options": [
                        {"label": "Yes", "next_id": "n2"},
                        {"label": "No", "next_id": "n3"}
                    ]
                },
                "n2": {
                    "id": "n2",
                    "type": "end",
                    "label": "End",
                    "prompt": "...",
                    "options": []
                }
            }
        }, indent=2))
        
        print("\n" + "=" * 60)
        print("Test completed (without API call)")
        print("=" * 60)
        return
    
    # Step 2: Generate tree
    print("\n[2] Generating tree (this may take 10-30 seconds)...")
    try:
        tree = generate_tree(spec_text)
        print(f"    Generated tree with {len(tree.nodes)} nodes")
        print(f"    Root node: {tree.root_id}")
        
        # Display tree structure
        print("\n[3] Tree structure:")
        print(json.dumps(tree.model_dump(), indent=2))
        
        print("\n" + "=" * 60)
        print("Tree generation SUCCESS!")
        print("=" * 60)
        
    except ValueError as e:
        print(f"    ERROR: {e}")
        print("\n    This might be due to:")
        print("    - Mistral API key not valid")
        print("    - Network issues")
        print("    - LLM response not valid JSON")
        sys.exit(1)
    except Exception as e:
        print(f"    UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
