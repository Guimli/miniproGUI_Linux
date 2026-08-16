"""Application entry point.

Port of MiniproUI/MiniproUIApp.swift (Visual Minipro 1.5.8).
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from ..utils import apply_libusb_debug_logging, settings
from .window import MainWindow

APP_ID = "io.github.moozzyk.VisualMiniproLinux"


class VisualMiniproApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        # LIBUSB_DEBUG has to be set before minipro is spawned.
        apply_libusb_debug_logging(settings.libusb_debug_logging)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    application = VisualMiniproApplication()
    return application.run(argv)
