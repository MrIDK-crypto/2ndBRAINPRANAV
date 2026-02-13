"""
Enhanced Parser Comparison Tool v2
Better error handling and content display
"""

import os
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List

# Test documents
TEST_DOCS = [
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAssUk-kk/File-BEAT x UCLA Health Business Plan Presenta.pptx",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAssUk-kk/File-BEAT Charter Template.docx",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/DM 3TqrbcAAAAE/File-image(1).png",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAA9opKPFk/File-ED Encounter Data V2.xlsx",
    "/Users/rishitjain/Downloads/Takeout/Google Chat/Groups/Space AAAAn7sv4eE/File-BEAT Healthcare Consulting Project Charter(3).pdf"
]


def test_current_parser(file_path: str) -> Dict:
    """Test current parser"""
    try:
        from parsers.document_parser import DocumentParser
        parser = DocumentParser()
        result = parser.parse(file_path)
        if result:
            return {
                'success': True,
                'content': result['content'],
                'metadata': result['metadata'],
                'chars': len(result['content'])
            }
        return {'success': False, 'error': 'No content extracted', 'chars': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)[:100], 'chars': 0}


def test_unstructured(file_path: str) -> Dict:
    """Test Unstructured parser"""
    try:
        from unstructured.partition.auto import partition
        elements = partition(filename=file_path)
        content = "\n\n".join([str(el) for el in elements])
        return {
            'success': True,
            'content': content,
            'metadata': {
                'elements': len(elements),
                'types': list(set([type(el).__name__ for el in elements]))
            },
            'chars': len(content)
        }
    except Exception as e:
        error_msg = str(e).split('\n')[0][:100]  # First line only
        return {'success': False, 'error': error_msg, 'chars': 0}


def test_pymupdf(file_path: str) -> Dict:
    """Test PyMuPDF"""
    ext = Path(file_path).suffix.lower()
    if ext != '.pdf':
        return {'success': False, 'error': 'Only handles PDFs', 'chars': 0}

    try:
        import fitz
        doc = fitz.open(file_path)
        text_parts = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(text.strip())

        content = '\n\n'.join(text_parts)
        return {
            'success': True,
            'content': content,
            'metadata': {'pages': len(doc)},
            'chars': len(content)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)[:100], 'chars': 0}


def test_tesseract(file_path: str) -> Dict:
    """Test Tesseract OCR"""
    ext = Path(file_path).suffix.lower()
    if ext not in ['.png', '.jpg', '.jpeg']:
        return {'success': False, 'error': 'Only handles images', 'chars': 0}

    try:
        import pytesseract
        from PIL import Image

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)

        return {
            'success': True,
            'content': text,
            'metadata': {'size': image.size},
            'chars': len(text)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)[:100], 'chars': 0}


def run_comparison():
    """Run comparison and generate report"""

    print("\n" + "="*80)
    print("PARSER COMPARISON V2")
    print("="*80)

    results = []

    for doc_path in TEST_DOCS:
        if not os.path.exists(doc_path):
            print(f"\n⚠️  Skipping: {Path(doc_path).name} (not found)")
            continue

        print(f"\n📄 Testing: {Path(doc_path).name}")

        doc_result = {
            'file_name': Path(doc_path).name,
            'file_type': Path(doc_path).suffix,
            'parsers': {}
        }

        # Test each parser
        parsers = {
            'Current Parser': test_current_parser,
            'Unstructured': test_unstructured,
            'PyMuPDF': test_pymupdf,
            'Tesseract OCR': test_tesseract
        }

        for parser_name, parser_func in parsers.items():
            print(f"  Testing {parser_name}...", end=' ')
            start = time.time()
            result = parser_func(doc_path)
            duration = time.time() - start
            result['duration'] = duration

            if result['success']:
                print(f"✅ {result['chars']:,} chars in {duration:.2f}s")
            else:
                print(f"❌ {result.get('error', 'Failed')}")

            doc_result['parsers'][parser_name] = result

        results.append(doc_result)

    # Generate HTML
    generate_html_report(results)


def generate_html_report(results):
    """Generate clean HTML report"""

    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Parser Comparison Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }

        .container { max-width: 1600px; margin: 0 auto; }

        .header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }

        .header h1 { color: #667eea; font-size: 32px; margin-bottom: 10px; }
        .header .subtitle { color: #666; }

        .document-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }

        .document-card h2 { color: #333; margin-bottom: 15px; }

        .parsers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }

        .parser-box {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background: #fafafa;
            position: relative;
        }

        .parser-box.success { border-color: #4caf50; background: #f1f8f4; }
        .parser-box.error { border-color: #f44336; background: #fff3f3; }

        .parser-box h3 {
            color: #333;
            font-size: 16px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }

        .badge.success { background: #4caf50; color: white; }
        .badge.error { background: #f44336; color: white; }
        .badge.winner { background: gold; color: #333; }

        .stats {
            margin: 10px 0;
            font-size: 13px;
            color: #555;
        }

        .stats div { margin: 4px 0; }

        .content-preview {
            background: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 12px;
            margin-top: 10px;
            max-height: 250px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            white-space: pre-wrap;
            word-wrap: break-word;
            line-height: 1.4;
        }

        .error-msg {
            background: #ffebee;
            border: 1px solid #f44336;
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
            color: #c62828;
            font-size: 12px;
        }

        .summary-table {
            width: 100%;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            margin-bottom: 25px;
        }

        .summary-table table {
            width: 100%;
            border-collapse: collapse;
        }

        .summary-table th {
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }

        .summary-table td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }

        .summary-table tr:hover { background: #f5f5f5; }

        .chart-bar {
            background: linear-gradient(90deg, #4caf50, #81c784);
            height: 25px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: white;
            font-size: 12px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Parser Comparison Report v2</h1>
            <p class="subtitle">Generated on """ + datetime.now().strftime("%B %d, %Y at %I:%M %p") + """</p>
        </div>
"""

    # Summary table
    parser_stats = {}

    for doc in results:
        for parser_name, result in doc['parsers'].items():
            if parser_name not in parser_stats:
                parser_stats[parser_name] = {
                    'total_chars': 0,
                    'successes': 0,
                    'total': 0,
                    'total_time': 0
                }

            parser_stats[parser_name]['total'] += 1
            if result['success']:
                parser_stats[parser_name]['successes'] += 1
                parser_stats[parser_name]['total_chars'] += result['chars']
            parser_stats[parser_name]['total_time'] += result.get('duration', 0)

    # Sort by total chars
    sorted_parsers = sorted(
        parser_stats.items(),
        key=lambda x: x[1]['total_chars'],
        reverse=True
    )

    html += """
        <div class="summary-table">
            <table>
                <thead>
                    <tr>
                        <th>Parser</th>
                        <th>Success Rate</th>
                        <th>Total Characters</th>
                        <th>Avg Time</th>
                        <th>Performance</th>
                    </tr>
                </thead>
                <tbody>
"""

    max_chars = max([s[1]['total_chars'] for s in sorted_parsers]) if sorted_parsers else 1

    for parser_name, stats in sorted_parsers:
        success_rate = (stats['successes'] / stats['total'] * 100) if stats['total'] > 0 else 0
        avg_time = stats['total_time'] / stats['total'] if stats['total'] > 0 else 0
        bar_width = (stats['total_chars'] / max_chars * 100) if max_chars > 0 else 0

        html += f"""
                    <tr>
                        <td><strong>{parser_name}</strong></td>
                        <td>{success_rate:.0f}% ({stats['successes']}/{stats['total']})</td>
                        <td>{stats['total_chars']:,} chars</td>
                        <td>{avg_time:.2f}s</td>
                        <td>
                            <div class="chart-bar" style="width: {bar_width}%">
                                {stats['total_chars']:,}
                            </div>
                        </td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>
"""

    # Document cards
    for doc in results:
        # Find winner
        winner = None
        max_chars = 0
        for parser_name, result in doc['parsers'].items():
            if result['success'] and result['chars'] > max_chars:
                max_chars = result['chars']
                winner = parser_name

        html += f"""
        <div class="document-card">
            <h2>📄 {doc['file_name']}</h2>
            <p style="color: #888; font-size: 14px; margin-bottom: 10px;">File type: {doc['file_type']}</p>

            <div class="parsers-grid">
"""

        for parser_name, result in doc['parsers'].items():
            is_winner = (parser_name == winner)
            status_class = "success" if result['success'] else "error"

            html += f"""
                <div class="parser-box {status_class}">
                    <h3>
                        {parser_name}
                        <span class="badge {status_class}">
                            {'✅ SUCCESS' if result['success'] else '❌ FAILED'}
                        </span>
                        {f'<span class="badge winner">🏆 WINNER</span>' if is_winner else ''}
                    </h3>
"""

            if result['success']:
                html += f"""
                    <div class="stats">
                        <div><strong>Characters:</strong> {result['chars']:,}</div>
                        <div><strong>Duration:</strong> {result.get('duration', 0):.2f}s</div>
                        <div><strong>Metadata:</strong> {json.dumps(result.get('metadata', {}))}</div>
                    </div>
                    <div class="content-preview">{result.get('content', '')[:1500]}{('...' if result.get('chars', 0) > 1500 else '')}</div>
"""
            else:
                html += f"""
                    <div class="error-msg">
                        <strong>Error:</strong> {result.get('error', 'Unknown error')}
                    </div>
"""

            html += """
                </div>
"""

        html += """
            </div>
        </div>
"""

    html += """
    </div>
</body>
</html>
"""

    # Save
    output_path = "/Users/rishitjain/Downloads/knowledgevault_backend/parser_comparison_v2.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n✅ HTML report saved: {output_path}")
    print(f"\n🌐 Open in browser:")
    print(f"   file://{output_path}")

    return output_path


if __name__ == "__main__":
    run_comparison()
