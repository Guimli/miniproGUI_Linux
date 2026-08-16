"""Programmer Info page: identity, warnings, firmware and software bundles.

Port of MiniproUI/ProgrammerInfoView.swift (Visual Minipro 1.5.8), including
FirmwareUpdateSection, SoftwareUpdateSection and UpdateFirmwareButton.

For the T56/T76 the "Install…" action does the whole Xgpro bundle dance:
extract the RAR, identify the firmware, build algorithm.xml from the .alg
files, and only then flash the firmware if the bundle is newer than what the
programmer runs.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ..minipro import MiniproAPI, ProgrammerInfo, ProgressUpdate
from ..minipro.errors import ProgrammerInfoUnavailable
from ..utils import (
    SoftwareBundleVerificationStatus,
    XgproFirmwareUtils,
    XgproSoftwareExtractor,
    needs_algorithm_installation,
    resolve_algorithm_xml_path,
)
from .model import MiniproModel
from .tasks import on_main_thread, run_async
from .widgets import (
    FIRMWARE_HELP_URL,
    SOFTWARE_BUNDLE_HELP_URL,
    ProgressDialog,
    TabHeader,
    error_dialog,
    programmer_not_connected_banner,
    property_row,
)

_STATUS_TEXT = {
    SoftwareBundleVerificationStatus.CHECKSUM_MATCH: (
        "Checksum verified.", "success", "emblem-ok-symbolic"
    ),
    SoftwareBundleVerificationStatus.CHECKSUM_NOT_AVAILABLE: (
        "Checksum verification was not possible for this bundle.", "warning",
        "dialog-warning-symbolic",
    ),
    SoftwareBundleVerificationStatus.CHECKSUM_MISMATCH: (
        "Bundle checksum does not match expected value.", "error", "dialog-error-symbolic"
    ),
    SoftwareBundleVerificationStatus.PROGRAMMER_MODEL_MISMATCH: (
        "This bundle targets a different programmer model.", "error", "dialog-error-symbolic"
    ),
    SoftwareBundleVerificationStatus.VERIFICATION_FAILED: (
        "Failed to verify bundle checksum.", "error", "dialog-error-symbolic"
    ),
}


class ProgrammerInfoPage(Gtk.Box):
    def __init__(self, model: MiniproModel, window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._model = model
        self._window = window
        self._selected_file: Optional[Path] = None
        self._checksum_status: Optional[SoftwareBundleVerificationStatus] = None
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self._header = TabHeader("Programmer: Unknown", "computer-chip-symbolic")
        self.append(self._header)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroller = Gtk.ScrolledWindow(child=self._content, vexpand=True)
        self.append(scroller)

        model.connect("programmer-changed", lambda _m: self.rebuild())
        self.rebuild()

    # -- rendering -------------------------------------------------------

    def rebuild(self) -> None:
        child = self._content.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._content.remove(child)
            child = nxt

        info = self._model.programmer_info
        if info is None:
            self._header.set_caption("Programmer: Unknown")
            self._header.set_secondary_caption(None)
            self._content.append(programmer_not_connected_banner())
            return

        self._header.set_caption(f"Programmer: Minipro {info.model.value}")
        self._header.set_secondary_caption(info.firmware_version)

        group = Adw.PreferencesGroup()
        group.add(property_row("Model", info.model.value))
        group.add(property_row("Firmware Version", info.firmware_version))
        group.add(property_row("Device Code", info.device_code))
        group.add(property_row("Serial Number", info.serial_number))
        group.add(property_row("Manufactured Date", info.date_manufactured))
        group.add(property_row("USB Speed", info.usb_speed))
        group.add(property_row("Supply Voltage", info.supply_voltage))
        self._content.append(group)

        if info.warnings:
            warnings_group = Adw.PreferencesGroup(title="Warnings")
            for warning in info.warnings:
                row = Adw.ActionRow(title=warning)
                row.set_title_lines(0)
                icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
                icon.add_css_class("warning")
                row.add_prefix(icon)
                warnings_group.add(row)
            self._content.append(warnings_group)

        if info.model.supports_firmware_update:
            if info.model.is_algo_based:
                self._content.append(self._build_software_section(info))
            else:
                self._content.append(self._build_firmware_section())

    def _build_firmware_section(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Firmware Update",
            description="Select the vendor firmware .dat file for this programmer.",
        )
        group.add(self._build_file_row("Select Firmware…", ["dat"], "Firmware file"))
        group.add(self._build_action_row("Update…"))
        group.add(self._build_link_row("Learn more about downloading firmware", FIRMWARE_HELP_URL))
        return group

    def _build_software_section(self, info: ProgrammerInfo) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Software Bundle Installation",
            description=(
                f"The {info.model.value} loads its programming algorithms from the Xgpro "
                "software bundle. Select the vendor .rar archive."
            ),
        )

        if needs_algorithm_installation(info):
            firmware_version = info.firmware_version_number()
            matching = (
                XgproFirmwareUtils.get_software_name(info.model, firmware_version)
                if firmware_version is not None
                else None
            )
            latest = XgproFirmwareUtils.get_latest_software_name(info.model)
            if matching:
                text = (
                    f"Missing algorithms for installed firmware. Matching bundle: {matching}. "
                    "Installing any other bundle may update the programmer firmware."
                )
            elif latest:
                text = (
                    "Missing algorithms for installed firmware. Install software matching your "
                    f"firmware version, or the latest known version: {latest}."
                )
            else:
                text = (
                    "Missing algorithms for installed firmware. Install software matching your "
                    "firmware version."
                )
            row = Adw.ActionRow(title=text)
            row.set_title_lines(0)
            icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            icon.add_css_class("warning")
            row.add_prefix(icon)
            group.add(row)

        group.add(self._build_file_row("Select Bundle…", ["rar"], "Software Bundle file"))
        group.add(self._build_action_row("Install…"))
        group.add(
            self._build_link_row(
                "Learn more about Software Bundles for T56 and T76 programmers",
                SOFTWARE_BUNDLE_HELP_URL,
            )
        )
        return group

    def _build_file_row(self, button_label: str, extensions: list[str], title: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=title, subtitle="N/A")
        row.set_subtitle_lines(0)
        button = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
        button.connect("clicked", lambda _b: self._choose_file(extensions, row))
        row.add_suffix(button)
        self._file_row = row
        return row

    def _build_action_row(self, button_label: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title="")
        self._status_label = Gtk.Label(xalign=0.0, label="")
        self._status_label.set_wrap(True)
        row.set_title("Ready when a file is selected")
        row.set_title_lines(0)
        self._status_icon = Gtk.Image()
        self._status_icon.set_visible(False)
        row.add_prefix(self._status_icon)

        self._action_button = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
        self._action_button.add_css_class("destructive-action")
        self._action_button.set_sensitive(False)
        self._action_button.connect("clicked", lambda _b: self._on_action_clicked())
        row.add_suffix(self._action_button)
        self._action_row = row
        return row

    def _build_link_row(self, label: str, url: str) -> Adw.ActionRow:
        row = Adw.ActionRow(title=label)
        row.set_title_lines(0)
        button = Gtk.LinkButton(uri=url, label="Open", valign=Gtk.Align.CENTER)
        row.add_suffix(button)
        return row

    # -- file selection --------------------------------------------------

    def _choose_file(self, extensions: list[str], row: Adw.ActionRow) -> None:
        dialog = Gtk.FileDialog(title="Select file")
        file_filter = Gtk.FileFilter()
        file_filter.set_name(" / ".join(f"*.{extension}" for extension in extensions))
        for extension in extensions:
            file_filter.add_pattern(f"*.{extension}")
            file_filter.add_pattern(f"*.{extension.upper()}")
        dialog.set_default_filter(file_filter)

        def on_open(source, result):
            try:
                gfile = source.open_finish(result)
            except GLib.Error:
                return
            path = Path(gfile.get_path())
            self._selected_file = path
            row.set_subtitle(str(path))
            self._update_checksum_status(path)
            self._action_button.set_sensitive(True)

        dialog.open(self._window, None, on_open)

    def _update_checksum_status(self, path: Path) -> None:
        if path.suffix.lower() != ".rar":
            self._checksum_status = None
            self._status_icon.set_visible(False)
            self._action_row.set_title("Ready to update firmware")
            return

        info = self._model.programmer_info
        status = XgproFirmwareUtils.verify_software_bundle(
            path, info.model if info else None
        )
        self._checksum_status = status
        text, css_class, icon_name = _STATUS_TEXT[status]
        self._action_row.set_title(text)
        self._status_icon.set_from_icon_name(icon_name)
        for candidate in ("success", "warning", "error"):
            self._status_icon.remove_css_class(candidate)
        self._status_icon.add_css_class(css_class)
        self._status_icon.set_visible(True)

    # -- actions ---------------------------------------------------------

    def _on_action_clicked(self) -> None:
        path = self._selected_file
        if path is None:
            return

        if path.suffix.lower() == ".rar":
            self._confirm_and_run(
                heading="Install software bundle?",
                body=(
                    f"{path.name} will be extracted and its programming algorithms installed.\n\n"
                    "If the bundle firmware differs from the installed firmware, the programmer "
                    "will also be reflashed. Do not unplug it during the process."
                ),
                confirm_label="Install",
                action=lambda: self._process_rar_firmware(path),
            )
        else:
            self._confirm_and_run(
                heading="Flash programmer firmware?",
                body=(
                    f"{path.name} will be written to the programmer's firmware.\n\n"
                    "Interrupting this or using the wrong file can leave the programmer "
                    "unusable. Do not unplug it during the update."
                ),
                confirm_label="Flash Firmware",
                action=lambda: self._update_firmware(path),
            )

    def _confirm_and_run(self, heading: str, body: str, confirm_label: str, action) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("go", confirm_label)
        dialog.set_response_appearance("go", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, response: action() if response == "go" else None)
        dialog.present(self._window)

    def _refresh_programmer_info(self) -> None:
        def work():
            return self._model.refresh_blocking()

        def done(result):
            programmer_info, devices = result
            self._model.apply_refresh(programmer_info, devices)

        run_async(work, done, lambda _exc: None)

    # -- plain firmware flash ---------------------------------------------

    def _update_firmware(self, path: Path) -> None:
        progress = ProgressDialog(self._window, "Updating firmware…")
        progress.present()

        def on_progress(update: ProgressUpdate) -> None:
            on_main_thread(progress.set_progress, update.operation, update.percentage)

        def work():
            MiniproAPI.update_firmware(str(path), on_progress)

        def done(_result):
            progress.close()
            self._selected_file = None
            self._refresh_programmer_info()

        def failed(exc: Exception):
            progress.close()
            error_dialog(self._window, "Firmware Update Failed", str(exc))
            self._refresh_programmer_info()

        run_async(work, done, failed)

    # -- Xgpro bundle install ----------------------------------------------

    def _process_rar_firmware(self, path: Path) -> None:
        progress = ProgressDialog(self._window, "Extracting firmware…")
        progress.present()

        def on_progress(update: ProgressUpdate) -> None:
            on_main_thread(progress.set_progress, update.operation, update.percentage)

        def work():
            output_directory = Path(tempfile.gettempdir()) / f"xgpro-firmware-{uuid.uuid4()}"
            try:
                XgproSoftwareExtractor.extract_rar(path, output_directory)
                on_main_thread(progress.set_progress, "Extracting Files", 100)

                firmware_info = XgproFirmwareUtils.get_firmware_info(output_directory)

                programmer_info = self._model.programmer_info
                if programmer_info is None:
                    raise ProgrammerInfoUnavailable()
                if firmware_info.programmer_model != programmer_info.model:
                    raise ValueError(
                        "Selected software bundle does not match the connected programmer "
                        f"({firmware_info.programmer_model.value} bundle, "
                        f"{programmer_info.model.value} connected)."
                    )

                on_main_thread(progress.set_label, "Preparing Algorithms…")
                algorithms_xml = XgproFirmwareUtils.create_algorithm_xml(
                    output_directory, firmware_info.programmer_model, on_progress
                )

                algorithms_path = resolve_algorithm_xml_path(
                    firmware_info.programmer_model, firmware_info.firmware_version
                )
                algorithms_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = algorithms_path.with_suffix(".xml.tmp")
                temporary.write_text(algorithms_xml, encoding="utf-8")
                temporary.replace(algorithms_path)

                installed_version = programmer_info.firmware_version_number()
                if installed_version is None:
                    raise ProgrammerInfoUnavailable()

                # Only reflash when the bundle carries a different firmware.
                if installed_version != firmware_info.firmware_version:
                    on_main_thread(progress.set_label, "Updating firmware…")
                    firmware_file = output_directory / firmware_info.file_name
                    MiniproAPI.update_firmware(str(firmware_file), on_progress)
                return algorithms_path
            finally:
                shutil.rmtree(output_directory, ignore_errors=True)

        def done(algorithms_path):
            progress.close()
            self._selected_file = None
            dialog = Adw.AlertDialog(
                heading="Software Bundle Installed",
                body=f"Programming algorithms were written to:\n{algorithms_path}",
            )
            dialog.add_response("ok", "OK")
            dialog.present(self._window)
            self._refresh_programmer_info()

        def failed(exc: Exception):
            progress.close()
            error_dialog(self._window, "Software Install Failed", str(exc))
            self._refresh_programmer_info()

        run_async(work, done, failed)
