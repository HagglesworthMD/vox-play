"""
Sequential masking utilities for memory-sensitive workflows.
"""

import gc
import logging
from typing import Callable, Iterable, Any, Optional

logger = logging.getLogger(__name__)

def process_instances_sequentially(
    instances: Iterable[Any],
    process_fn: Callable[[Any], None],
    *,
    identifier_fn: Optional[Callable[[Any], str]] = None,
    gc_collect: bool = True,
) -> int:
    """Process items one-by-one with cleanup between iterations.

    US series processed sequentially to prevent memory exhaustion.
    """

    failure_count = 0

    for instance in instances:
        try:
            process_fn(instance)
        except Exception as exc:  # pragma: no cover
            failure_count += 1
            identifier = identifier_fn(instance) if identifier_fn else str(instance)
            logger.warning("US masking failed for %s: %s", identifier, exc)
        finally:
            if gc_collect:
                gc.collect()

    return failure_count
