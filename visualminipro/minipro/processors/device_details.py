"""Per-chip details returned by `minipro --get_info`.

Port of MiniproUI/Minipro/ResponseProcessors/DeviceDetailsProcessor.swift
(Visual Minipro 1.5.8).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..invoker import InvocationResult
from .utils import KeyValuePair, ensure_no_error, extract_info

_DEVICE_INFO_KEYS = [
    "Name",
    "Available on",
    "Memory",
    "Package",
    "Default VCC voltage",
    "Vector count",
    "Protocol",
    "Read buffer size",
    "Write buffer size",
]

_PROGRAMMING_INFO_KEYS = [
    "Default VPP programming voltage",
    "Default VDD write voltage",
    "Default VCC verify voltage",
    "Default write pulse",
]


@dataclass
class DeviceDetails:
    name: str
    device_info: list[KeyValuePair] = field(default_factory=list)
    programming_info: list[KeyValuePair] = field(default_factory=list)
    is_logic_chip: bool = False


class DeviceDetailsProcessor:
    @staticmethod
    def run(result: InvocationResult) -> DeviceDetails:
        ensure_no_error(result)

        result_lines = [line for line in result.std_err.split("\n") if line]
        name_pairs = extract_info(result_lines, ["Name"])
        name = name_pairs[0].value if name_pairs else "(None)"
        device_info = extract_info(result_lines, _DEVICE_INFO_KEYS)
        programming_info = extract_info(result_lines, _PROGRAMMING_INFO_KEYS)
        # Logic ICs report a vector count and stop there - no buffer sizes follow.
        is_logic_chip = bool(device_info) and device_info[-1].key == "Vector count"
        return DeviceDetails(
            name=name,
            device_info=device_info,
            programming_info=programming_info,
            is_logic_chip=is_logic_chip,
        )
