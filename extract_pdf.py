#!/usr/bin/env python3
import pdfplumber
import sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else 'test-data/Inbound Call Center — Agent Rule Set.pdf'

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        print(f'=== Page {i+1} ===')
        text = page.extract_text()
        if text:
            print(text)
        print()
