"""Where the generated algorithm database lives, and whether it is missing.

Port of MiniproUI/Utilities/AlgorithmXmlUtils.swift (Visual Minipro 1.5.8).

The T56 and T76 cannot program anything until an algorithm.xml has been built
from the vendor's Xgpro software bundle. It is keyed by firmware version, so
updating the programmer's firmware requires regenerating it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..minipro.errors import ProgrammerInfoUnavailable
from ..minipro.model import ProgrammerModel
from ..minipro.processors import ProgrammerInfo
from .paths import data_dir


def resolve_algorithm_xml_path(
    programmer_model: ProgrammerModel, firmware_version: int
) -> Path:
    return data_dir() / programmer_model.value / f"0x{firmware_version:x}" / "algorithm.xml"


def resolve_algorithm_xml_path_for(programmer_info: Optional[ProgrammerInfo]) -> Path:
    if programmer_info is None:
        raise ProgrammerInfoUnavailable()
    firmware_version = programmer_info.firmware_version_number()
    if firmware_version is None:
        raise ProgrammerInfoUnavailable()
    return resolve_algorithm_xml_path(programmer_info.model, firmware_version)


def needs_algorithm_installation(programmer_info: Optional[ProgrammerInfo]) -> bool:
    if programmer_info is None or not programmer_info.model.is_algo_based:
        return False
    firmware_version = programmer_info.firmware_version_number()
    if firmware_version is None:
        return False
    return not resolve_algorithm_xml_path(programmer_info.model, firmware_version).is_file()


def algorithm_xml_path_if_needed(programmer_info: Optional[ProgrammerInfo]) -> Optional[Path]:
    """The --algorithms argument, or None for programmers that do not use one."""
    if programmer_info is None or not programmer_info.model.is_algo_based:
        return None
    try:
        return resolve_algorithm_xml_path_for(programmer_info)
    except ProgrammerInfoUnavailable:
        return None
