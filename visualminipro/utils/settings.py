"""Persistent settings.

Replaces MiniproUI/UserDefaultsExtensions.swift (Visual Minipro 1.5.8) with a
JSON file under $XDG_CONFIG_HOME, since Linux has no UserDefaults.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .paths import config_dir

logger = logging.getLogger("visualminipro.settings")

_FAVORITE_CHIPS_KEY = "favoriteChips"
_LIBUSB_DEBUG_LOGGING_KEY = "libusbDebugLogging"
_USE_LEGACY_INFOIC_KEY = "useLegacyInfoIC"
# Linux addition: path to the minipro+ MAME ROM database. Empty means
# "auto-detect from the usual locations".
_MAME_DATABASE_PATH_KEY = "mameDatabasePath"

_DEFAULTS: dict[str, Any] = {
    _FAVORITE_CHIPS_KEY: [],
    _LIBUSB_DEBUG_LOGGING_KEY: False,
    _USE_LEGACY_INFOIC_KEY: False,
    _MAME_DATABASE_PATH_KEY: "",
}


class Settings:
    def __init__(self) -> None:
        self._path = config_dir() / "settings.json"
        self._values: dict[str, Any] = dict(_DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            if isinstance(stored, dict):
                self._values.update(stored)
        except FileNotFoundError:
            pass
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read settings from %s: %s", self._path, exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_suffix(".json.tmp")
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self._values, handle, indent=2)
            temporary.replace(self._path)
        except OSError as exc:
            logger.warning("Could not write settings to %s: %s", self._path, exc)

    @property
    def favorite_chips(self) -> list[str]:
        value = self._values.get(_FAVORITE_CHIPS_KEY, [])
        return list(value) if isinstance(value, list) else []

    @favorite_chips.setter
    def favorite_chips(self, value: list[str]) -> None:
        self._values[_FAVORITE_CHIPS_KEY] = list(value)
        self._save()

    @property
    def libusb_debug_logging(self) -> bool:
        return bool(self._values.get(_LIBUSB_DEBUG_LOGGING_KEY, False))

    @libusb_debug_logging.setter
    def libusb_debug_logging(self, value: bool) -> None:
        self._values[_LIBUSB_DEBUG_LOGGING_KEY] = bool(value)
        self._save()
        apply_libusb_debug_logging(value)

    @property
    def mame_database_path(self) -> str:
        value = self._values.get(_MAME_DATABASE_PATH_KEY, "")
        return value if isinstance(value, str) else ""

    @mame_database_path.setter
    def mame_database_path(self, value: str) -> None:
        self._values[_MAME_DATABASE_PATH_KEY] = value or ""
        self._save()

    @property
    def use_legacy_infoic(self) -> bool:
        return bool(self._values.get(_USE_LEGACY_INFOIC_KEY, False))

    @use_legacy_infoic.setter
    def use_legacy_infoic(self, value: bool) -> None:
        self._values[_USE_LEGACY_INFOIC_KEY] = bool(value)
        self._save()


def apply_libusb_debug_logging(enabled: bool) -> None:
    """LIBUSB_DEBUG is read by libusb inside the minipro child process."""
    if enabled:
        os.environ["LIBUSB_DEBUG"] = "4"
    else:
        os.environ.pop("LIBUSB_DEBUG", None)


settings = Settings()
