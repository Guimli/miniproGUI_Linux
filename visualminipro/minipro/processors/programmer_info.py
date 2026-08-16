"""Programmer identification.

Port of MiniproUI/Minipro/ResponseProcessors/ProgrammerInfoProcessor.swift
(Visual Minipro 1.5.8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..errors import ProgrammerInfoUnavailable
from ..invoker import InvocationResult
from ..model import ProgrammerModel
from .utils import ensure_no_error

_MODEL = re.compile(r"Found (\S+)")
_FIRMWARE_VERSION = re.compile(r"Found \S+ (.+)\n")
_DEVICE_CODE = re.compile(r"Device code: (\S+)")
_SERIAL_NUMBER = re.compile(r"Serial code: (\S+)")
_DATE_MANUFACTURED = re.compile(r"Manufactured: (\d{4}-\d{2}-\d{2})(\d{2}:\d{2})")
_USB_SPEED = re.compile(r"USB speed: (.+)\n")
_SUPPLY_VOLTAGE = re.compile(r"Supply voltage: (.+)\n")
_HEX = re.compile(r"0x[0-9a-fA-F]+")
_WHITESPACE = re.compile(r"[\s]+")


@dataclass
class ProgrammerInfo:
    model: ProgrammerModel
    firmware_version: str
    device_code: str
    serial_number: str
    date_manufactured: str
    usb_speed: str
    supply_voltage: str
    warnings: list[str] = field(default_factory=list)

    def firmware_version_number(self) -> Optional[int]:
        """The `0x...` part of the firmware string, as an integer.

        This is what names the per-firmware algorithm folder for T56/T76.
        """
        match = _HEX.search(self.firmware_version)
        if match is not None:
            try:
                return int(match.group(0)[2:], 16) & 0xFFFF
            except ValueError:
                return None
        return None


def _sanitize_version_warning_line(line: str) -> str:
    return _WHITESPACE.sub(" ", line)


def _find_warnings(std_err: str) -> list[str]:
    warnings: list[str] = []
    lines = [line for line in std_err.split("\n") if line]
    for index, line in enumerate(lines):
        marker = line.find("Warning: ")
        if marker == -1:
            continue
        warning = line[marker + len("Warning: "):]
        if warning.startswith("Firmware is") and index + 2 < len(lines):
            # The firmware mismatch warning spills the expected/actual versions
            # onto the two following lines.
            warnings.append(
                f"{warning}{_sanitize_version_warning_line(lines[index + 1])},"
                f"{_sanitize_version_warning_line(lines[index + 2])}"
            )
        else:
            warnings.append(warning)
    return warnings


class ProgrammerInfoProcessor:
    @staticmethod
    def run(result: InvocationResult) -> ProgrammerInfo:
        ensure_no_error(result)

        std_err = result.std_err
        model = _MODEL.search(std_err)
        firmware_version = _FIRMWARE_VERSION.search(std_err)
        device_code = _DEVICE_CODE.search(std_err)
        serial_number = _SERIAL_NUMBER.search(std_err)
        date_manufactured = _DATE_MANUFACTURED.search(std_err)
        usb_speed = _USB_SPEED.search(std_err)
        supply_voltage = _SUPPLY_VOLTAGE.search(std_err)

        if model is None or firmware_version is None or device_code is None or serial_number is None:
            raise ProgrammerInfoUnavailable()

        return ProgrammerInfo(
            model=ProgrammerModel.parse(model.group(1)),
            firmware_version=firmware_version.group(1),
            device_code=device_code.group(1),
            serial_number=serial_number.group(1),
            date_manufactured=(
                f"{date_manufactured.group(1)} {date_manufactured.group(2)}"
                if date_manufactured is not None
                else "N/A"
            ),
            usb_speed=usb_speed.group(1) if usb_speed is not None else "N/A",
            supply_voltage=supply_voltage.group(1) if supply_voltage is not None else "N/A",
            warnings=_find_warnings(std_err),
        )
