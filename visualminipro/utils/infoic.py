"""InfoIC database resolution.

Port of MiniproUI/Utilities/InfoICUtils.swift (Visual Minipro 1.5.8).

The T76 always uses the current database - the legacy 0.7.4 database predates
it. On Linux the files come from minipro's share directory rather than the app
bundle, and the legacy database is only offered when it is actually present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..minipro.model import ProgrammerModel
from .paths import find_minipro_share_file


def resolve_infoic_path(
    programmer_model: Optional[ProgrammerModel], use_legacy_infoic: bool = False
) -> Optional[Path]:
    if use_legacy_infoic and programmer_model != ProgrammerModel.T76:
        # Prefer the legacy database, but fall back so a missing file is not fatal.
        return find_minipro_share_file("infoic_0.7.4.xml", "infoic.xml")
    return find_minipro_share_file("infoic.xml")


def legacy_infoic_available() -> bool:
    return find_minipro_share_file("infoic_0.7.4.xml") is not None
