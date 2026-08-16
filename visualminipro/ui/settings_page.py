"""Settings page.

Port of MiniproUI/SettingsView.swift and FavoriteChipsView.swift
(Visual Minipro 1.5.8). UserDefaults is replaced by the JSON-backed Settings.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ..minipro import find_minipro
from ..utils import (
    database_summary,
    find_database,
    legacy_infoic_available,
    logicic_path,
    settings,
)
from ..utils.paths import config_dir, data_dir
from .model import MiniproModel
from .widgets import TabHeader, property_row


class SettingsPage(Gtk.Box):
    def __init__(self, model: MiniproModel, window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._model = model
        self._window = window
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self.append(TabHeader("Settings", "preferences-system-symbolic"))

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroller = Gtk.ScrolledWindow(child=content, vexpand=True)
        self.append(scroller)

        content.append(self._build_favorites_group())
        content.append(self._build_mame_group())
        content.append(self._build_compatibility_group())
        content.append(self._build_diagnostics_group())
        content.append(self._build_locations_group())

    def _build_mame_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="MAME ROM Database",
            description=(
                "After every chip read or file open, the buffer's SHA1 is looked up in "
                "this database to identify known arcade ROMs. Build it with the minipro+ "
                "project's build_mame_database.py."
            ),
        )

        detected = find_database(settings.mame_database_path)
        self._mame_row = Adw.ActionRow(title="Database file")
        self._mame_row.set_subtitle_lines(0)
        self._update_mame_row(detected)

        choose_button = Gtk.Button(label="Select…", valign=Gtk.Align.CENTER)
        choose_button.connect("clicked", self._on_choose_mame_database)
        self._mame_row.add_suffix(choose_button)

        reset_button = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER)
        reset_button.set_tooltip_text("Clear the configured path and auto-detect again")
        reset_button.add_css_class("flat")
        reset_button.connect("clicked", self._on_reset_mame_database)
        self._mame_row.add_suffix(reset_button)

        group.add(self._mame_row)
        return group

    def _update_mame_row(self, database_path) -> None:
        if database_path is None:
            configured = settings.mame_database_path
            self._mame_row.set_subtitle(
                f"Not found at {configured}" if configured
                else "Not found — searched ~/minipro+/mame_roms.db and minipro's share directory"
            )
            return
        try:
            summary = database_summary(database_path)
            self._mame_row.set_subtitle(f"{database_path}\n{summary}")
        except Exception:  # noqa: BLE001
            self._mame_row.set_subtitle(str(database_path))

    def _on_choose_mame_database(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Select the MAME ROM database")
        file_filter = Gtk.FileFilter()
        file_filter.set_name("SQLite database (*.db)")
        file_filter.add_pattern("*.db")
        dialog.set_default_filter(file_filter)

        def on_open(source, result):
            try:
                gfile = source.open_finish(result)
            except GLib.Error:
                return
            settings.mame_database_path = gfile.get_path()
            self._update_mame_row(find_database(settings.mame_database_path))

        dialog.open(self._window, None, on_open)

    def _on_reset_mame_database(self, _button: Gtk.Button) -> None:
        settings.mame_database_path = ""
        self._update_mame_row(find_database(""))

    def _build_favorites_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Favorite Chips",
            description=(
                "Substrings matched against chip names. When the Chip Programming list has "
                "'Favorites only' enabled, it shows just these — unless nothing matches, in "
                "which case the full list is shown."
            ),
        )

        self._favorites_rows_container = Adw.PreferencesGroup()

        entry_row = Adw.EntryRow(title="Add a chip name or substring")
        add_button = Gtk.Button(label="Add", valign=Gtk.Align.CENTER)
        add_button.add_css_class("suggested-action")
        entry_row.add_suffix(add_button)

        def add_favorite(*_args):
            text = entry_row.get_text().strip()
            if not text:
                return
            favorites = settings.favorite_chips
            if text not in favorites:
                settings.favorite_chips = favorites + [text]
                self._rebuild_favorites()
            entry_row.set_text("")

        add_button.connect("clicked", add_favorite)
        entry_row.connect("entry-activated", add_favorite)
        group.add(entry_row)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.append(group)
        box.append(self._favorites_rows_container)
        self._rebuild_favorites()
        return box

    def _rebuild_favorites(self) -> None:
        container = self._favorites_rows_container
        child = container.get_first_child()
        # Adw.PreferencesGroup wraps its rows; rebuild by removing known rows.
        for row in getattr(self, "_favorite_rows", []):
            container.remove(row)
        self._favorite_rows = []

        for chip in settings.favorite_chips:
            row = Adw.ActionRow(title=chip)
            remove_button = Gtk.Button(
                icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER
            )
            remove_button.add_css_class("flat")
            remove_button.set_tooltip_text("Remove")

            def remove(_button, value=chip):
                settings.favorite_chips = [c for c in settings.favorite_chips if c != value]
                self._rebuild_favorites()

            remove_button.connect("clicked", remove)
            row.add_suffix(remove_button)
            container.add(row)
            self._favorite_rows.append(row)

        if not settings.favorite_chips:
            row = Adw.ActionRow(title="No favorites yet")
            row.set_sensitive(False)
            container.add(row)
            self._favorite_rows.append(row)

    def _build_compatibility_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title="Compatibility")
        row = Adw.SwitchRow(
            title="Use legacy InfoIC database",
            subtitle="The T76 always uses the current database.",
            active=settings.use_legacy_infoic,
        )
        if not legacy_infoic_available():
            row.set_sensitive(False)
            row.set_subtitle(
                "No infoic_0.7.4.xml found in minipro's share directory, so the current "
                "database is always used."
            )

        def toggled(switch_row, _param):
            settings.use_legacy_infoic = switch_row.get_active()

        row.connect("notify::active", toggled)
        group.add(row)
        return group

    def _build_diagnostics_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title="Diagnostics")
        row = Adw.SwitchRow(
            title="Enable libusb debug logging",
            subtitle="Sets LIBUSB_DEBUG=4 for minipro; output goes to the application log.",
            active=settings.libusb_debug_logging,
        )

        def toggled(switch_row, _param):
            settings.libusb_debug_logging = switch_row.get_active()

        row.connect("notify::active", toggled)
        group.add(row)
        return group

    def _build_locations_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Locations",
            description="Where this build looks for its tools and data on Debian.",
        )
        group.add(property_row("minipro binary", find_minipro() or "not found"))
        group.add(property_row("InfoIC database", str(self._model.infoic_path() or "not found")))
        group.add(property_row("Logic IC database", str(logicic_path() or "not found")))
        group.add(property_row("Algorithms", str(data_dir())))
        group.add(property_row("Settings file", str(config_dir() / "settings.json")))
        group.add(
            property_row(
                "MAME database", str(find_database(settings.mame_database_path) or "not found")
            )
        )
        return group
