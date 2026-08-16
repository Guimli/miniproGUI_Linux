"""Chip details panel.

Port of MiniproUI/DeviceDetailsView.swift (Visual Minipro 1.5.8).
"""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..minipro import DeviceDetails
from .widgets import property_row


class DeviceDetailsPanel(Gtk.Box):
    def __init__(self, expect_logic_chip: bool = False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._expect_logic_chip = expect_logic_chip
        self._groups: list[Gtk.Widget] = []
        self._placeholder = Gtk.Label(label="Select a chip to see its details")
        self._placeholder.add_css_class("dim-label")
        self._placeholder.set_margin_top(12)
        self._placeholder.set_margin_bottom(12)
        self.append(self._placeholder)

    def _clear(self) -> None:
        for group in self._groups:
            self.remove(group)
        self._groups.clear()

    def set_details(self, details: Optional[DeviceDetails]) -> None:
        self._clear()
        if details is None:
            self._placeholder.set_visible(True)
            return
        self._placeholder.set_visible(False)

        if details.device_info:
            group = Adw.PreferencesGroup(title="Device Info")
            for pair in details.device_info:
                group.add(property_row(pair.key, pair.value))
            self.append(group)
            self._groups.append(group)

        # Logic ICs report no programming voltages, so the section is omitted.
        if details.programming_info:
            group = Adw.PreferencesGroup(title="Programming Info")
            for pair in details.programming_info:
                group.add(property_row(pair.key, pair.value))
            self.append(group)
            self._groups.append(group)

        if self._expect_logic_chip and not details.is_logic_chip:
            warning = Gtk.Label(
                label="This chip is not a logic IC and cannot be tested.",
                xalign=0.0,
            )
            warning.add_css_class("warning")
            warning.set_wrap(True)
            self.append(warning)
            self._groups.append(warning)
