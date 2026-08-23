"""Thread-safety hardening for ATLAS JSONL persistence.

The production HTTP server and background workers share one process. This layer
serializes append operations and the full forward maturity read/rewrite
transaction so a concurrent append cannot be lost during atomic replacement.
"""


def install(collector):
    if getattr(collector, "_STORAGE_HARDENING_INSTALLED", False):
        return getattr(collector, "STORAGE_HARDENING_STATE", {})

    lock = collector.ARCHIVE_LOCK
    state = {
        "enabled": True,
        "forward_write_locked": False,
        "forward_update_locked": False,
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

    # update_forward_returns performs read -> mutate -> temp file -> replace.
    # Locking the entire transaction is required; locking only _forward_write
    # cannot protect an append that lands between the read and replace phases.
    original_forward_update = getattr(collector, "update_forward_returns", None)
    if original_forward_update is not None:
        def locked_forward_update(*args, **kwargs):
            with lock:
                return original_forward_update(*args, **kwargs)
        collector.update_forward_returns = locked_forward_update
        state["forward_update_locked"] = True

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
