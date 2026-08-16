"""Background work helper.

SwiftUI's `.task {}` / `Task {}` blocks kept the UI responsive while minipro
ran. GTK has no equivalent, so every MiniproAPI call goes to a worker thread
and results are marshalled back onto the main loop with GLib.idle_add.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

from gi.repository import GLib

logger = logging.getLogger("visualminipro.tasks")


def run_async(
    work: Callable[[], Any],
    on_success: Optional[Callable[[Any], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> threading.Thread:
    """Run `work` off the main loop, then dispatch the outcome back onto it."""

    def target() -> None:
        try:
            result = work()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user verbatim
            logger.info("background task failed: %s: %s", type(exc).__name__, exc)
            if on_error is not None:
                GLib.idle_add(on_error, exc, priority=GLib.PRIORITY_DEFAULT)
            return
        if on_success is not None:
            GLib.idle_add(on_success, result, priority=GLib.PRIORITY_DEFAULT)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def on_main_thread(callback: Callable[..., Any], *args: Any) -> None:
    """Schedule `callback` on the GTK main loop (safe from any thread)."""
    GLib.idle_add(lambda: (callback(*args), False)[1], priority=GLib.PRIORITY_DEFAULT)
