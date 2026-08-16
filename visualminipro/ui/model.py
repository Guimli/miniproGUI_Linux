"""Shared application state.

Port of the MiniproModel ObservableObject in MiniproUI/ContentView.swift
(Visual Minipro 1.5.8). GObject signals replace @Published properties.
"""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GObject  # noqa: E402

from ..minipro import (
    DeviceDetails,
    LogicICTestResult,
    MiniproAPI,
    ProgrammerInfo,
    ReadOptions,
    SupportedDevices,
    VisualMiniproInfo,
    WriteOptions,
)
from ..utils import (
    MameDatabaseError,
    MameMatch,
    compute_sha1,
    find_by_sha1,
    find_database,
    logicic_path,
    resolve_infoic_path,
    settings,
)


class MiniproModel(GObject.Object):
    __gsignals__ = {
        # Emitted after the programmer and its chip database are (re)loaded.
        "programmer-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "devices-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "buffer-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # Emitted once the SHA1 and MAME lookup for the current buffer are done.
        "buffer-analyzed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self) -> None:
        super().__init__()
        self.programmer_info: Optional[ProgrammerInfo] = None
        self.supported_devices: Optional[SupportedDevices] = None
        self.device_details: Optional[DeviceDetails] = None
        self.logic_ic_details: Optional[DeviceDetails] = None
        self.logic_ic_test_result: Optional[LogicICTestResult] = None
        self.visual_minipro_info: Optional[VisualMiniproInfo] = None
        self.buffer: Optional[bytes] = None
        self.read_options = ReadOptions()
        self.write_options = WriteOptions()
        self.apply_favorite_filter = True
        # Set when the chip database could not be loaded, for display.
        self.devices_error: Optional[Exception] = None
        # Analysis of the current buffer.
        self.buffer_sha1: Optional[str] = None
        self.buffer_source: Optional[str] = None
        self.mame_matches: Optional[list[MameMatch]] = None
        self.mame_error: Optional[Exception] = None
        self.mame_searched = False

    # -- buffer ---------------------------------------------------------

    def set_buffer(self, data: Optional[bytes], source: Optional[str] = None) -> None:
        """Replace the buffer and invalidate its analysis.

        `source` describes where the data came from ("chip AT28C256", a file
        name) purely for display.
        """
        self.buffer = data
        self.buffer_source = source
        self.buffer_sha1 = None
        self.mame_matches = None
        self.mame_error = None
        self.mame_searched = False
        self.emit("buffer-changed")

    def analyze_buffer_blocking(self) -> tuple[Optional[str], Optional[list[MameMatch]], Optional[Exception]]:
        """Hash the buffer and look the hash up in the MAME database.

        Runs on a worker thread: SHA1 over a large NAND dump and the SQLite
        query should never block the UI.
        """
        data = self.buffer
        if data is None:
            return None, None, None

        sha1 = compute_sha1(data)

        database_path = find_database(settings.mame_database_path)
        if database_path is None:
            configured = settings.mame_database_path
            message = (
                f"The MAME database was not found at {configured}."
                if configured
                else "No MAME ROM database found. Set its location in Settings "
                     "(MAME-Embedded-Database builds it as mame_roms.db)."
            )
            return sha1, None, MameDatabaseError(message)

        try:
            return sha1, find_by_sha1(database_path, sha1), None
        except MameDatabaseError as exc:
            return sha1, None, exc

    def apply_analysis(
        self,
        sha1: Optional[str],
        matches: Optional[list[MameMatch]],
        error: Optional[Exception],
    ) -> None:
        self.buffer_sha1 = sha1
        self.mame_matches = matches
        self.mame_error = error
        self.mame_searched = sha1 is not None
        self.emit("buffer-analyzed")

    # -- paths ----------------------------------------------------------

    def infoic_path(self):
        model = self.programmer_info.model if self.programmer_info else None
        return resolve_infoic_path(model, settings.use_legacy_infoic)

    # -- blocking loaders, called from a worker thread -------------------

    def load_programmer_info(self) -> Optional[ProgrammerInfo]:
        """Mirrors `try? await MiniproAPI.getProgrammerInfo()` - absence is not an error."""
        try:
            return MiniproAPI.get_programmer_info()
        except Exception:  # noqa: BLE001
            return None

    def load_supported_devices(self) -> Optional[SupportedDevices]:
        if self.programmer_info is None:
            return None
        infoic = self.infoic_path()
        logicic = logicic_path()
        if infoic is None or logicic is None:
            self.devices_error = FileNotFoundError(
                "minipro's infoic.xml / logicic.xml could not be found in "
                "/usr/local/share/minipro or /usr/share/minipro."
            )
            return None
        try:
            devices = MiniproAPI.get_supported_devices(infoic, logicic)
            self.devices_error = None
            return devices
        except Exception as exc:  # noqa: BLE001
            self.devices_error = exc
            return None

    def refresh_blocking(self) -> tuple[Optional[ProgrammerInfo], Optional[SupportedDevices]]:
        """Load the programmer and its chip list in one worker-thread round trip."""
        self.programmer_info = self.load_programmer_info()
        devices = self.load_supported_devices() if self.programmer_info else None
        return self.programmer_info, devices

    def apply_refresh(
        self,
        programmer_info: Optional[ProgrammerInfo],
        devices: Optional[SupportedDevices],
    ) -> None:
        """Commit a refresh result on the main thread and notify listeners."""
        self.programmer_info = programmer_info
        if devices is not None:
            self.supported_devices = devices
        elif programmer_info is None:
            self.supported_devices = None
        self.emit("programmer-changed")
        self.emit("devices-changed")

    def filter_favorite_chips(self, chips: list[str]) -> list[str]:
        """Favourites are substring matches; an empty result falls back to everything."""
        favorites = [chip.lower() for chip in settings.favorite_chips]
        if not favorites:
            return chips
        filtered = [
            chip for chip in chips
            if any(favorite in chip.lower() for favorite in favorites)
        ]
        return filtered if filtered else chips
