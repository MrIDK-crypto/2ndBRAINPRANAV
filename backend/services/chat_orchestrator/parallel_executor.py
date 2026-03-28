"""Layer 3: Parallel Executor — runs multiple service adapters concurrently."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)

PER_SERVICE_TIMEOUT = 90
TOTAL_TIMEOUT = 120

_ADAPTER_REGISTRY: Dict[str, Callable] = {}


def _register_adapters():
    global _ADAPTER_REGISTRY
    if _ADAPTER_REGISTRY:
        return

    from .adapters.hij_adapter import run_hij
    from .adapters.competitor_adapter import run_competitor_finder
    from .adapters.idea_adapter import run_idea_reality
    from .adapters.co_researcher_adapter import run_co_researcher

    _ADAPTER_REGISTRY = {
        "hij": run_hij,
        "competitor_finder": run_competitor_finder,
        "idea_reality": run_idea_reality,
        "co_researcher": run_co_researcher,
    }


def execute(
    tool_calls: List[Dict[str, Any]],
    context_package: Optional[Dict[str, Any]] = None,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    tenant_id: Optional[str] = None,
    on_service_start: Optional[Callable] = None,
    on_service_complete: Optional[Callable] = None,
) -> List[Dict[str, Any]]:
    _register_adapters()

    if not tool_calls:
        return []

    results = []
    tasks = []

    for tc in tool_calls:
        service = tc["service"]
        args = tc.get("args", {})
        adapter_fn = _ADAPTER_REGISTRY.get(service)
        if not adapter_fn:
            logger.warning(f"No adapter registered for service: {service}")
            continue

        kwargs = _build_adapter_kwargs(
            service=service,
            args=args,
            context_package=context_package,
            file_bytes=file_bytes,
            filename=filename,
            tenant_id=tenant_id,
        )
        tasks.append((service, adapter_fn, kwargs))

    if not tasks:
        return []

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_service = {}

        for service, adapter_fn, kwargs in tasks:
            if on_service_start:
                on_service_start(service)
            future = executor.submit(adapter_fn, **kwargs)
            future_to_service[future] = service

        try:
            for future in as_completed(future_to_service, timeout=TOTAL_TIMEOUT):
                service = future_to_service[future]
                try:
                    result = future.result(timeout=PER_SERVICE_TIMEOUT)
                    results.append(result)
                    if on_service_complete:
                        on_service_complete(service, result.get("status", "success"))
                except TimeoutError:
                    logger.warning(f"Service {service} timed out")
                    from .adapters import make_result_envelope
                    results.append(make_result_envelope(
                        service=service,
                        status="timeout",
                        error=f"Service timed out after {PER_SERVICE_TIMEOUT}s. Try the standalone version.",
                    ))
                    if on_service_complete:
                        on_service_complete(service, "timeout")
                except Exception as e:
                    logger.error(f"Service {service} failed: {e}", exc_info=True)
                    from .adapters import make_result_envelope
                    results.append(make_result_envelope(
                        service=service,
                        status="error",
                        error=str(e),
                    ))
                    if on_service_complete:
                        on_service_complete(service, "error")

        except TimeoutError:
            logger.warning("Total execution timeout exceeded")
            for future, service in future_to_service.items():
                if not future.done():
                    from .adapters import make_result_envelope
                    results.append(make_result_envelope(
                        service=service,
                        status="timeout",
                        error="Overall timeout exceeded.",
                    ))

    return results


def _build_adapter_kwargs(
    service: str,
    args: Dict[str, Any],
    context_package: Optional[Dict],
    file_bytes: Optional[bytes],
    filename: Optional[str],
    tenant_id: Optional[str],
) -> Dict[str, Any]:
    kwargs = {"context_package": context_package}

    if service == "hij":
        kwargs["file_bytes"] = file_bytes
        kwargs["filename"] = filename
        kwargs["raw_text"] = args.get("paper_text")
    elif service == "competitor_finder":
        kwargs["topics"] = args.get("topics")
        kwargs["field"] = args.get("field")
        kwargs["paper_text"] = args.get("paper_text")
    elif service == "idea_reality":
        kwargs["idea_description"] = args.get("idea_description", "")
    elif service == "co_researcher":
        kwargs["research_question"] = args.get("research_question", "")
        kwargs["paper_text"] = args.get("paper_text")
        kwargs["protocol_text"] = args.get("protocol_text")
        kwargs["tenant_id"] = tenant_id

    return kwargs
