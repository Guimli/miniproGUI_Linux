"""Logic IC Test page: 74xx/40xx testing.

Port of MiniproUI/LogicICTestView.swift and LogicICTestResultView.swift
(Visual Minipro 1.5.8).
"""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..minipro import LogicICTestResult, MiniproAPI
from ..utils import algorithm_xml_path_if_needed, needs_algorithm_installation
from .device_details import DeviceDetailsPanel
from .model import MiniproModel
from .tasks import run_async
from .widgets import (
    SearchableList,
    TabHeader,
    error_dialog,
    missing_algorithms_banner,
    programmer_not_connected_banner,
)


class LogicICTestPage(Gtk.Box):
    def __init__(self, model: MiniproModel, window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._model = model
        self._window = window
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self._header = TabHeader("Selected Logic IC: None", "application-x-firmware-symbolic")
        self.append(self._header)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self.append(self._stack)

        not_connected = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        not_connected.append(programmer_not_connected_banner())
        self._stack.add_named(not_connected, "not-connected")

        self._missing_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._missing_box.append(missing_algorithms_banner())
        self._stack.add_named(self._missing_box, "missing-algorithms")

        self._stack.add_named(self._build_tester(), "tester")

        model.connect("programmer-changed", lambda _m: self._sync_state())
        model.connect("devices-changed", lambda _m: self._sync_devices())
        self._sync_state()

    def _build_tester(self) -> Gtk.Widget:
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self._chip_list = SearchableList(on_selection_changed=self._on_chip_selected)
        self._chip_list.set_size_request(300, -1)
        columns.append(self._chip_list)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.set_hexpand(True)

        self._details_panel = DeviceDetailsPanel(expect_logic_chip=True)
        right.append(self._details_panel)

        self._test_button = Gtk.Button(label="Test")
        self._test_button.add_css_class("suggested-action")
        self._test_button.set_halign(Gtk.Align.START)
        self._test_button.set_sensitive(False)
        self._test_button.connect("clicked", self._on_test_clicked)
        right.append(self._test_button)

        self._result_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._result_box.set_vexpand(True)
        scroller = Gtk.ScrolledWindow(child=self._result_box, vexpand=True)
        right.append(scroller)

        columns.append(right)
        return columns

    # -- state ----------------------------------------------------------

    def _sync_state(self) -> None:
        info = self._model.programmer_info
        if info is None:
            self._stack.set_visible_child_name("not-connected")
        elif needs_algorithm_installation(info):
            self._stack.set_visible_child_name("missing-algorithms")
        else:
            self._stack.set_visible_child_name("tester")

    def _sync_devices(self) -> None:
        devices = self._model.supported_devices
        self._chip_list.set_items(devices.logic_ics if devices else [])

    def _on_chip_selected(self, device: Optional[str]) -> None:
        self._clear_results()
        self._model.logic_ic_test_result = None
        if device is None or self._model.programmer_info is None:
            self._model.logic_ic_details = None
            self._details_panel.set_details(None)
            self._test_button.set_sensitive(False)
            self._header.set_caption("Selected Logic IC: None")
            return

        infoic = self._model.infoic_path()
        if infoic is None:
            return

        def work():
            return MiniproAPI.get_device_details(device, infoic)

        def done(details):
            self._model.logic_ic_details = details
            self._details_panel.set_details(details)
            self._test_button.set_sensitive(details.is_logic_chip)
            self._header.set_caption(f"Selected Logic IC: {details.name}")

        def failed(_exc):
            self._model.logic_ic_details = None
            self._details_panel.set_details(None)
            self._test_button.set_sensitive(False)
            self._header.set_caption("Selected Logic IC: None")

        run_async(work, done, failed)

    # -- testing ---------------------------------------------------------

    def _on_test_clicked(self, _button: Gtk.Button) -> None:
        details = self._model.logic_ic_details
        if details is None:
            return
        algorithms = algorithm_xml_path_if_needed(self._model.programmer_info)
        self._test_button.set_sensitive(False)
        self._clear_results()

        def work():
            return MiniproAPI.test_logic_ic(details.name, algorithms)

        def done(result: LogicICTestResult):
            self._test_button.set_sensitive(True)
            self._model.logic_ic_test_result = result
            self._show_result(result)

        def failed(exc: Exception):
            self._test_button.set_sensitive(True)
            self._model.logic_ic_test_result = None
            error_dialog(self._window, "Logic IC Test Error", str(exc))

        run_async(work, done, failed)

    def _clear_results(self) -> None:
        child = self._result_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._result_box.remove(child)
            child = nxt

    def _show_result(self, result: LogicICTestResult) -> None:
        self._clear_results()

        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if result.is_success:
            icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            icon.add_css_class("success")
            label = Gtk.Label(label=f"{result.device} passed", xalign=0.0)
            label.add_css_class("success")
        else:
            icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
            icon.add_css_class("error")
            label = Gtk.Label(
                label=f"{result.device} failed: {result.num_errors} errors encountered",
                xalign=0.0,
            )
            label.add_css_class("error")
        label.add_css_class("heading")
        banner.append(icon)
        banner.append(label)
        self._result_box.append(banner)

        if not result.test_vectors:
            return

        caption = Gtk.Label(
            label="Test vectors — a pin marked with '-' did not match the expected level.",
            xalign=0.0,
        )
        caption.add_css_class("dim-label")
        caption.add_css_class("caption")
        caption.set_wrap(True)
        self._result_box.append(caption)

        grid = Gtk.Grid(column_spacing=6, row_spacing=2)
        grid.add_css_class("monospace")
        for row_index, vector in enumerate(result.test_vectors):
            index_label = Gtk.Label(label=f"{row_index + 1:>4}", xalign=1.0)
            index_label.add_css_class("dim-label")
            grid.attach(index_label, 0, row_index, 1, 1)
            for column_index, pin in enumerate(vector):
                pin_label = Gtk.Label(label=pin, xalign=0.5)
                if pin.endswith("-"):
                    pin_label.add_css_class("error")
                grid.attach(pin_label, column_index + 1, row_index, 1, 1)
        self._result_box.append(grid)
