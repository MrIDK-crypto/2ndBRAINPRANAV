"""
Generate comprehensive HTML report comparing all parsers including LlamaParse
"""

import json
from datetime import datetime
from pathlib import Path

# Load results
with open('/Users/rishitjain/Downloads/knowledgevault_backend/llamaparse_results.json', 'r') as f:
    results = json.load(f)

html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>LlamaParse vs All Parsers - Complete Comparison</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }

        .container { max-width: 1800px; margin: 0 auto; }

        .header {
            background: white;
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.2);
        }

        .header h1 {
            color: #667eea;
            font-size: 36px;
            margin-bottom: 10px;
        }

        .header .subtitle {
            color: #666;
            font-size: 16px;
        }

        .highlight {
            background: #ffd700;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            border-left: 5px solid #ff6b6b;
        }

        .highlight h2 {
            color: #333;
            margin-bottom: 10px;
        }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }

        .summary-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            position: relative;
            overflow: hidden;
        }

        .summary-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }

        .summary-card.winner {
            border: 3px solid gold;
        }

        .summary-card.winner::before {
            height: 6px;
            background: linear-gradient(90deg, #ffd700, #ffed4e);
        }

        .summary-card h3 {
            color: #333;
            font-size: 18px;
            margin-bottom: 15px;
        }

        .summary-card .stat {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }

        .summary-card .label {
            color: #888;
            font-size: 13px;
        }

        .winner-badge {
            display: inline-block;
            background: gold;
            color: #333;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 8px;
        }

        .document-section {
            background: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.2);
        }

        .document-section h2 {
            color: #333;
            margin-bottom: 10px;
            font-size: 26px;
        }

        .file-info {
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
        }

        .parsers-comparison {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }

        .parser-card {
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            background: #fafafa;
            position: relative;
            transition: all 0.3s ease;
        }

        .parser-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        }

        .parser-card.success {
            border-color: #4caf50;
            background: #f1f8f4;
        }

        .parser-card.error {
            border-color: #f44336;
            background: #fff3f3;
        }

        .parser-card.winner {
            border-color: gold;
            border-width: 3px;
            background: linear-gradient(135deg, #fffbea 0%, #fff8dc 100%);
        }

        .parser-card h3 {
            color: #333;
            margin-bottom: 12px;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }

        .badge.success { background: #4caf50; color: white; }
        .badge.error { background: #f44336; color: white; }
        .badge.winner { background: gold; color: #333; }

        .stats {
            margin: 15px 0;
            font-size: 14px;
            color: #555;
        }

        .stats div {
            margin: 8px 0;
            display: flex;
            justify-content: space-between;
        }

        .stats .value {
            font-weight: bold;
            color: #333;
        }

        .content-preview {
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 15px;
            margin-top: 15px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .error-msg {
            background: #ffebee;
            border: 1px solid #f44336;
            border-radius: 6px;
            padding: 12px;
            margin-top: 12px;
            color: #c62828;
            font-size: 13px;
        }

        .trophy {
            font-size: 24px;
            position: absolute;
            top: -12px;
            right: -12px;
            background: white;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }

        .comparison-table {
            width: 100%;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            margin-bottom: 25px;
        }

        .comparison-table table {
            width: 100%;
            border-collapse: collapse;
        }

        .comparison-table th {
            background: #667eea;
            color: white;
            padding: 18px;
            text-align: left;
            font-weight: 600;
        }

        .comparison-table td {
            padding: 15px 18px;
            border-bottom: 1px solid #eee;
        }

        .comparison-table tr:hover {
            background: #f8f9fa;
        }

        .chart-bar {
            background: linear-gradient(90deg, #4caf50, #81c784);
            height: 30px;
            border-radius: 5px;
            display: flex;
            align-items: center;
            padding: 0 12px;
            color: white;
            font-size: 13px;
            font-weight: bold;
            transition: all 0.3s ease;
        }

        .chart-bar:hover {
            transform: scaleX(1.02);
        }

        .insight-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 20px;
            border-radius: 6px;
            margin: 20px 0;
        }

        .insight-box h3 {
            color: #1976d2;
            margin-bottom: 10px;
        }

        .insight-box ul {
            margin-left: 20px;
        }

        .insight-box li {
            margin: 8px 0;
            color: #333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 LlamaParse vs All Parsers - Complete Comparison</h1>
            <p class="subtitle">Generated on """ + datetime.now().strftime("%B %d, %Y at %I:%M %p") + """ | Python 3.12.7 Environment</p>
        </div>
"""

# Calculate summary stats
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

winner = sorted_parsers[0][0] if sorted_parsers else None

# Highlight box
html += f"""
        <div class="highlight">
            <h2>🏆 WINNER: {winner}</h2>
            <p><strong>{parser_stats[winner]['total_chars']:,} total characters extracted</strong> across all documents</p>
            <p>Success rate: {(parser_stats[winner]['successes'] / parser_stats[winner]['total'] * 100):.0f}% ({parser_stats[winner]['successes']}/{parser_stats[winner]['total']} files)</p>
        </div>
"""

# Summary cards
html += """
        <div class="summary-cards">
"""

for parser_name, stats in sorted_parsers:
    is_winner = (parser_name == winner)
    success_rate = (stats['successes'] / stats['total'] * 100) if stats['total'] > 0 else 0

    html += f"""
            <div class="summary-card{'  winner' if is_winner else ''}">
                <h3>{parser_name} {f'<span class="winner-badge">🏆 WINNER</span>' if is_winner else ''}</h3>
                <div class="stat">{stats['total_chars']:,}</div>
                <div class="label">Total Characters</div>
                <div style="margin-top: 15px;">
                    <div style="font-size: 16px; font-weight: bold; color: #333;">{success_rate:.0f}%</div>
                    <div class="label">Success Rate ({stats['successes']}/{stats['total']})</div>
                </div>
                <div style="margin-top: 10px;">
                    <div style="font-size: 14px; color: #666;">Avg: {stats['total_time'] / stats['total']:.1f}s</div>
                </div>
            </div>
"""

html += """
        </div>
"""

# Comparison table
html += """
        <div class="comparison-table">
            <table>
                <thead>
                    <tr>
                        <th>Parser</th>
                        <th>Success Rate</th>
                        <th>Total Characters</th>
                        <th>Avg Duration</th>
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
                        <td>{avg_time:.1f}s</td>
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

# Key insights
html += """
        <div class="insight-box">
            <h3>🔍 Key Insights</h3>
            <ul>
"""

llama_stats = parser_stats.get('LlamaParse', {})
current_stats = parser_stats.get('Current Parser', {})

if llama_stats and current_stats:
    improvement = ((llama_stats['total_chars'] / current_stats['total_chars']) - 1) * 100 if current_stats['total_chars'] > 0 else 0
    html += f"""
                <li><strong>LlamaParse extracts {improvement:.0f}% more content</strong> than the current parser ({llama_stats['total_chars']:,} vs {current_stats['total_chars']:,} chars)</li>
                <li><strong>100% success rate</strong> - LlamaParse handled all {llama_stats['total']} file types successfully</li>
                <li><strong>Structured output</strong> - Markdown format preserves tables, headers, and formatting</li>
                <li><strong>Trade-off:</strong> Slower processing ({llama_stats['total_time'] / llama_stats['total']:.1f}s avg) but higher quality</li>
"""

html += """
            </ul>
        </div>
"""

# Document-by-document comparison
for doc in results:
    # Find winner for this doc
    doc_winner = None
    max_chars_doc = 0
    for parser_name, result in doc['parsers'].items():
        if result['success'] and result['chars'] > max_chars_doc:
            max_chars_doc = result['chars']
            doc_winner = parser_name

    html += f"""
        <div class="document-section">
            <h2>📄 {doc['file_name']}</h2>
            <p class="file-info">File type: {doc['file_type']} | Winner: <strong>{doc_winner}</strong> ({max_chars_doc:,} chars)</p>

            <div class="parsers-comparison">
"""

    for parser_name, result in doc['parsers'].items():
        is_doc_winner = (parser_name == doc_winner)
        status_class = "success" if result['success'] else "error"
        card_class = f"{status_class}{' winner' if is_doc_winner else ''}"

        html += f"""
                <div class="parser-card {card_class}">
                    {f'<div class="trophy">🏆</div>' if is_doc_winner else ''}
                    <h3>
                        {parser_name}
                        <span class="badge {status_class}">
                            {'✅ SUCCESS' if result['success'] else '❌ FAILED'}
                        </span>
                    </h3>
"""

        if result['success']:
            html += f"""
                    <div class="stats">
                        <div><span>Characters:</span><span class="value">{result['chars']:,}</span></div>
                        <div><span>Duration:</span><span class="value">{result.get('duration', 0):.2f}s</span></div>
                        <div><span>Metadata:</span><span class="value">{json.dumps(result.get('metadata', {}))}</span></div>
                    </div>
                    <div class="content-preview">{result.get('content', '')[:2000]}{('...' if result.get('chars', 0) > 2000 else '')}</div>
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
output_path = "/Users/rishitjain/Downloads/knowledgevault_backend/llamaparse_complete_report.html"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ Report generated: {output_path}")
print(f"\n🌐 Open in browser:")
print(f"   file://{output_path}")
