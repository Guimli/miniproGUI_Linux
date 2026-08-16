"""Filesystem locations, translated from macOS conventions to XDG.

Replaces the Bundle.main / applicationSupportDirectory lookups in
MiniproUI/Utilities/InfoICUtils.swift and AlgorithmXmlUtils.swift
(Visual Minipro 1.5.8).

  macOS                                  Linux
  -------------------------------------  ----------------------------------------
  Bundle.main infoic.xml / logicic.xml    /usr/local/share/minipro/*.xml (minipro)
  ~/Library/Application Support           $XDG_DATA_HOME (~/.local/share)
  UserDefaults                            $XDG_CONFIG_HOME (~/.config)
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "visual-minipro"

# Where `make install` puts minipro's data files, plus the usual packaged spots.
_MINIPRO_SHARE_DIRS = (
    Path("/usr/local/share/minipro"),
    Path("/usr/share/minipro"),
    Path("/usr/local/share"),
    Path("/usr/share"),
)


def data_dir() -> Path:
    """Per-user data: generated algorithm databases live here."""
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_DIR_NAME


def config_dir() -> Path:
    """Per-user configuration: the settings file lives here."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / APP_DIR_NAME


def find_minipro_share_file(*names: str) -> Path | None:
    """Locate a minipro data file (infoic.xml, logicic.xml) by trying each name.

    Names are tried in order so callers can express a preference, e.g. the
    legacy InfoIC database before the current one.
    """
    for name in names:
        for directory in _MINIPRO_SHARE_DIRS:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def logicic_path() -> Path | None:
    return find_minipro_share_file("logicic.xml")
