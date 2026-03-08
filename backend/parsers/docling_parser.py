"""
Docling Document Parser
Uses the docling library for local, free document parsing.
No API keys required — runs entirely on the local machine.
Supports: PDF, DOCX, PPTX, XLSX, HTML, images, and more.
"""

import os
from pathlib import Path
from typing import Dict, Optional
import warnings

warnings.filterwarnings('ignore')

try:
    from docling.document_converter import DocumentConverter
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False


class DoclingParser:
    """Parse documents locally using the docling library"""

    def __init__(self):
        if not HAS_DOCLING:
            raise ImportError(
                "docling not installed. Run: pip install docling"
            )

        self.converter = DocumentConverter()
        self.supported_formats = [
            '.pdf', '.docx', '.pptx', '.xlsx',
            '.html', '.htm',
            '.png', '.jpg', '.jpeg', '.tiff',
            '.txt', '.md'
        ]
        print("✓ Docling document parser initialized (local, no API)")

    def can_parse(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def parse(self, file_path: str) -> Optional[Dict]:
        """
        Parse a document using docling and return markdown output.

        Returns:
            Dict with 'content' and 'metadata' or None if parsing failed
        """
        if not os.path.exists(file_path):
            print(f"  ⚠ File not found: {file_path}")
            return None

        ext = Path(file_path).suffix.lower()
        if ext not in self.supported_formats:
            print(f"  ⚠ Unsupported format for docling: {ext}")
            return None

        file_name = Path(file_path).name

        try:
            print(f"  📄 Parsing {file_name} with docling (local)...")

            result = self.converter.convert(file_path)
            content = result.document.export_to_markdown()

            if not content or len(content.strip()) < 10:
                print(f"  ⚠ Docling returned insufficient content for {file_name}")
                return None

            # Remove NUL characters
            content = content.replace('\x00', '')

            return {
                'content': content,
                'raw_content': content,
                'metadata': {
                    'file_type': ext.lstrip('.'),
                    'file_name': file_name,
                    'total_chars': len(content),
                    'parser': 'docling',
                    'model': 'local'
                }
            }

        except Exception as e:
            print(f"  ✗ Docling failed to parse {file_name}: {e}")
            return None

    def parse_batch(self, file_paths: list) -> Dict[str, Optional[Dict]]:
        results = {}
        for file_path in file_paths:
            results[file_path] = self.parse(file_path)
        return results
