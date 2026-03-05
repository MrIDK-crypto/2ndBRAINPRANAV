"""
Enhanced Code-Aware Gap Detector for GitHub Repository Analysis

Multi-layered analysis:
1. Regex-based pattern matching (fast, broad coverage)
2. AST-based analysis (accurate, Python-specific)
3. LLM-enhanced analysis (deep semantic understanding)
"""

import re
import ast
import json
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict


# =============================================================================
# MAIN ENTRY POINTS
# =============================================================================

def analyze_code_gaps(documents: List[Dict], max_gaps_per_category: int = 8) -> Dict[str, Any]:
    """
    Analyze GitHub code documents using multi-layered analysis.

    Layers:
    1. Regex patterns - security, TODOs, config values
    2. AST analysis - complexity, type hints, unused code (Python only)
    3. Cross-file analysis - missing tests, architectural patterns
    """
    github_docs = [d for d in documents if d.get('source_type') == 'github']

    if not github_docs:
        return {'gaps': [], 'total_gaps': 0, 'gaps_by_category': {}, 'documents_analyzed': 0}

    all_gaps = []

    for doc in github_docs:
        content = doc.get('content', '')
        title = doc.get('title', '')
        metadata = doc.get('metadata') or doc.get('doc_metadata') or {}
        file_path = metadata.get('file_path') or title

        # Determine file type
        is_python = file_path.endswith('.py')
        is_javascript = file_path.endswith(('.js', '.jsx', '.ts', '.tsx'))

        # Layer 1: Regex-based analysis (all languages)
        all_gaps.extend(_analyze_todos(content, file_path))
        all_gaps.extend(_analyze_security_regex(content, file_path))
        all_gaps.extend(_analyze_error_handling_regex(content, file_path))
        all_gaps.extend(_analyze_api_endpoints(content, file_path))
        all_gaps.extend(_analyze_config_values(content, file_path))
        all_gaps.extend(_analyze_code_quality_regex(content, file_path))

        # Layer 2: AST-based analysis (Python only)
        if is_python:
            all_gaps.extend(_analyze_python_ast(content, file_path))

        # Layer 2b: JavaScript/TypeScript patterns
        if is_javascript:
            all_gaps.extend(_analyze_javascript_patterns(content, file_path))

    # Cross-file analysis
    all_gaps.extend(_analyze_testing(github_docs))
    all_gaps.extend(_analyze_architecture_patterns(github_docs))

    # Count by category
    stats = defaultdict(int)
    for gap in all_gaps:
        stats[gap['category']] += 1

    # Deduplicate similar gaps
    all_gaps = _deduplicate_gaps(all_gaps)

    # Limit per category
    limited = []
    cat_counts = defaultdict(int)
    for gap in all_gaps:
        if cat_counts[gap['category']] < max_gaps_per_category:
            limited.append(gap)
            cat_counts[gap['category']] += 1

    # Sort by priority
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    limited.sort(key=lambda g: priority_order.get(g['priority'], 4))

    return {
        'gaps': limited,
        'total_gaps': len(all_gaps),
        'gaps_by_category': dict(stats),
        'documents_analyzed': len(github_docs),
        'analysis_layers': ['regex', 'ast', 'cross-file']
    }


def analyze_code_gaps_with_llm(
    documents: List[Dict],
    max_gaps_per_category: int = 8,
    use_llm: bool = True
) -> Dict[str, Any]:
    """
    Full analysis including LLM-enhanced deep analysis.

    Args:
        documents: Code documents to analyze
        max_gaps_per_category: Max gaps per category
        use_llm: Whether to use LLM for deep analysis (costs API calls)
    """
    # First run standard analysis
    result = analyze_code_gaps(documents, max_gaps_per_category)

    if not use_llm:
        return result

    github_docs = [d for d in documents if d.get('source_type') == 'github']

    # Layer 3: LLM-enhanced analysis for complex code
    llm_gaps = _analyze_with_llm(github_docs, max_gaps=max_gaps_per_category * 2)

    if llm_gaps:
        result['gaps'].extend(llm_gaps)
        for gap in llm_gaps:
            cat = gap['category']
            result['gaps_by_category'][cat] = result['gaps_by_category'].get(cat, 0) + 1
        result['total_gaps'] += len(llm_gaps)
        result['analysis_layers'].append('llm')

    # Re-sort and limit
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    result['gaps'].sort(key=lambda g: priority_order.get(g['priority'], 4))

    return result


# =============================================================================
# LAYER 1: REGEX-BASED ANALYSIS
# =============================================================================

def _analyze_todos(content: str, file_path: str) -> List[Dict]:
    """Find TODOs/FIXMEs and generate contextual questions."""
    gaps = []
    patterns = [
        r'#\s*(TODO|FIXME|XXX|HACK|BUG|OPTIMIZE|REFACTOR)[\s:]+(.+?)(?:\n|$)',
        r'//\s*(TODO|FIXME|XXX|HACK|BUG|OPTIMIZE|REFACTOR)[\s:]+(.+?)(?:\n|$)',
        r'/\*\s*(TODO|FIXME|XXX|HACK|BUG)[\s:]+(.+?)\*/',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
            tag = match.group(1).upper()
            message = match.group(2).strip()

            # Get surrounding context
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context = content[start:end].strip()

            # Find what function/class this is in
            func_match = re.search(r'def\s+(\w+)|class\s+(\w+)|function\s+(\w+)', content[:match.start()][::-1])
            location = ""
            if func_match:
                func_name = func_match.group(1) or func_match.group(2) or func_match.group(3)
                if func_name:
                    location = f" in {func_name[::-1]}()"

            priority = 'high' if tag in ['FIXME', 'BUG'] else 'medium'

            # Generate specific question based on TODO content
            question = _generate_todo_question(tag, message, file_path, location)

            gaps.append({
                'category': 'todo_fixme',
                'title': f"{tag}: {message[:60]}{'...' if len(message) > 60 else ''}",
                'description': f"Found {tag} in {file_path}{location}",
                'question': question,
                'evidence': context[:300],
                'file_path': file_path,
                'priority': priority
            })

    return gaps


def _generate_todo_question(tag: str, message: str, file_path: str, location: str) -> str:
    """Generate contextual question based on TODO content."""
    msg_lower = message.lower()

    if 'security' in msg_lower or 'vulnerab' in msg_lower or 'injection' in msg_lower:
        return f"Security issue flagged{location} at {file_path}: '{message}'. What is the vulnerability and what's the remediation plan?"
    elif 'auth' in msg_lower:
        return f"Authentication TODO{location} at {file_path}: '{message}'. What authentication method will be implemented?"
    elif 'optim' in msg_lower or 'performance' in msg_lower or 'slow' in msg_lower:
        return f"Performance TODO{location} at {file_path}: '{message}'. What are the current bottlenecks and target metrics?"
    elif 'rate limit' in msg_lower:
        return f"Rate limiting TODO at {file_path}: '{message}'. What limits are needed (requests/min, per user/IP)?"
    elif 'test' in msg_lower:
        return f"Testing TODO at {file_path}: '{message}'. What test coverage is needed?"
    elif 'deprecat' in msg_lower:
        return f"Deprecation TODO{location} at {file_path}: '{message}'. What's the migration path?"
    elif 'refactor' in msg_lower:
        return f"Refactoring TODO{location} at {file_path}: '{message}'. What's the target architecture?"
    elif 'cache' in msg_lower:
        return f"Caching TODO{location} at {file_path}: '{message}'. What caching strategy is planned?"
    elif 'valid' in msg_lower:
        return f"Validation TODO{location} at {file_path}: '{message}'. What validation rules are needed?"
    else:
        return f"{tag} at {file_path}{location}: '{message}'. What is the status and plan for addressing this?"


def _analyze_security_regex(content: str, file_path: str) -> List[Dict]:
    """Find security issues using regex patterns."""
    gaps = []

    # Hardcoded secrets
    secret_patterns = [
        (r'(?:api_key|apikey|secret|password|passwd|pwd|token|auth_token|access_token|private_key)\s*[=:]\s*["\']([^"\']{8,})["\']', 'API key/secret', 'critical'),
        (r'(?:sk-|pk_|sk_live_|sk_test_|ghp_|gho_|github_pat_)[a-zA-Z0-9]{20,}', 'API key', 'critical'),
        (r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----', 'Private key', 'critical'),
        (r'(?:mongodb|postgres|mysql|redis)://[^"\'\s]+:[^"\'\s]+@', 'Database connection string with credentials', 'critical'),
    ]

    for pattern, secret_type, priority in secret_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            gaps.append({
                'category': 'security',
                'title': f"Hardcoded {secret_type} in {file_path}",
                'description': f"Found what appears to be a hardcoded {secret_type}",
                'question': f"Hardcoded {secret_type} found in {file_path}. Is this a production credential? Move to environment variables or secrets manager immediately.",
                'evidence': '[REDACTED - possible secret]',
                'file_path': file_path,
                'priority': priority
            })

    # SQL Injection
    sql_patterns = [
        (r'(?:execute|cursor\.execute|query)\s*\(\s*[f"\'].*\{.*\}', 'SQL injection via f-string'),
        (r'(?:execute|cursor\.execute|query)\s*\(\s*["\'].*%s.*%\s*\(', 'SQL injection via % formatting'),
        (r'(?:execute|cursor\.execute|query)\s*\(\s*["\'].*\+.*\+', 'SQL injection via concatenation'),
    ]

    for pattern, issue_type in sql_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            context = content[max(0, match.start()-50):match.end()+100]
            gaps.append({
                'category': 'security',
                'title': f"Potential {issue_type}",
                'description': f"Dynamic SQL query construction in {file_path}",
                'question': f"{issue_type} risk in {file_path}. Is user input being passed to this query? Use parameterized queries instead.",
                'evidence': context[:200],
                'file_path': file_path,
                'priority': 'critical'
            })

    # XSS vulnerabilities
    xss_patterns = [
        (r'innerHTML\s*=', 'XSS via innerHTML'),
        (r'dangerouslySetInnerHTML', 'XSS via dangerouslySetInnerHTML'),
        (r'document\.write\s*\(', 'XSS via document.write'),
        (r'\$\(\s*["\'][^"\']*\+', 'XSS via jQuery selector'),
    ]

    for pattern, issue_type in xss_patterns:
        for match in re.finditer(pattern, content):
            context = content[max(0, match.start()-50):match.end()+100]
            gaps.append({
                'category': 'security',
                'title': f"Potential {issue_type}",
                'description': f"Unsafe HTML manipulation in {file_path}",
                'question': f"{issue_type} risk in {file_path}. Is user input being rendered? Sanitize with DOMPurify or escape HTML entities.",
                'evidence': context[:200],
                'file_path': file_path,
                'priority': 'high'
            })

    # eval() and similar
    eval_patterns = [
        (r'\beval\s*\(', 'eval()'),
        (r'\bexec\s*\(', 'exec()'),
        (r'Function\s*\(', 'Function constructor'),
        (r'setTimeout\s*\(\s*["\']', 'setTimeout with string'),
        (r'setInterval\s*\(\s*["\']', 'setInterval with string'),
    ]

    for pattern, func_name in eval_patterns:
        for match in re.finditer(pattern, content):
            context = content[match.start():min(len(content), match.end()+100)]
            gaps.append({
                'category': 'security',
                'title': f"Dangerous {func_name} usage in {file_path}",
                'description': f"{func_name} can execute arbitrary code",
                'question': f"{func_name} in {file_path} is a security risk. Can this be replaced with a safer alternative like JSON.parse(), ast.literal_eval(), or a proper parser?",
                'evidence': context[:150],
                'file_path': file_path,
                'priority': 'high'
            })

    # Shell injection
    shell_patterns = [
        (r'(?:os\.system|os\.popen|subprocess\.call|subprocess\.run|subprocess\.Popen)\s*\([^)]*(?:f["\']|\+|%)', 'shell injection'),
        (r'child_process\.exec\s*\([^)]*(?:\+|`)', 'shell injection'),
    ]

    for pattern, issue_type in shell_patterns:
        for match in re.finditer(pattern, content):
            context = content[max(0, match.start()-30):match.end()+50]
            gaps.append({
                'category': 'security',
                'title': f"Potential {issue_type} in {file_path}",
                'description': "User input may be passed to shell command",
                'question': f"Shell command with dynamic input in {file_path}. Is user input being passed? Use subprocess with list arguments and shell=False.",
                'evidence': context[:200],
                'file_path': file_path,
                'priority': 'critical'
            })

    # Path traversal
    if re.search(r'open\s*\([^)]*(?:\+|f["\']|%)', content):
        gaps.append({
            'category': 'security',
            'title': f"Potential path traversal in {file_path}",
            'description': "File path may include user input",
            'question': f"File operation with dynamic path in {file_path}. Validate path doesn't contain '../' and is within allowed directory.",
            'evidence': 'Dynamic file path construction detected',
            'file_path': file_path,
            'priority': 'high'
        })

    # CORS wildcard
    if re.search(r'Access-Control-Allow-Origin["\']?\s*[=:]\s*["\']?\*', content, re.IGNORECASE):
        gaps.append({
            'category': 'security',
            'title': f"CORS wildcard in {file_path}",
            'description': "Allows requests from any origin",
            'question': f"CORS wildcard (*) in {file_path}. Should this be restricted to specific origins? This allows any website to make requests.",
            'evidence': 'Access-Control-Allow-Origin: *',
            'file_path': file_path,
            'priority': 'medium'
        })

    # JWT without verification
    if re.search(r'jwt\.decode\s*\([^)]*verify\s*=\s*False', content):
        gaps.append({
            'category': 'security',
            'title': f"JWT without verification in {file_path}",
            'description': "JWT token not being verified",
            'question': f"JWT decoded without verification in {file_path}. This allows forged tokens. Always verify JWT signatures.",
            'evidence': 'jwt.decode(..., verify=False)',
            'file_path': file_path,
            'priority': 'critical'
        })

    return gaps


def _analyze_error_handling_regex(content: str, file_path: str) -> List[Dict]:
    """Find error handling issues using regex."""
    gaps = []

    # Bare except in Python
    for match in re.finditer(r'except\s*:', content):
        start = max(0, match.start() - 100)
        context = content[start:match.end() + 50]
        gaps.append({
            'category': 'error_handling',
            'title': f"Bare except in {file_path}",
            'description': "Catches all exceptions including KeyboardInterrupt, SystemExit",
            'question': f"Bare 'except:' in {file_path} catches all exceptions. What specific exceptions should be caught?",
            'evidence': context[:200],
            'file_path': file_path,
            'priority': 'medium'
        })

    # Swallowed exceptions
    for match in re.finditer(r'except[^:]*:\s*\n\s*pass', content):
        start = max(0, match.start() - 100)
        context = content[start:match.end() + 20]
        gaps.append({
            'category': 'error_handling',
            'title': f"Swallowed exception in {file_path}",
            'description': "Exception is caught and ignored",
            'question': f"Exception silently ignored in {file_path}. Should this be logged? Is there error recovery needed?",
            'evidence': context[:200],
            'file_path': file_path,
            'priority': 'high'
        })

    # Empty catch blocks in JS/TS
    for match in re.finditer(r'catch\s*\([^)]*\)\s*\{\s*\}', content):
        gaps.append({
            'category': 'error_handling',
            'title': f"Empty catch block in {file_path}",
            'description': "Error is caught but not handled",
            'question': f"Empty catch block in {file_path}. Should this error be logged or handled?",
            'evidence': match.group(0),
            'file_path': file_path,
            'priority': 'high'
        })

    # console.log in catch (should be console.error)
    for match in re.finditer(r'catch[^{]*\{[^}]*console\.log', content):
        gaps.append({
            'category': 'error_handling',
            'title': f"console.log in catch block in {file_path}",
            'description': "Errors should use console.error",
            'question': f"Using console.log for errors in {file_path}. Use console.error for proper error logging.",
            'evidence': 'console.log in catch block',
            'file_path': file_path,
            'priority': 'low'
        })

    return gaps


def _analyze_code_quality_regex(content: str, file_path: str) -> List[Dict]:
    """Find code quality issues using regex."""
    gaps = []

    # Very long lines (>150 chars)
    lines = content.split('\n')
    long_lines = [(i+1, len(line)) for i, line in enumerate(lines) if len(line) > 150]
    if len(long_lines) > 5:
        gaps.append({
            'category': 'code_quality',
            'title': f"Many long lines in {file_path}",
            'description': f"{len(long_lines)} lines exceed 150 characters",
            'question': f"{file_path} has {len(long_lines)} lines over 150 chars. Consider breaking these up for readability.",
            'evidence': f"Lines {', '.join(str(l[0]) for l in long_lines[:5])}... are too long",
            'file_path': file_path,
            'priority': 'low'
        })

    # Deep nesting detection (4+ levels)
    indent_pattern = re.compile(r'^(\s+)')
    max_indent = 0
    for line in lines:
        match = indent_pattern.match(line)
        if match:
            indent = len(match.group(1))
            if indent > max_indent:
                max_indent = indent

    # Assuming 4-space indent, 16+ spaces = 4+ levels
    if max_indent >= 16:
        levels = max_indent // 4
        gaps.append({
            'category': 'code_quality',
            'title': f"Deep nesting ({levels} levels) in {file_path}",
            'description': f"Code is nested {levels} levels deep",
            'question': f"{file_path} has {levels}-level nesting. Consider extracting helper functions or using early returns.",
            'evidence': f"Maximum indentation: {max_indent} spaces",
            'file_path': file_path,
            'priority': 'medium'
        })

    # Magic numbers
    magic_pattern = r'(?<!["\'\w])(?:(?<![=<>!])(?:100|1000|3600|86400|60|24|365|1024|2048|4096)(?![0-9]))(?!["\'])'
    magic_matches = list(re.finditer(magic_pattern, content))
    if len(magic_matches) > 3:
        gaps.append({
            'category': 'code_quality',
            'title': f"Magic numbers in {file_path}",
            'description': f"Found {len(magic_matches)} magic numbers",
            'question': f"{file_path} has magic numbers. Consider defining constants with descriptive names (e.g., SECONDS_PER_HOUR = 3600).",
            'evidence': 'Magic numbers found: ' + ', '.join(m.group(0) for m in magic_matches[:5]),
            'file_path': file_path,
            'priority': 'low'
        })

    # Duplicate code patterns (simple detection)
    # Look for identical lines repeated
    line_counts = defaultdict(int)
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 30 and not stripped.startswith(('#', '//', '/*', '*', 'import', 'from')):
            line_counts[stripped] += 1

    duplicates = [(line, count) for line, count in line_counts.items() if count >= 3]
    if duplicates:
        gaps.append({
            'category': 'code_quality',
            'title': f"Duplicate code in {file_path}",
            'description': f"Found {len(duplicates)} repeated code patterns",
            'question': f"{file_path} has repeated code. Consider extracting to reusable functions.",
            'evidence': f"'{duplicates[0][0][:50]}...' appears {duplicates[0][1]} times",
            'file_path': file_path,
            'priority': 'medium'
        })

    # Hardcoded URLs/IPs
    url_pattern = r'https?://(?!localhost|127\.0\.0\.1|example\.com)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'

    urls = re.findall(url_pattern, content)
    ips = re.findall(ip_pattern, content)

    # Filter out common test IPs
    ips = [ip for ip in ips if not ip.startswith(('127.', '0.', '192.168.', '10.'))]

    if urls or ips:
        gaps.append({
            'category': 'code_quality',
            'title': f"Hardcoded URLs/IPs in {file_path}",
            'description': f"Found {len(urls)} URLs and {len(ips)} IPs",
            'question': f"Hardcoded URLs/IPs in {file_path}. Should these be environment variables or config settings?",
            'evidence': ', '.join(urls[:3] + ips[:2])[:100],
            'file_path': file_path,
            'priority': 'medium'
        })

    # Print statements in production code
    print_count = len(re.findall(r'\bprint\s*\(', content))
    console_count = len(re.findall(r'console\.log\s*\(', content))
    if print_count > 5 or console_count > 10:
        gaps.append({
            'category': 'code_quality',
            'title': f"Debug statements in {file_path}",
            'description': f"Found {print_count} print() and {console_count} console.log()",
            'question': f"{file_path} has {print_count + console_count} debug statements. Replace with proper logging for production.",
            'evidence': f'{print_count} print statements, {console_count} console.log calls',
            'file_path': file_path,
            'priority': 'low'
        })

    return gaps


def _analyze_api_endpoints(content: str, file_path: str) -> List[Dict]:
    """Analyze API endpoints."""
    gaps = []

    # Flask/FastAPI patterns
    patterns = [
        r'@(?:app|router|blueprint|api)\.(?:route|get|post|put|delete|patch)\s*\([\'"]([^\'"]+)[\'"]',
        r'@(?:GetMapping|PostMapping|PutMapping|DeleteMapping)\s*\([\'"]([^\'"]+)[\'"]',  # Spring
        r'router\.(?:get|post|put|delete|patch)\s*\([\'"]([^\'"]+)[\'"]',  # Express
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            endpoint = match.group(1)

            # Get the function after the decorator
            func_match = re.search(r'(?:def|function|async\s+function)\s+(\w+)', content[match.end():match.end()+200])
            func_name = func_match.group(1) if func_match else 'handler'

            # Check for documentation
            has_docs = bool(re.search(r'["\'\s]{3}|/\*\*', content[match.end():match.end()+300]))

            if has_docs:
                continue  # Skip documented endpoints

            question_parts = [f"API endpoint `{endpoint}` ({func_name}) in {file_path}:"]
            question_parts.append("What request parameters/body does it accept?")
            question_parts.append("What response format does it return?")
            question_parts.append("What authentication is required?")

            if 'admin' in endpoint.lower():
                question_parts.append("What admin privileges are needed?")
            if any(x in endpoint.lower() for x in ['user', 'profile', 'account']):
                question_parts.append("How is user data protected?")
            if any(x in endpoint.lower() for x in ['upload', 'file', 'image']):
                question_parts.append("What file validations are performed?")

            gaps.append({
                'category': 'api_documentation',
                'title': f"Undocumented API: {endpoint}",
                'description': f"Endpoint needs documentation in {file_path}",
                'question': ' '.join(question_parts),
                'evidence': match.group(0),
                'file_path': file_path,
                'priority': 'high'
            })

    return gaps[:10]  # Limit API gaps per file


def _analyze_config_values(content: str, file_path: str) -> List[Dict]:
    """Find hardcoded configuration values."""
    gaps = []

    patterns = [
        (r'(?:timeout|delay|interval)\s*[=:]\s*(\d{2,})', 'timeout/delay'),
        (r'(?:max_\w+|min_\w+|limit)\s*[=:]\s*(\d+)', 'limit'),
        (r'(?:port)\s*[=:]\s*(\d{4,5})', 'port'),
        (r'(?:retries|retry_count|max_retries)\s*[=:]\s*(\d+)', 'retry count'),
        (r'(?:batch_size|chunk_size|page_size)\s*[=:]\s*(\d+)', 'batch size'),
        (r'(?:cache_ttl|ttl|expir\w*)\s*[=:]\s*(\d+)', 'cache TTL'),
    ]

    seen = set()
    for pattern, config_type in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            full_match = match.group(0)
            value = match.group(1)

            if full_match in seen:
                continue
            seen.add(full_match)

            start = max(0, match.start() - 50)
            context = content[start:match.end() + 30]

            gaps.append({
                'category': 'configuration',
                'title': f"Hardcoded {config_type}: {full_match[:40]}",
                'description': f"Configuration value in {file_path}",
                'question': f"Configuration `{full_match}` in {file_path}: Why was {value} chosen? Should this be configurable via environment variable?",
                'evidence': context[:150],
                'file_path': file_path,
                'priority': 'low'
            })

    return gaps[:5]


def _analyze_javascript_patterns(content: str, file_path: str) -> List[Dict]:
    """Analyze JavaScript/TypeScript specific patterns."""
    gaps = []

    # Missing error boundaries in React
    if 'React' in content and 'componentDidCatch' not in content and 'ErrorBoundary' not in content:
        if re.search(r'class\s+\w+\s+extends\s+(?:React\.)?Component', content):
            gaps.append({
                'category': 'error_handling',
                'title': f"No error boundary in {file_path}",
                'description': "React component may crash without error handling",
                'question': f"React components in {file_path} have no error boundary. Add componentDidCatch or use an ErrorBoundary component.",
                'evidence': 'Class component without error boundary',
                'file_path': file_path,
                'priority': 'medium'
            })

    # useEffect without cleanup
    use_effect_matches = list(re.finditer(r'useEffect\s*\(\s*\(\)\s*=>\s*\{([^}]+)\}', content))
    for match in use_effect_matches:
        body = match.group(1)
        has_cleanup = 'return' in body
        has_subscription = any(x in body for x in ['addEventListener', 'subscribe', 'setInterval', 'setTimeout'])
        if has_subscription and not has_cleanup:
            gaps.append({
                'category': 'code_quality',
                'title': f"useEffect without cleanup in {file_path}",
                'description': "Subscription/timer without cleanup causes memory leaks",
                'question': f"useEffect in {file_path} sets up subscription/timer without cleanup. Return a cleanup function.",
                'evidence': body[:100],
                'file_path': file_path,
                'priority': 'high'
            })

    # Missing PropTypes or TypeScript types
    if '.jsx' in file_path and 'PropTypes' not in content and not re.search(r':\s*\w+Props', content):
        gaps.append({
            'category': 'code_quality',
            'title': f"No prop validation in {file_path}",
            'description': "Component props are not validated",
            'question': f"React component in {file_path} has no prop validation. Add PropTypes or convert to TypeScript.",
            'evidence': 'No PropTypes found',
            'file_path': file_path,
            'priority': 'low'
        })

    # Async/await without try-catch
    async_functions = list(re.finditer(r'async\s+(?:function\s+\w+|\(\w*\)|[\w]+)\s*(?:\([^)]*\))?\s*(?:=>)?\s*\{([^}]{100,})\}', content))
    for match in async_functions:
        body = match.group(1)
        has_await = 'await' in body
        has_try = 'try' in body
        if has_await and not has_try:
            gaps.append({
                'category': 'error_handling',
                'title': f"Async without try-catch in {file_path}",
                'description': "Async function may have unhandled rejections",
                'question': f"Async function in {file_path} uses await without try-catch. Add error handling for async operations.",
                'evidence': body[:80],
                'file_path': file_path,
                'priority': 'medium'
            })
            break  # Only report once per file

    return gaps


# =============================================================================
# LAYER 2: AST-BASED ANALYSIS (Python)
# =============================================================================

def _analyze_python_ast(content: str, file_path: str) -> List[Dict]:
    """Analyze Python code using AST for accurate detection."""
    gaps = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return gaps  # Can't parse, skip AST analysis

    # Collect function info
    functions = []
    classes = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            functions.append(node)
        elif isinstance(node, ast.ClassDef):
            classes.append(node)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    # Analyze functions
    for func in functions:
        # Skip private/dunder methods
        if func.name.startswith('_'):
            continue

        # Check for docstring
        has_docstring = (
            func.body and
            isinstance(func.body[0], ast.Expr) and
            isinstance(func.body[0].value, (ast.Str, ast.Constant))
        )

        # Check for type hints
        has_return_hint = func.returns is not None
        args_with_hints = sum(1 for arg in func.args.args if arg.annotation)
        total_args = len(func.args.args)

        # Calculate complexity (simplified cyclomatic)
        complexity = _calculate_complexity(func)

        # Get function length
        func_lines = func.end_lineno - func.lineno if hasattr(func, 'end_lineno') else 0

        # Report issues
        if not has_docstring and total_args > 2:
            gaps.append({
                'category': 'documentation',
                'title': f"Undocumented: {func.name}()",
                'description': f"Function with {total_args} parameters lacks documentation",
                'question': f"Function `{func.name}` in {file_path} has {total_args} parameters but no docstring. Document the purpose, parameters, and return value.",
                'evidence': f"def {func.name}(...) at line {func.lineno}",
                'file_path': file_path,
                'priority': 'medium'
            })

        if total_args > 0 and args_with_hints == 0 and not func.name.startswith('test'):
            gaps.append({
                'category': 'type_safety',
                'title': f"No type hints: {func.name}()",
                'description': f"Function has {total_args} untyped parameters",
                'question': f"Function `{func.name}` in {file_path} has no type hints. Add type annotations for better IDE support and error catching.",
                'evidence': f"def {func.name}(...) at line {func.lineno}",
                'file_path': file_path,
                'priority': 'low'
            })

        if complexity > 10:
            gaps.append({
                'category': 'complexity',
                'title': f"High complexity: {func.name}()",
                'description': f"Cyclomatic complexity is {complexity}",
                'question': f"Function `{func.name}` in {file_path} has complexity {complexity} (>10). Consider breaking into smaller functions.",
                'evidence': f"def {func.name}(...) at line {func.lineno}, complexity: {complexity}",
                'file_path': file_path,
                'priority': 'medium' if complexity < 15 else 'high'
            })

        if func_lines > 50:
            gaps.append({
                'category': 'code_quality',
                'title': f"Long function: {func.name}()",
                'description': f"Function is {func_lines} lines long",
                'question': f"Function `{func.name}` in {file_path} is {func_lines} lines. Consider extracting helper functions.",
                'evidence': f"def {func.name}(...) spans lines {func.lineno}-{func.end_lineno}",
                'file_path': file_path,
                'priority': 'medium'
            })

    # Check for unused imports (basic check)
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            used_names.add(node.attr)

    # Note: This is a simplified check and may have false positives

    return gaps[:10]  # Limit per file


def _calculate_complexity(func_node) -> int:
    """Calculate simplified cyclomatic complexity for a function."""
    complexity = 1  # Base complexity

    for node in ast.walk(func_node):
        # Decision points
        if isinstance(node, (ast.If, ast.While, ast.For)):
            complexity += 1
        elif isinstance(node, ast.ExceptHandler):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            # and/or add to complexity
            complexity += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            # List/dict comprehensions with conditions
            complexity += len(node.ifs)
        elif isinstance(node, ast.IfExp):
            # Ternary expressions
            complexity += 1

    return complexity


# =============================================================================
# LAYER 3: LLM-ENHANCED ANALYSIS
# =============================================================================

def _analyze_with_llm(documents: List[Dict], max_gaps: int = 10) -> List[Dict]:
    """Use LLM for deep semantic analysis of complex code."""
    gaps = []

    try:
        from services.openai_client import get_openai_client
        client = get_openai_client()
    except Exception as e:
        print(f"[CodeGap] LLM not available: {e}")
        return gaps

    # Find complex/important files to analyze
    candidates = []
    for doc in documents:
        content = doc.get('content', '')
        metadata = doc.get('metadata') or doc.get('doc_metadata') or {}
        file_path = metadata.get('file_path') or doc.get('title', '')

        # Score files by importance
        score = 0
        if 'main' in file_path.lower() or 'app' in file_path.lower():
            score += 3
        if 'service' in file_path.lower() or 'controller' in file_path.lower():
            score += 2
        if 'api' in file_path.lower() or 'route' in file_path.lower():
            score += 2
        if 'auth' in file_path.lower() or 'security' in file_path.lower():
            score += 3
        if len(content) > 2000:
            score += 1

        if score > 0:
            candidates.append((score, file_path, content[:8000]))

    # Sort by importance and take top 3
    candidates.sort(reverse=True, key=lambda x: x[0])
    top_files = candidates[:3]

    if not top_files:
        return gaps

    # Build context for LLM
    code_context = "\n\n".join([
        f"=== {path} ===\n{content[:2500]}"
        for _, path, content in top_files
    ])

    prompt = f"""Analyze this code and identify SPECIFIC knowledge gaps - things that would confuse a new engineer or could cause bugs.

{code_context}

Focus on:
1. **Business Logic** - What business rules are unclear or undocumented?
2. **Edge Cases** - What happens in edge cases? Are they handled?
3. **Data Flow** - How does data flow through this code? What transformations happen?
4. **Error Scenarios** - What can go wrong? How are errors propagated?
5. **Integration Points** - What external services/APIs does this interact with?
6. **Assumptions** - What assumptions does this code make that should be documented?

For each gap, provide:
- category: business_logic | edge_cases | data_flow | error_handling | integration | assumptions
- title: Short title (max 50 chars)
- question: Specific question about this code
- file_path: Which file this applies to
- priority: high | medium | low

Return as JSON array. Only include SPECIFIC gaps found in THIS code, not generic advice."""

    try:
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a senior code reviewer. Identify specific knowledge gaps in the provided code. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )

        response_text = response.choices[0].message.content

        # Parse JSON from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            llm_gaps = json.loads(json_match.group())
        else:
            llm_gaps = json.loads(response_text)

        for gap in llm_gaps[:max_gaps]:
            gaps.append({
                'category': gap.get('category', 'llm_analysis'),
                'title': gap.get('title', 'Code Analysis Gap')[:60],
                'description': 'Identified by AI code analysis',
                'question': gap.get('question', ''),
                'evidence': 'AI analysis of code patterns',
                'file_path': gap.get('file_path'),
                'priority': gap.get('priority', 'medium'),
                'source': 'llm'
            })

        print(f"[CodeGap] LLM generated {len(gaps)} gaps")

    except Exception as e:
        print(f"[CodeGap] LLM analysis failed: {e}")

    return gaps


# =============================================================================
# CROSS-FILE ANALYSIS
# =============================================================================

def _analyze_testing(docs: List[Dict]) -> List[Dict]:
    """Check for testing gaps across the repository."""
    gaps = []

    test_files = []
    source_files = []

    for doc in docs:
        title = doc.get('title', '') or ''
        metadata = doc.get('metadata') or doc.get('doc_metadata') or {}
        file_path = metadata.get('file_path') or title

        if 'test' in file_path.lower():
            test_files.append(file_path)
        elif file_path.endswith(('.py', '.js', '.ts', '.jsx', '.tsx')):
            source_files.append(file_path)

    if not test_files and source_files:
        # No tests at all
        gaps.append({
            'category': 'testing',
            'title': "No test files found",
            'description': f"Repository has {len(source_files)} source files but no tests",
            'question': f"No test files found. Critical files like {', '.join(source_files[:3])} need tests. What testing framework will be used?",
            'evidence': f"Source files: {len(source_files)}, Test files: 0",
            'file_path': None,
            'priority': 'high'
        })
    elif test_files and source_files:
        # Check coverage ratio
        ratio = len(test_files) / len(source_files)
        if ratio < 0.3:
            gaps.append({
                'category': 'testing',
                'title': "Low test coverage",
                'description': f"Only {len(test_files)} test files for {len(source_files)} source files",
                'question': f"Test coverage is low ({len(test_files)} tests for {len(source_files)} files). Which critical paths need tests first?",
                'evidence': f"Coverage ratio: {ratio:.1%}",
                'file_path': None,
                'priority': 'medium'
            })

    return gaps


def _analyze_architecture_patterns(docs: List[Dict]) -> List[Dict]:
    """Analyze architectural patterns across the repository."""
    gaps = []

    # Collect file paths
    file_paths = []
    for doc in docs:
        metadata = doc.get('metadata') or doc.get('doc_metadata') or {}
        file_path = metadata.get('file_path') or doc.get('title', '')
        if file_path:
            file_paths.append(file_path.lower())

    if not file_paths:
        return gaps

    # Check for common missing architectural components
    checks = [
        ('logging', ['log', 'logger', 'logging'], "No logging infrastructure found. How are events and errors logged?"),
        ('config', ['config', 'settings', 'env'], "No configuration management found. How are environment-specific settings handled?"),
        ('middleware', ['middleware', 'interceptor'], "No middleware found. How are cross-cutting concerns (auth, logging, error handling) managed?"),
        ('database migrations', ['migration', 'alembic', 'flyway'], "No database migrations found. How are schema changes managed?"),
    ]

    for name, keywords, question in checks:
        has_component = any(any(kw in path for kw in keywords) for path in file_paths)
        if not has_component and len(file_paths) > 5:  # Only check for larger repos
            gaps.append({
                'category': 'architecture',
                'title': f"Missing {name}",
                'description': f"No {name} files detected",
                'question': question,
                'evidence': f"Searched {len(file_paths)} files",
                'file_path': None,
                'priority': 'medium'
            })

    return gaps


# =============================================================================
# UTILITIES
# =============================================================================

def _deduplicate_gaps(gaps: List[Dict]) -> List[Dict]:
    """Remove duplicate or very similar gaps."""
    seen = set()
    unique_gaps = []

    for gap in gaps:
        # Create a fingerprint for the gap
        fingerprint = (
            gap['category'],
            gap.get('file_path', ''),
            gap['title'][:30].lower()
        )

        if fingerprint not in seen:
            seen.add(fingerprint)
            unique_gaps.append(gap)

    return unique_gaps


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

def analyze_architecture_gaps(documents: List[Dict], architecture_docs: List[Dict], max_gaps: int = 10) -> List[Dict]:
    """Legacy function for backward compatibility."""
    return _analyze_with_llm(documents, max_gaps)


def analyze_code_gaps_with_architecture(
    documents: List[Dict],
    architecture_docs: List[Dict] = None,
    max_gaps_per_category: int = 5
) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    return analyze_code_gaps_with_llm(documents, max_gaps_per_category, use_llm=bool(architecture_docs))
