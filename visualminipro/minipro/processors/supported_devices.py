"""Supported chip lists, split into logic ICs and memory ICs.

Port of MiniproUI/Minipro/ResponseProcessors/SupportedDevicesProcessor.swift
(Visual Minipro 1.5.8).

Linux differences:
  * logicic.xml comes from minipro's share directory (/usr/local/share/minipro)
    instead of the macOS app bundle.
  * minipro's infoic.xml contains 258 comments with '--' inside them, which is
    illegal XML. macOS's XMLDocument accepts them; Python's expat rejects the
    whole 19 MB file. Comments are stripped before parsing, and the resulting
    name sets are cached by (path, mtime) since parsing takes ~0.6 s.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ..invoker import InvocationResult
from .utils import ensure_no_error

logger = logging.getLogger("visualminipro.supported_devices")

_CUSTOM_SUFFIX = re.compile(r"\(custom\)")
_XML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

_ic_name_cache: dict[tuple[str, float], set[str]] = {}


@dataclass
class SupportedDevices:
    logic_ics: list[str] = field(default_factory=list)
    eeprom_ics: list[str] = field(default_factory=list)


def _get_ic_names(path: Path) -> set[str]:
    """Collect every chip name declared in an infoic/logicic XML database.

    The XML parser expands `&#9;` into a real tab, but minipro prints names
    such as "MT28FW512ABA1HPN-0AAT&#9;(RB158)@BGA64" with the entity intact, so
    both spellings are indexed.
    """
    ic_names: set[str] = set()
    try:
        cache_key = (str(path), path.stat().st_mtime)
    except OSError as exc:
        logger.warning("Could not stat IC database %s: %s", path, exc)
        return ic_names

    cached = _ic_name_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        root = ET.fromstring(_XML_COMMENT.sub("", raw))
    except (OSError, ET.ParseError) as exc:
        logger.warning("Could not parse IC database %s: %s", path, exc)
        return ic_names

    for node in root.iter("ic"):
        name_list = node.get("name") or ""
        for name in name_list.split(","):
            stripped = name.strip()
            ic_names.add(stripped.replace("\t", "&#9;"))
            ic_names.add(stripped)

    _ic_name_cache[cache_key] = ic_names
    return ic_names


def _dedupe(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            result.append(line)
    return result


class SupportedDevicesProcessor:
    @staticmethod
    def run(result: InvocationResult, infoic_path: Path, logicic_path: Path) -> SupportedDevices:
        ensure_no_error(result)

        logic_ics = _get_ic_names(logicic_path)
        eeprom_ics = _get_ic_names(infoic_path)

        # Custom chips get "(custom)" appended to their names:
        # https://gitlab.com/DavidGriffith/minipro/-/blob/master/src/database.c
        lines = [
            _CUSTOM_SUFFIX.sub("", line)
            for line in result.std_out_string.splitlines()
        ]
        lines = [line for line in lines if line]

        return SupportedDevices(
            logic_ics=SupportedDevicesProcessor._get_logic_ics(lines, logic_ics, eeprom_ics),
            eeprom_ics=SupportedDevicesProcessor._get_eeprom_ics(lines, logic_ics, eeprom_ics),
        )

    @staticmethod
    def _get_logic_ics(lines: list[str], logic_ics: set[str], eeprom_ics: set[str]) -> list[str]:
        return [
            line for line in _dedupe(lines)
            if line in logic_ics or line not in eeprom_ics
        ]

    @staticmethod
    def _get_eeprom_ics(lines: list[str], logic_ics: set[str], eeprom_ics: set[str]) -> list[str]:
        return [
            line for line in _dedupe(lines)
            if line in eeprom_ics or line not in logic_ics
        ]
