"""
Document Parser for Office Files
Uses Azure Mistral Document AI (mistral-document-ai-2505) for all document parsing
Falls back to traditional parsers if Azure Document AI is unavailable
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Optional
import warnings
warnings.filterwarnings('ignore')

# Try to import Azure Document AI parser
try:
    from parsers.azure_doc_parser import AzureDocumentParser
    HAS_AZURE_DOC_AI = True
except ImportError:
    HAS_AZURE_DOC_AI = False

# PDF parsing (fallback)
try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# PowerPoint parsing (fallback)
try:
    from pptx import Presentation
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

# Excel parsing (fallback)
try:
    import openpyxl
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

# Word parsing (fallback)
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


class DocumentParser:
    """Parse various document formats to extract text"""

    def __init__(self, config=None, use_azure_doc_ai=True):
        """
        Initialize document parser

        Args:
            config: Configuration object (optional, will use env vars if not provided)
            use_azure_doc_ai: Whether to use Azure Document AI (default: True)
        """
        self.config = config
        self.use_azure_doc_ai = use_azure_doc_ai and HAS_AZURE_DOC_AI
        self.azure_doc_parser = None

        # Initialize Azure Document AI if available and requested
        if self.use_azure_doc_ai:
            try:
                self.azure_doc_parser = AzureDocumentParser(config)
                print("✓ Using Azure Mistral Document AI for document parsing")
            except Exception as e:
                print(f"⚠ Failed to initialize Azure Document AI: {e}")
                print("  Falling back to traditional parsers")
                self.use_azure_doc_ai = False

        # Set up supported formats
        self.supported_formats = []
        if self.use_azure_doc_ai and self.azure_doc_parser:
            self.supported_formats = self.azure_doc_parser.supported_formats
        else:
            if HAS_PDF:
                self.supported_formats.append('.pdf')
            if HAS_PPTX:
                self.supported_formats.append('.pptx')
            if HAS_XLSX:
                self.supported_formats.extend(['.xlsx', '.xls', '.xlsm', '.xlsb'])
            if HAS_DOCX:
                self.supported_formats.append('.docx')

    def can_parse(self, file_path: str) -> bool:
        """Check if file format is supported"""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats

    def parse(self, file_path: str) -> Optional[Dict]:
        """
        Parse a document and return extracted text
        Uses Azure Mistral Document AI if available, falls back to traditional parsers

        Returns:
            Dict with 'content' and 'metadata' or None if parsing failed
        """
        if not os.path.exists(file_path):
            return None

        ext = Path(file_path).suffix.lower()

        # Try Azure Document AI first if available
        if self.use_azure_doc_ai and self.azure_doc_parser:
            try:
                return self.azure_doc_parser.parse(file_path)
            except Exception as e:
                print(f"  ⚠ Azure Document AI failed: {e}")
                print(f"  Falling back to traditional parser for {Path(file_path).name}")

        # Fall back to traditional parsers
        try:
            result = None
            if ext == '.pdf' and HAS_PDF:
                result = self._parse_pdf(file_path)
            elif ext == '.pptx' and HAS_PPTX:
                result = self._parse_pptx(file_path)
            elif ext in ('.xlsx', '.xls', '.xlsm', '.xlsb') and HAS_XLSX:
                result = self._parse_xlsx(file_path)
            elif ext == '.docx' and HAS_DOCX:
                result = self._parse_docx(file_path)

            # Sanitize content - remove NUL characters that break database storage
            if result and result.get('content'):
                result['content'] = result['content'].replace('\x00', '')

            return result
        except Exception as e:
            print(f"  ⚠ Error parsing {Path(file_path).name}: {e}")
            return None

        return None

    def parse_file_bytes(self, file_bytes: bytes, filename: str) -> Optional[str]:
        """
        Parse file bytes using Mistral Document AI (with local fallback).
        Saves bytes to temp file, calls self.parse(), returns content string.

        Args:
            file_bytes: Raw file content as bytes
            filename: Original filename (used to determine file type)

        Returns:
            Extracted text string, or None if parsing failed
        """
        ext = Path(filename).suffix.lower()
        if not ext:
            return None

        # Plain text files - decode directly
        if ext in ('.txt', '.md', '.csv', '.json', '.xml', '.html', '.htm'):
            try:
                return file_bytes.decode('utf-8', errors='ignore')
            except Exception:
                return None

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            result = self.parse(tmp_path)
            if result and result.get('content'):
                return result['content']
            return None
        except Exception as e:
            print(f"[DocumentParser] parse_file_bytes error for {filename}: {e}")
            return None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _parse_pdf(self, file_path: str) -> Dict:
        """Extract text from PDF"""
        text_parts = []

        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            num_pages = len(pdf_reader.pages)

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text and text.strip():
                    # Remove NUL characters that cause database issues
                    clean_text = text.replace('\x00', '').strip()
                    if clean_text:
                        text_parts.append(clean_text)

        content = '\n\n'.join(text_parts)
        # Final cleanup of any remaining NUL characters
        content = content.replace('\x00', '')

        return {
            'content': content,
            'metadata': {
                'pages': num_pages,
                'file_type': 'pdf'
            }
        }

    def _parse_pptx(self, file_path: str) -> Dict:
        """Extract text from PowerPoint"""
        text_parts = []

        prs = Presentation(file_path)

        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = []

            # Extract text from shapes
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text.strip())

            if slide_text:
                text_parts.append(f"[Slide {slide_num}]\n" + '\n'.join(slide_text))

        content = '\n\n'.join(text_parts)

        return {
            'content': content,
            'metadata': {
                'slides': len(prs.slides),
                'file_type': 'pptx'
            }
        }

    def _parse_xlsx(self, file_path: str) -> Dict:
        """Extract text from Excel files (.xlsx, .xls, .xlsm, .xlsb) with 10K row limit per sheet"""
        MAX_ROWS_PER_SHEET = 10000
        ext = Path(file_path).suffix.lower()

        # For .xls and .xlsb, use pandas (openpyxl can't read these)
        if ext in ('.xls', '.xlsb'):
            return self._parse_excel_pandas(file_path, MAX_ROWS_PER_SHEET)

        # For .xlsx and .xlsm, use openpyxl
        text_parts = []
        total_rows = 0
        truncated_sheets = []

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_text = [f"[Sheet: {sheet_name}]"]

            row_count = 0
            for row in sheet.iter_rows(values_only=True):
                if row_count >= MAX_ROWS_PER_SHEET:
                    truncated_sheets.append(sheet_name)
                    break

                row_values = [str(cell) for cell in row if cell is not None and str(cell).strip()]
                if row_values:
                    sheet_text.append(' | '.join(row_values))
                    row_count += 1

            if row_count > 0:
                text_parts.append('\n'.join(sheet_text))
                total_rows += row_count

        wb.close()

        if truncated_sheets:
            warning = f"\n\n[WARNING] The following sheets exceeded {MAX_ROWS_PER_SHEET:,} rows and were truncated: {', '.join(truncated_sheets)}"
            text_parts.append(warning)

        content = '\n\n'.join(text_parts)

        return {
            'content': content,
            'metadata': {
                'sheets': len(wb.sheetnames),
                'total_rows': total_rows,
                'truncated_sheets': truncated_sheets,
                'max_rows_per_sheet': MAX_ROWS_PER_SHEET,
                'file_type': ext.lstrip('.')
            }
        }

    def _parse_excel_pandas(self, file_path: str, max_rows: int) -> Dict:
        """Fallback Excel parser using pandas for .xls and .xlsb formats"""
        import pandas as pd

        text_parts = []
        total_rows = 0
        truncated_sheets = []

        try:
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names

            for sheet_name in sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=max_rows)
                if len(df) >= max_rows:
                    truncated_sheets.append(sheet_name)

                sheet_text = [f"[Sheet: {sheet_name}]"]
                for _, row in df.iterrows():
                    row_values = [str(v) for v in row if pd.notna(v) and str(v).strip()]
                    if row_values:
                        sheet_text.append(' | '.join(row_values))
                        total_rows += 1

                if len(sheet_text) > 1:
                    text_parts.append('\n'.join(sheet_text))

            xls.close()
        except Exception as e:
            print(f"[DocumentParser] pandas Excel parse error: {e}")
            return {'content': '', 'metadata': {'error': str(e), 'file_type': Path(file_path).suffix.lstrip('.')}}

        if truncated_sheets:
            warning = f"\n\n[WARNING] The following sheets exceeded {max_rows:,} rows and were truncated: {', '.join(truncated_sheets)}"
            text_parts.append(warning)

        content = '\n\n'.join(text_parts)

        return {
            'content': content,
            'metadata': {
                'sheets': len(sheet_names),
                'total_rows': total_rows,
                'truncated_sheets': truncated_sheets,
                'max_rows_per_sheet': max_rows,
                'file_type': Path(file_path).suffix.lstrip('.')
            }
        }

    def _parse_docx(self, file_path: str) -> Dict:
        """Extract text from Word document"""
        doc = Document(file_path)

        text_parts = []

        # Extract paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text.strip())

        # Extract tables
        for table in doc.tables:
            for row in table.rows:
                row_text = ' | '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)

        content = '\n\n'.join(text_parts)

        return {
            'content': content,
            'metadata': {
                'paragraphs': len(doc.paragraphs),
                'tables': len(doc.tables),
                'file_type': 'docx'
            }
        }

    def parse_pdf_bytes(self, content: bytes) -> str:
        """
        Extract text from PDF bytes (for file uploads)

        Args:
            content: PDF file content as bytes

        Returns:
            Extracted text string
        """
        import io

        # Try Azure Document AI first if available
        if HAS_AZURE_DOC_AI and self.azure_doc_parser:
            try:
                result = self.azure_doc_parser.parse_bytes(content, 'application/pdf')
                if result.get('success') and result.get('content'):
                    return result['content']
            except Exception as e:
                print(f"[DocumentParser] Azure Document AI failed, falling back to PyPDF2: {e}")

        # Fall back to PyPDF2
        if not HAS_PDF:
            raise Exception("PDF parsing not available. PyPDF2 is not installed.")

        text_parts = []
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            num_pages = len(pdf_reader.pages)

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if text and text.strip():
                    # Remove NUL characters that cause database issues
                    clean_text = text.replace('\x00', '').strip()
                    if clean_text:
                        text_parts.append(clean_text)

            result = '\n\n'.join(text_parts)
            # Final cleanup of any remaining NUL characters
            return result.replace('\x00', '')
        except Exception as e:
            raise Exception(f"Failed to parse PDF: {str(e)}")

    def parse_word_bytes(self, content: bytes) -> str:
        """
        Extract text from Word document bytes (for file uploads)

        Args:
            content: DOCX file content as bytes

        Returns:
            Extracted text string
        """
        import io

        # Try Azure Document AI first if available
        if HAS_AZURE_DOC_AI and self.azure_doc_parser:
            try:
                result = self.azure_doc_parser.parse_bytes(content, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
                if result.get('success') and result.get('content'):
                    return result['content']
            except Exception as e:
                print(f"[DocumentParser] Azure Document AI failed, falling back to python-docx: {e}")

        # Fall back to python-docx
        if not HAS_DOCX:
            raise Exception("Word document parsing not available. python-docx is not installed.")

        text_parts = []
        try:
            doc = Document(io.BytesIO(content))

            # Extract paragraphs
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text.strip())

            # Extract tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = ' | '.join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_text:
                        text_parts.append(row_text)

            return '\n\n'.join(text_parts)
        except Exception as e:
            raise Exception(f"Failed to parse Word document: {str(e)}")


if __name__ == "__main__":
    # Test the parser
    parser = DocumentParser()
    print(f"Supported formats: {parser.supported_formats}")

    # Test with a sample file
    test_file = "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-Timeline - BEAT Healthcare Consulting.pptx"
    if os.path.exists(test_file):
        result = parser.parse(test_file)
        if result:
            print(f"\nExtracted {len(result['content'])} characters")
            print(f"Preview: {result['content'][:200]}...")
