"""
LlamaParse Test Script - Uses Python 3.12 Environment
Tests LlamaParse on all document types and compares with other parsers
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime

# Set API key
os.environ.setdefault('LLAMA_CLOUD_API_KEY', os.getenv('LLAMA_CLOUD_API_KEY', ''))

# Test documents
TEST_DOCS = [
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAssUk-kk/File-BEAT x UCLA Health Business Plan Presenta.pptx",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAssUk-kk/File-BEAT Charter Template.docx",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/DM 3TqrbcAAAAE/File-image(1).png",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAA9opKPFk/File-ED Encounter Data V2.xlsx",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-BEAT Healthcare Consulting Project Charter(3).pdf"
]


def test_llamaparse(file_path: str):
    """Test LlamaParse on a file"""
    from llama_parse import LlamaParse

    print(f"  Testing LlamaParse... ", end='', flush=True)

    try:
        start = time.time()

        parser = LlamaParse(
            api_key=os.environ['LLAMA_CLOUD_API_KEY'],
            result_type="markdown",
            verbose=False
        )

        documents = parser.load_data(file_path)
        content = "\n\n".join([doc.text for doc in documents])

        duration = time.time() - start
        chars = len(content)

        print(f"✅ {chars:,} chars in {duration:.2f}s")

        return {
            'success': True,
            'content': content,
            'chars': chars,
            'duration': duration,
            'metadata': {
                'num_documents': len(documents),
                'format': 'markdown'
            }
        }
    except Exception as e:
        duration = time.time() - start
        error_msg = str(e).split('\n')[0][:150]
        print(f"❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'chars': 0,
            'duration': duration
        }


def test_current_parser(file_path: str):
    """Test current parser"""
    import sys
    sys.path.insert(0, '/Users/rishitjain/Downloads/knowledgevault_backend')

    from parsers.document_parser import DocumentParser

    print(f"  Testing Current Parser... ", end='', flush=True)

    try:
        start = time.time()
        parser = DocumentParser()
        result = parser.parse(file_path)
        duration = time.time() - start

        if result:
            chars = len(result['content'])
            print(f"✅ {chars:,} chars in {duration:.2f}s")
            return {
                'success': True,
                'content': result['content'],
                'chars': chars,
                'duration': duration,
                'metadata': result['metadata']
            }
        else:
            print(f"⚠️  No content")
            return {'success': False, 'error': 'No content', 'chars': 0, 'duration': duration}
    except Exception as e:
        duration = time.time() - start
        print(f"❌ {str(e)[:50]}")
        return {'success': False, 'error': str(e)[:100], 'chars': 0, 'duration': duration}


def test_unstructured(file_path: str):
    """Test Unstructured parser"""
    from unstructured.partition.auto import partition

    print(f"  Testing Unstructured... ", end='', flush=True)

    try:
        start = time.time()
        elements = partition(filename=file_path)
        content = "\n\n".join([str(el) for el in elements])
        duration = time.time() - start

        chars = len(content)
        print(f"✅ {chars:,} chars in {duration:.2f}s")

        return {
            'success': True,
            'content': content,
            'chars': chars,
            'duration': duration,
            'metadata': {'elements': len(elements)}
        }
    except Exception as e:
        duration = time.time() - start
        error_msg = str(e).split('\n')[0][:100]
        print(f"❌ {error_msg}")
        return {'success': False, 'error': error_msg, 'chars': 0, 'duration': duration}


def test_pymupdf(file_path: str):
    """Test PyMuPDF"""
    import fitz

    ext = Path(file_path).suffix.lower()
    if ext != '.pdf':
        print(f"  Testing PyMuPDF... ⚠️  Only handles PDFs")
        return {'success': False, 'error': 'Only handles PDFs', 'chars': 0, 'duration': 0}

    print(f"  Testing PyMuPDF... ", end='', flush=True)

    try:
        start = time.time()
        doc = fitz.open(file_path)
        text_parts = []

        for page in doc:
            text = page.get_text()
            if text.strip():
                text_parts.append(text.strip())

        content = '\n\n'.join(text_parts)
        duration = time.time() - start

        chars = len(content)
        print(f"✅ {chars:,} chars in {duration:.2f}s")

        return {
            'success': True,
            'content': content,
            'chars': chars,
            'duration': duration,
            'metadata': {'pages': len(doc)}
        }
    except Exception as e:
        duration = time.time() - start
        print(f"❌ {str(e)[:50]}")
        return {'success': False, 'error': str(e)[:100], 'chars': 0, 'duration': duration}


def test_tesseract(file_path: str):
    """Test Tesseract OCR"""
    import pytesseract
    from PIL import Image

    ext = Path(file_path).suffix.lower()
    if ext not in ['.png', '.jpg', '.jpeg']:
        print(f"  Testing Tesseract OCR... ⚠️  Only handles images")
        return {'success': False, 'error': 'Only handles images', 'chars': 0, 'duration': 0}

    print(f"  Testing Tesseract OCR... ", end='', flush=True)

    try:
        start = time.time()
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        duration = time.time() - start

        chars = len(text)
        print(f"✅ {chars:,} chars in {duration:.2f}s")

        return {
            'success': True,
            'content': text,
            'chars': chars,
            'duration': duration,
            'metadata': {'size': image.size}
        }
    except Exception as e:
        duration = time.time() - start
        print(f"❌ {str(e)[:50]}")
        return {'success': False, 'error': str(e)[:100], 'chars': 0, 'duration': duration}


def main():
    """Run comprehensive comparison"""

    print("\n" + "="*80)
    print("COMPREHENSIVE PARSER COMPARISON - WITH LLAMAPARSE!")
    print("="*80)
    print(f"Python version: {os.sys.version}")
    print(f"Running from: {os.getcwd()}")
    print("="*80 + "\n")

    results = []

    for doc_path in TEST_DOCS:
        if not os.path.exists(doc_path):
            print(f"⚠️  File not found: {Path(doc_path).name}\n")
            continue

        print(f"📄 {Path(doc_path).name}")
        print(f"   Type: {Path(doc_path).suffix}")

        doc_result = {
            'file_name': Path(doc_path).name,
            'file_type': Path(doc_path).suffix,
            'file_path': doc_path,
            'parsers': {}
        }

        # Test all parsers
        doc_result['parsers']['LlamaParse'] = test_llamaparse(doc_path)
        doc_result['parsers']['Current Parser'] = test_current_parser(doc_path)
        doc_result['parsers']['Unstructured'] = test_unstructured(doc_path)
        doc_result['parsers']['PyMuPDF'] = test_pymupdf(doc_path)
        doc_result['parsers']['Tesseract OCR'] = test_tesseract(doc_path)

        results.append(doc_result)
        print()

    # Save results
    output_file = '/Users/rishitjain/Downloads/knowledgevault_backend/llamaparse_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print("="*80)
    print("SUMMARY")
    print("="*80)

    # Calculate totals
    parser_totals = {}
    for doc in results:
        for parser_name, result in doc['parsers'].items():
            if parser_name not in parser_totals:
                parser_totals[parser_name] = {
                    'total_chars': 0,
                    'successes': 0,
                    'total': 0
                }

            parser_totals[parser_name]['total'] += 1
            if result['success']:
                parser_totals[parser_name]['successes'] += 1
                parser_totals[parser_name]['total_chars'] += result['chars']

    # Print summary
    print(f"\n{'Parser':<20} {'Success Rate':<15} {'Total Characters':<20}")
    print("-" * 60)

    for parser_name in ['LlamaParse', 'Current Parser', 'Unstructured', 'PyMuPDF', 'Tesseract OCR']:
        stats = parser_totals[parser_name]
        success_rate = (stats['successes'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{parser_name:<20} {success_rate:>5.0f}% ({stats['successes']}/{stats['total']}){' ':<5} {stats['total_chars']:>15,} chars")

    print("\n" + "="*80)
    print(f"✅ Results saved to: {output_file}")
    print("="*80 + "\n")

    return results


if __name__ == "__main__":
    main()
