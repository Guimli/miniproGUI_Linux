"""Main window.

Port of MiniproUI/ContentView.swift (Visual Minipro 1.5.8): a sidebar of pages
next to a detail area, with the programmer and chip database loaded on start.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..minipro import MiniproAPI, find_minipro
from .about import AboutPage
from .chip_programming import ChipProgrammingPage
from .logic_test import LogicICTestPage
from .model import MiniproModel
from .programmer_info import ProgrammerInfoPage
from .settings_page import SettingsPage
from .tasks import run_async
from .widgets import error_dialog

PAGES = [
    ("chip-programming", "Chip Programming", "media-flash-symbolic"),
    ("logic-ic-test", "Logic IC Test", "application-x-firmware-symbolic"),
    ("programmer-info", "Programmer Info", "computer-chip-symbolic"),
    ("settings", "Settings", "preferences-system-symbolic"),
    ("about", "About Visual Minipro", "help-about-symbolic"),
]


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application):
        super().__init__(
            application=application,
            title="Visual Minipro",
            default_width=1280,
            default_height=820,
        )
        self._model = MiniproModel()

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._pages = {
            "chip-programming": ChipProgrammingPage(self._model, self),
            "logic-ic-test": LogicICTestPage(self._model, self),
            "programmer-info": ProgrammerInfoPage(self._model, self),
            "settings": SettingsPage(self._model, self),
            "about": AboutPage(self._model, self),
        }
        for name, _title, _icon in PAGES:
            self._stack.add_named(self._pages[name], name)

        # Content first: building the sidebar selects a row, whose handler
        # needs the content page to already exist.
        content = self._build_content()
        split_view = Adw.NavigationSplitView(
            sidebar=self._build_sidebar(),
            content=content,
            min_sidebar_width=200,
            max_sidebar_width=260,
        )
        self.set_content(split_view)

        self._status_label.set_label("Detecting programmer…")
        self.refresh()

    def _build_sidebar(self) -> Adw.NavigationPage:
        self._list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("navigation-sidebar")
        self._list_box.connect("row-selected", self._on_page_selected)

        for _name, title, icon_name in PAGES:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.append(Gtk.Image.new_from_icon_name(icon_name))
            box.append(Gtk.Label(label=title, xalign=0.0))
            row.set_child(box)
            self._list_box.append(row)

        self._list_box.select_row(self._list_box.get_row_at_index(0))

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.append(self._list_box)

        self._status_label = Gtk.Label(xalign=0.0)
        self._status_label.add_css_class("dim-label")
        self._status_label.add_css_class("caption")
        self._status_label.set_wrap(True)
        self._status_label.set_margin_top(8)
        self._status_label.set_margin_bottom(8)
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_end(12)
        self._status_label.set_valign(Gtk.Align.END)
        self._status_label.set_vexpand(True)
        sidebar_box.append(self._status_label)

        toolbar = Adw.ToolbarView(content=sidebar_box)
        header = Adw.HeaderBar()
        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.set_tooltip_text("Detect the programmer again")
        refresh_button.connect("clicked", lambda _b: self.refresh())
        header.pack_end(refresh_button)
        toolbar.add_top_bar(header)

        return Adw.NavigationPage(child=toolbar, title="Visual Minipro")

    def _build_content(self) -> Adw.NavigationPage:
        toolbar = Adw.ToolbarView(content=self._stack)
        self._content_header = Adw.HeaderBar()
        toolbar.add_top_bar(self._content_header)
        self._content_page = Adw.NavigationPage(child=toolbar, title="Chip Programming")
        return self._content_page

    def _on_page_selected(self, _list_box: Gtk.ListBox, row) -> None:
        if row is None:
            return
        name, title, _icon = PAGES[row.get_index()]
        self._stack.set_visible_child_name(name)
        self._content_page.set_title(title)

    # -- refresh ---------------------------------------------------------

    def refresh(self) -> None:
        """Detect the programmer and reload its chip database."""
        if find_minipro() is None:
            self._status_label.set_label("minipro not found")
            error_dialog(
                self,
                "minipro not found",
                "The 'minipro' command-line tool is not installed or not on PATH.\n\n"
                "Install it with:\n"
                "  sudo apt install build-essential pkg-config libusb-1.0-0-dev zlib1g-dev\n"
                "  git clone https://gitlab.com/DavidGriffith/minipro.git\n"
                "  cd minipro && make && sudo make install",
            )
            return

        self._status_label.set_label("Detecting programmer…")

        def work():
            return self._model.refresh_blocking()

        def done(result):
            programmer_info, devices = result
            self._model.apply_refresh(programmer_info, devices)
            if programmer_info is None:
                self._status_label.set_label("No programmer detected")
            elif self._model.devices_error is not None:
                self._status_label.set_label(
                    f"{programmer_info.model.value} connected — chip list unavailable"
                )
            else:
                count = len(devices.eeprom_ics) if devices else 0
                self._status_label.set_label(
                    f"{programmer_info.model.value} connected — {count} chips"
                )
            self._load_about_info()

        def failed(exc):
            self._status_label.set_label("Detection failed")
            error_dialog(self, "Could not query the programmer", str(exc))

        run_async(work, done, failed)

    def _load_about_info(self) -> None:
        def work():
            return MiniproAPI.get_visual_minipro_info()

        def done(info):
            self._model.visual_minipro_info = info
            self._pages["about"].rebuild()

        run_async(work, done, lambda _exc: None)
