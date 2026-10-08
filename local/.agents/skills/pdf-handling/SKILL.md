---
name: pdf-handling
description: Use when processing PDFs — extracting text, creating documents, filling forms, or merging/splitting files.
---

# PDF Handling

## When to Use This Skill
- Extracting text or tables from PDF documents
- Generating PDFs from HTML, Markdown, or structured data
- Filling in PDF form fields programmatically
- Merging multiple PDFs or splitting a PDF into pages

## Workflow
1. Install the library: `pnpm install PyMuPDF` or `pip install PyMuPDF` or `npm install pdf-lib`
2. For extraction: open the PDF and iterate over pages, extracting text blocks
3. For creation: build the PDF from HTML with WeasyPrint or from layout with pdf-lib
4. For forms: read existing fields, fill values, and flatten if needed
5. For merging: concatenate page arrays from multiple PDFs
6. For splitting: extract page ranges and save as new PDFs
7. Test output in multiple PDF viewers

## Rules
- Preserve text encoding — handle unicode correctly
- Don't modify signed PDFs — signature validation will fail
- Use vector graphics when possible, not rasterized text
- Handle password-protected PDFs gracefully — report the error, don't guess
- Test with both text-heavy and image-heavy PDFs
- Respect PDF/A compliance if archiving documents
