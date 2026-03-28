"""Adapter utilities for wrapping existing services."""

import json
import logging
from typing import Generator, List, Dict, Any

logger = logging.getLogger(__name__)


def parse_sse_stream(generator: Generator[str, None, None]) -> List[Dict[str, Any]]:
    """
    Consume an SSE generator and parse events into structured dicts.

    Existing services (HIJ, Competitor Finder) yield raw SSE strings like:
        "event: progress\\ndata: {...}\\n\\n"

    This collects all events and returns them as a list of parsed dicts:
        [{"event": "progress", "data": {...}}, ...]
    """
    events = []
    buffer = ""

    for chunk in generator:
        buffer += chunk

        while "\n\n" in buffer:
            event_str, buffer = buffer.split("\n\n", 1)
            event_data = _parse_single_sse_event(event_str.strip())
            if event_data:
                events.append(event_data)

    if buffer.strip():
        event_data = _parse_single_sse_event(buffer.strip())
        if event_data:
            events.append(event_data)

    return events


def _parse_single_sse_event(event_str: str) -> Dict[str, Any] | None:
    """Parse a single SSE event string into {event, data}."""
    event_type = "message"
    data_lines = []

    for line in event_str.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if not data_lines:
        return None

    raw_data = "\n".join(data_lines)
    try:
        parsed_data = json.loads(raw_data)
    except json.JSONDecodeError:
        parsed_data = raw_data

    return {"event": event_type, "data": parsed_data}


def make_result_envelope(
    service: str,
    status: str = "success",
    summary: str | None = None,
    full_results: Dict | None = None,
    error: str | None = None,
) -> Dict[str, Any]:
    """Create a standardized result envelope for the parallel executor."""
    return {
        "service": service,
        "status": status,
        "summary": summary,
        "full_results": full_results,
        "error": error,
    }
