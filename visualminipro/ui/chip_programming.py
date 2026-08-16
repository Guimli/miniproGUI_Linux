"""Chip Programming page: read and write EEPROM/flash contents.

Port of MiniproUI/ChipProgrammingView.swift, ReadChipView.swift and
WriteChipView.swift (Visual Minipro 1.5.8).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from ..minipro import MiniproAPI, ProgressUpdate, ReadOptions, WriteOptions
from ..utils import (
    XgproFirmwareUtils,
    algorithm_xml_path_if_needed,
    needs_algorithm_installation,
)
from .device_details import DeviceDetailsPanel
from .hex_view import BinaryDataView
from .mame_view import MameResultsView
from .model import MiniproModel
from .tasks import on_main_thread, run_async
from .widgets import (
    ProgressDialog,
    SearchableList,
    TabHeader,
    error_dialog,
    format_byte_count,
    missing_algorithms_banner,
    option_toggle_row,
    programmer_not_connected_banner,
)


class ChipProgrammingPage(Gtk.Box):
    def __init__(self, model: MiniproModel, window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._model = model
        self._window = window
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self._header = TabHeader("Selected Chip: None", "media-flash-symbolic")
        self.append(self._header)

        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        columns.set_vexpand(True)
        self.append(columns)

        columns.append(self._build_buffer_column())
        columns.append(self._build_action_column())
        columns.append(self._build_chip_column())

        model.connect("programmer-changed", lambda _m: self._sync_state())
        model.connect("devices-changed", lambda _m: self._sync_devices())
        model.connect("buffer-changed", lambda _m: self._sync_buffer())
        model.connect("buffer-analyzed", lambda _m: self._sync_analysis())
        self._sync_state()

    # -- construction ---------------------------------------------------

    def _build_buffer_column(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_hexpand(True)
        # Wide enough for a full 16-byte row plus its ASCII column.
        box.set_size_request(600, -1)

        # Buffer identity, shared by both tabs: size and SHA1 of what is loaded.
        info_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._size_label = Gtk.Label(xalign=0.0, label="No data loaded")
        self._size_label.add_css_class("heading")
        info_bar.append(self._size_label)

        # Shown in full and selectable - it is the value you paste into a ROM
        # database or a bug report, so it must never be elided.
        self._sha1_label = Gtk.Label(xalign=0.0, label="", selectable=True)
        self._sha1_label.add_css_class("monospace")
        info_bar.append(self._sha1_label)

        self._source_label = Gtk.Label(xalign=0.0, label="")
        self._source_label.add_css_class("dim-label")
        self._source_label.add_css_class("caption")
        self._source_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        self._source_label.set_hexpand(True)
        info_bar.append(self._source_label)
        box.append(info_bar)

        self._hex_view = BinaryDataView()
        self._mame_view = MameResultsView()

        self._buffer_stack = Adw.ViewStack()
        self._buffer_stack.add_titled_with_icon(
            self._hex_view, "hex", "Hex View", "view-list-symbolic"
        )
        self._buffer_stack.add_titled_with_icon(
            self._mame_view, "mame", "MAME Database", "system-search-symbolic"
        )
        self._buffer_stack.set_vexpand(True)

        switcher = Adw.ViewSwitcher(
            stack=self._buffer_stack,
            policy=Adw.ViewSwitcherPolicy.WIDE,
            halign=Gtk.Align.START,
        )
        box.append(switcher)

        frame = Gtk.Frame(child=self._buffer_stack)
        frame.set_vexpand(True)
        box.append(frame)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        open_button = Gtk.Button(label="Open File…")
        open_button.connect("clicked", self._on_open_file)
        buttons.append(open_button)

        self._save_button = Gtk.Button(label="Save File…")
        self._save_button.connect("clicked", self._on_save_file)
        self._save_button.set_sensitive(False)
        buttons.append(self._save_button)

        self._clear_button = Gtk.Button(label="Clear")
        self._clear_button.connect("clicked", lambda _b: self._model.set_buffer(None))
        self._clear_button.set_sensitive(False)
        buttons.append(self._clear_button)
        box.append(buttons)
        return box

    def _build_action_column(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_valign(Gtk.Align.CENTER)

        self._read_button = Gtk.Button(label="◀◀  Read")
        self._read_button.set_tooltip_text("Read the chip contents into the buffer")
        self._read_button.add_css_class("suggested-action")
        self._read_button.connect("clicked", self._on_read_clicked)
        box.append(self._read_button)

        self._write_button = Gtk.Button(label="Write  ▶▶")
        self._write_button.set_tooltip_text("Write the buffer to the chip")
        self._write_button.add_css_class("destructive-action")
        self._write_button.connect("clicked", self._on_write_clicked)
        box.append(self._write_button)

        self._read_button.set_sensitive(False)
        self._write_button.set_sensitive(False)
        return box

    def _build_chip_column(self) -> Gtk.Widget:
        self._chip_stack = Gtk.Stack()
        self._chip_stack.set_size_request(380, -1)
        self._chip_stack.set_hexpand(True)

        self._not_connected = programmer_not_connected_banner()
        not_connected_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        not_connected_box.append(self._not_connected)
        self._chip_stack.add_named(not_connected_box, "not-connected")

        self._missing_algorithms_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._chip_stack.add_named(self._missing_algorithms_box, "missing-algorithms")

        self._chip_list = SearchableList(
            on_selection_changed=self._on_chip_selected,
            show_filter_toggle=True,
            additional_filter=self._model.filter_favorite_chips,
        )
        self._chip_list.set_vexpand(True)
        self._chip_list.set_size_request(-1, 260)

        self._details_panel = DeviceDetailsPanel()
        details_scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            child=self._details_panel,
            vexpand=True,
        )

        # A draggable split so long chip lists and long detail lists can each
        # be given room, rather than the details squeezing the list flat.
        chooser = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        chooser.set_start_child(self._chip_list)
        chooser.set_end_child(details_scroller)
        chooser.set_resize_start_child(True)
        chooser.set_resize_end_child(True)
        chooser.set_shrink_start_child(False)
        chooser.set_position(320)
        self._chip_stack.add_named(chooser, "chooser")

        return self._chip_stack

    # -- state ----------------------------------------------------------

    def _sync_state(self) -> None:
        info = self._model.programmer_info
        if info is None:
            self._chip_stack.set_visible_child_name("not-connected")
        elif needs_algorithm_installation(info):
            self._populate_missing_algorithms()
            self._chip_stack.set_visible_child_name("missing-algorithms")
        else:
            self._chip_stack.set_visible_child_name("chooser")
        self._sync_buttons()

    def _populate_missing_algorithms(self) -> None:
        child = self._missing_algorithms_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._missing_algorithms_box.remove(child)
            child = nxt

        info = self._model.programmer_info
        detail = ""
        if info is not None:
            firmware_version = info.firmware_version_number()
            if firmware_version is not None:
                matching = XgproFirmwareUtils.get_software_name(info.model, firmware_version)
                latest = XgproFirmwareUtils.get_latest_software_name(info.model)
                if matching:
                    detail = (
                        f"Missing algorithms for installed firmware. Matching bundle: {matching}\n"
                        "Installing any other bundle may update the programmer firmware."
                    )
                elif latest:
                    detail = (
                        "Missing algorithms for installed firmware. Install software matching "
                        f"your firmware version, or the latest known version: {latest}."
                    )
                else:
                    detail = (
                        "Missing algorithms for installed firmware. Install software matching "
                        "your firmware version."
                    )
        self._missing_algorithms_box.append(missing_algorithms_banner(detail))

    def _sync_devices(self) -> None:
        devices = self._model.supported_devices
        self._chip_list.set_items(devices.eeprom_ics if devices else [])

    def _sync_buffer(self) -> None:
        buffer = self._model.buffer
        self._hex_view.set_data(buffer)
        self._save_button.set_sensitive(buffer is not None)
        self._clear_button.set_sensitive(buffer is not None)
        self._sync_buttons()

        if buffer is None:
            self._size_label.set_label("No data loaded")
            self._sha1_label.set_label("")
            self._source_label.set_label("")
            self._mame_view.show_idle()
            return

        source = self._model.buffer_source
        self._size_label.set_label(format_byte_count(len(buffer)))
        self._source_label.set_label(f"— {source}" if source else "")
        self._source_label.set_tooltip_text(source or "")
        self._sha1_label.set_label("SHA1: computing…")
        self._mame_view.show_searching()
        self._start_analysis()

    def _start_analysis(self) -> None:
        """Hash the buffer and search MAME, off the main loop."""

        def work():
            return self._model.analyze_buffer_blocking()

        def done(outcome):
            sha1, matches, error = outcome
            self._model.apply_analysis(sha1, matches, error)

        def failed(exc: Exception):
            self._model.apply_analysis(None, None, exc)

        run_async(work, done, failed)

    def _sync_analysis(self) -> None:
        sha1 = self._model.buffer_sha1
        self._sha1_label.set_label(f"SHA1: {sha1}" if sha1 else "")
        if sha1:
            self._sha1_label.set_tooltip_text(sha1)

        if self._model.buffer is None:
            self._mame_view.show_idle()
        elif self._model.mame_error is not None:
            self._mame_view.show_error(self._model.mame_error)
        elif self._model.mame_matches is not None:
            self._mame_view.show_matches(self._model.mame_matches)

    def _sync_buttons(self) -> None:
        details = self._model.device_details
        usable = (
            details is not None
            and not details.is_logic_chip
            and self._model.programmer_info is not None
            and not needs_algorithm_installation(self._model.programmer_info)
        )
        self._read_button.set_sensitive(bool(usable))
        self._write_button.set_sensitive(bool(usable) and self._model.buffer is not None)
        self._header.set_caption(f"Selected Chip: {details.name if details else 'None'}")

    # -- chip selection --------------------------------------------------

    def _on_chip_selected(self, device: Optional[str]) -> None:
        if device is None or self._model.programmer_info is None:
            self._model.device_details = None
            self._details_panel.set_details(None)
            self._sync_buttons()
            return

        infoic = self._model.infoic_path()
        if infoic is None:
            return

        def work():
            return MiniproAPI.get_device_details(device, infoic)

        def done(details):
            self._model.device_details = details
            self._details_panel.set_details(details)
            self._sync_buttons()

        def failed(_exc):
            self._model.device_details = None
            self._details_panel.set_details(None)
            self._sync_buttons()

        run_async(work, done, failed)

    # -- file handling ---------------------------------------------------

    def _on_open_file(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title="Open binary file")

        def on_open(source, result):
            try:
                gfile = source.open_finish(result)
            except GLib.Error:
                return  # cancelled
            path = Path(gfile.get_path())
            try:
                data = path.read_bytes()
            except OSError as exc:
                error_dialog(self._window, "Could not open file", str(exc))
                return
            self._model.set_buffer(data, source=path.name)

        dialog.open(self._window, None, on_open)

    def _on_save_file(self, _button: Gtk.Button) -> None:
        if self._model.buffer is None:
            return
        dialog = Gtk.FileDialog(title="Save buffer")
        device = self._model.device_details
        dialog.set_initial_name(f"{device.name if device else 'dump'}.bin")

        def on_save(source, result):
            try:
                gfile = source.save_finish(result)
            except GLib.Error:
                return  # cancelled
            try:
                Path(gfile.get_path()).write_bytes(self._model.buffer or b"")
            except OSError as exc:
                error_dialog(self._window, "Could not save file", str(exc))

        dialog.save(self._window, None, on_save)

    # -- read ------------------------------------------------------------

    def _on_read_clicked(self, _button: Gtk.Button) -> None:
        details = self._model.device_details
        if details is None:
            return

        options = self._model.read_options
        dialog = Adw.AlertDialog(
            heading="Read Options",
            body=f"Read the contents of {details.name} into the buffer.",
        )
        group = Adw.PreferencesGroup()
        ignore_id_row = option_toggle_row(
            "Ignore chip ID mismatch", options.ignore_chip_id_mismatch, True
        )
        group.add(ignore_id_row)
        dialog.set_extra_child(group)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("read", "Read")
        dialog.set_response_appearance("read", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("read")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response != "read":
                return
            self._model.read_options = ReadOptions(
                ignore_chip_id_mismatch=ignore_id_row.get_active()
            )
            self._start_read(details.name)

        dialog.connect("response", on_response)
        dialog.present(self._window)

    def _start_read(self, device: str) -> None:
        infoic = self._model.infoic_path()
        if infoic is None:
            error_dialog(
                self._window, "Reading Chip Contents Failed", "infoic.xml could not be found."
            )
            return
        algorithms = algorithm_xml_path_if_needed(self._model.programmer_info)
        progress = ProgressDialog(self._window, "Reading Chip Contents…")
        progress.present()

        def on_progress(update: ProgressUpdate) -> None:
            on_main_thread(progress.set_progress, update.operation, update.percentage)

        def work():
            return MiniproAPI.read(
                device=device,
                algorithm_xml_path=algorithms,
                read_options=self._model.read_options,
                infoic_path=infoic,
                progress_update=on_progress,
            )

        def done(data: bytes):
            progress.close()
            self._model.set_buffer(data, source=f"read from {device}")

        def failed(exc: Exception):
            progress.close()
            error_dialog(self._window, "Reading Chip Contents Failed", str(exc))

        run_async(work, done, failed)

    # -- write -----------------------------------------------------------

    def _on_write_clicked(self, _button: Gtk.Button) -> None:
        details = self._model.device_details
        buffer = self._model.buffer
        if details is None or buffer is None:
            return

        options = self._model.write_options
        dialog = Adw.AlertDialog(
            heading="Write Options",
            body=(
                f"Write {len(buffer):,} bytes to {details.name}. "
                "This overwrites the chip contents."
            ).replace(",", " "),
        )
        group = Adw.PreferencesGroup()
        rows = {
            "ignore_file_size_mismatch": option_toggle_row(
                "Ignore file size mismatch", options.ignore_file_size_mismatch, True
            ),
            "ignore_chip_id_mismatch": option_toggle_row(
                "Ignore chip ID mismatch", options.ignore_chip_id_mismatch, True
            ),
            "skip_verification": option_toggle_row(
                "Skip verification after writing", options.skip_verification, True
            ),
            "unprotect_before_write": option_toggle_row(
                "Unprotect chip before writing", options.unprotect_before_write, False
            ),
            "protect_after_write": option_toggle_row(
                "Protect chip after writing", options.protect_after_write, False
            ),
        }
        for row in rows.values():
            group.add(row)
        dialog.set_extra_child(group)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("write", "Write")
        dialog.set_response_appearance("write", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dialog, response):
            if response != "write":
                return
            self._model.write_options = WriteOptions(
                **{key: row.get_active() for key, row in rows.items()}
            )
            self._start_write(details.name, buffer)

        dialog.connect("response", on_response)
        dialog.present(self._window)

    def _start_write(self, device: str, buffer: bytes) -> None:
        infoic = self._model.infoic_path()
        if infoic is None:
            error_dialog(self._window, "Write Failure", "infoic.xml could not be found.")
            return
        algorithms = algorithm_xml_path_if_needed(self._model.programmer_info)
        progress = ProgressDialog(self._window, "Writing Chip Contents…")
        progress.present()

        def on_progress(update: ProgressUpdate) -> None:
            # minipro reads the chip back to verify, so a "Reading" phase here
            # means verification has started.
            if "Reading" in update.operation:
                on_main_thread(progress.set_label, "Verifying Data…")
            on_main_thread(progress.set_progress, update.operation, update.percentage)

        def work():
            MiniproAPI.write(
                device=device,
                data=buffer,
                algorithm_xml_path=algorithms,
                write_options=self._model.write_options,
                infoic_path=infoic,
                progress_update=on_progress,
            )

        def done(_result):
            progress.close()
            toast = Adw.AlertDialog(heading="Write Complete", body=f"{device} written successfully.")
            toast.add_response("ok", "OK")
            toast.present(self._window)

        def failed(exc: Exception):
            progress.close()
            error_dialog(self._window, "Write Failure", str(exc))

        run_async(work, done, failed)
