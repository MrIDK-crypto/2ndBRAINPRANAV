"""
json_utils.py — Robust JSON parsing and API retry helpers for LLM responses.

Handles common issues like:
- Unterminated strings
- Truncated JSON
- Markdown code blocks
- Trailing commas
- API timeouts with retry logic
"""

import json
import re
import time
from functools import wraps


def retry_api_call(max_retries: int = 3, base_delay: float = 2.0):
    """
    Decorator that retries API calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()

                    # Check if it's a retryable error
                    is_timeout = "timeout" in error_str or "timed out" in error_str
                    is_rate_limit = "429" in error_str or "rate" in error_str
                    is_server_error = "500" in error_str or "502" in error_str or "503" in error_str

                    if attempt < max_retries and (is_timeout or is_rate_limit or is_server_error):
                        delay = base_delay * (2 ** attempt)
                        print(f"[retry] Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        # Non-retryable error or max retries reached
                        raise
            raise last_exception
        return wrapper
    return decorator


def robust_json_parse(raw: str, fallback: dict = None) -> dict:
    """
    Attempt to parse JSON from LLM response with error recovery.

    Args:
        raw: The raw string from the LLM
        fallback: Default value if parsing fails completely

    Returns:
        Parsed JSON dict or fallback value
    """
    if fallback is None:
        fallback = {}

    if not raw or not raw.strip():
        return fallback

    # Strip markdown code blocks if present
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # First, try normal parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to fix unterminated strings by finding the last complete object/array
    try:
        # Find balanced braces/brackets
        fixed = fix_truncated_json(text)
        return json.loads(fixed)
    except (json.JSONDecodeError, Exception):
        pass

    # Try removing trailing commas
    try:
        # Remove trailing commas before } or ]
        no_trailing = re.sub(r',\s*([}\]])', r'\1', text)
        return json.loads(no_trailing)
    except json.JSONDecodeError:
        pass

    # Last resort: extract any valid JSON object
    try:
        # Find the first { and try to find matching }
        start = text.find('{')
        if start >= 0:
            depth = 0
            in_string = False
            escape = False
            for i, c in enumerate(text[start:], start):
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[start:i+1])
    except (json.JSONDecodeError, Exception):
        pass

    print(f"[json_utils] Failed to parse JSON, using fallback. Raw (first 500 chars): {raw[:500]}")
    return fallback


def fix_truncated_json(text: str) -> str:
    """
    Attempt to fix truncated JSON by closing unclosed brackets/braces/strings.
    """
    # Track state
    in_string = False
    escape = False
    stack = []

    for i, c in enumerate(text):
        if escape:
            escape = False
            continue

        if c == '\\' and in_string:
            escape = True
            continue

        if c == '"':
            if in_string:
                in_string = False
            else:
                in_string = True
            continue

        if in_string:
            continue

        if c == '{':
            stack.append('}')
        elif c == '[':
            stack.append(']')
        elif c == '}' or c == ']':
            if stack and stack[-1] == c:
                stack.pop()

    # Close unclosed string
    if in_string:
        text += '"'

    # Close unclosed brackets/braces
    while stack:
        text += stack.pop()

    return text
