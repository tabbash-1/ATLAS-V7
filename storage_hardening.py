"""Thread-safety hardening for ATLAS JSONL persistence.

The production HTTP server and background workers share one process. This layer
serializes append operations that were historically safe in the single-worker
prototype but can now be reached concurrently by HTTP and cloud workers.
"""


def install(collector):
    if getattr(collector, "_STORAGE_HARDENING_INSTALLED", False):
        return getattr(collector, "STORAGE_HARDENING_STATE", {})

    lock = collector.ARCHIVE_LOCK
    state = {
        "enabled": True,
        "forward_write_locked": False,
        "confluence_write_locked": False,
        "event_write_locked": False,
    }

    original_forward_write = getattr(collector, "_forward_write", None)
    if original_forward_write is not None:
        def locked_forward_write(row):
            with lock:
                return original_forward_write(row)
        collector._forward_write = locked_forward_write
        state["forward_write_locked"] = True

    original_confluence_observe = getattr(collector, "confluence_observe", None)
    if original_confluence_observe is not None:
        def locked_confluence_observe(payload):
            with lock:
                return original_confluence_observe(payload)
        collector.confluence_observe = locked_confluence_observe
        state["confluence_write_locked"] = True

    original_event_observe = getattr(collector, "event_observe", None)
    if original_event_observe is not None:
        def locked_event_observe(payload):
            with lock:
                return original_event_observe(payload)
        collector.event_observe = locked_event_observe
        state["event_write_locked"] = True

    collector.STORAGE_HARDENING_STATE = state
    collector._STORAGE_HARDENING_INSTALLED = True
    return state
