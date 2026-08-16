"""Shared response-processor helpers.

Port of MiniproUI/Minipro/ResponseProcessors/ReponseProcessorUtils.swift
(Visual Minipro 1.5.8). Swift Regex literals map onto Python `re` patterns
one-for-one here, including the negative lookahead used to let
"Logic test failed: N errors encountered" through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from ..errors import (
    DeviceNotFound,
    InvalidChip,
    IOErrorResult,
    ProgrammerNotFound,
    UnknownError,
    UnsupportedChip,
)
from ..invoker import InvocationResult

_DEVICE_NOT_FOUND = re.compile(r"Device (.*) not found!")
_IO_ERROR = re.compile(r"IO error:(.*)")
# Must not swallow "Logic test failed: 10 errors encountered."
_ERROR = re.compile(r"[Ee]rror(?!s encountered)")
_INVALID_CHIP_ID = re.compile(r"Invalid Chip ID: expected (\S+), got (\S+)")


@dataclass(frozen=True)
class KeyValuePair:
    key: str
    value: str


def ensure_no_error(result: InvocationResult, ignore_invalid_chip_id: bool = False) -> None:
    """Raise the most specific MiniproAPIError the output warrants.

    Called first by every processor, matching the Swift contract.
    """
    std_err = result.std_err

    if "No programmer found" in std_err:
        raise ProgrammerNotFound()

    device_not_found = _DEVICE_NOT_FOUND.search(std_err)
    if device_not_found is not None:
        raise DeviceNotFound(device_not_found.group(1))

    io_errors = []
    for line in std_err.split("\n"):
        match = _IO_ERROR.search(line)
        if match is not None:
            io_errors.append(match.group(1).strip())
    if io_errors:
        raise IOErrorResult("\n".join(io_errors))

    if _ERROR.search(std_err) is not None:
        raise UnknownError(std_err.strip())

    if "This chip is not supported yet." in std_err:
        raise UnsupportedChip()

    if not ignore_invalid_chip_id:
        invalid_chip = _INVALID_CHIP_ID.search(std_err)
        if invalid_chip is not None:
            raise InvalidChip(invalid_chip.group(1), invalid_chip.group(2))


def extract_info(result_lines: Sequence[str], keys: Iterable[str]) -> list[KeyValuePair]:
    """Pull `Key: value` lines out of minipro output, in key order."""
    info: list[KeyValuePair] = []
    for key in keys:
        for line in result_lines:
            if line.startswith(key):
                info.append(KeyValuePair(key=key, value=line[len(key) + 1:].strip()))
    return info
