"""The small processors: device ID, read, write, progress, firmware update.

Ports of DeviceIdProcessor.swift, ReadProcessor.swift, WriteProcessor.swift,
ProgressUpdateProcessor.swift and UpdateFirmwareProcessor.swift
(Visual Minipro 1.5.8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..errors import (
    ChipIdMismatch,
    FirmwareUpdateError,
    IncorrectFileSize,
    ReadError,
    UnknownError,
    VerificationFailed,
)
from ..invoker import InvocationResult
from .utils import ensure_no_error

_CHIP_ID_MISMATCH = re.compile(r"Chip ID mismatch: expected (\S+), got (\S+)")
_CHIP_ID = re.compile(r"Chip ID: +(\S+) +OK")


class DeviceIdProcessor:
    @staticmethod
    def run(result: InvocationResult) -> str:
        ensure_no_error(result)

        mismatch = _CHIP_ID_MISMATCH.search(result.std_err)
        if mismatch is not None:
            raise ChipIdMismatch(mismatch.group(1), mismatch.group(2))

        chip_id = _CHIP_ID.search(result.std_err)
        if chip_id is not None:
            return chip_id.group(1)

        raise UnknownError("Failed to get device ID")


class ReadProcessor:
    @staticmethod
    def run(result: InvocationResult) -> bytes:
        ensure_no_error(result)

        if result.exit_code != 0:
            raise ReadError(result.exit_code)

        return result.std_out


_WRITING_OK = re.compile(r"Writing .* OK")
_VERIFICATION_FAILED = re.compile(r"Verification failed at address.*")
_INCORRECT_FILE_SIZE = re.compile(r"Incorrect file size: (\d+) \(needed (\d+)")


class WriteProcessor:
    @staticmethod
    def run(result: InvocationResult, write_options) -> None:
        ensure_no_error(result, ignore_invalid_chip_id=write_options.ignore_chip_id_mismatch)

        # T76 specific - the FPGA reset line is noise, not a result.
        std_err = result.std_err.replace("FPGA Reset  OK\n", "")

        if write_options.skip_verification:
            if _WRITING_OK.search(std_err) is not None:
                return
        else:
            if std_err.endswith("Verification OK\n"):
                return

            verification_failed = _VERIFICATION_FAILED.search(std_err)
            if verification_failed is not None:
                raise VerificationFailed(verification_failed.group(0))

        if not write_options.ignore_file_size_mismatch:
            incorrect_size = _INCORRECT_FILE_SIZE.search(std_err)
            if incorrect_size is not None:
                raise IncorrectFileSize(int(incorrect_size.group(2)), int(incorrect_size.group(1)))

        last_line = ""
        lines = [line for line in result.std_err.split("\n") if line]
        if lines:
            last_line = lines[-1]
        raise UnknownError(f"{last_line} Exit code: {result.exit_code}")


@dataclass(frozen=True)
class ProgressUpdate:
    operation: str
    percentage: int


# `...` is left as "any three characters" to match the Swift regex literal.
_PROGRESS = re.compile(r"(Reading\s+\w+|Writing\s+\w+|Reflashing)...\s+(\d+)%")


class ProgressUpdateProcessor:
    @staticmethod
    def run(data: Optional[bytes]) -> Optional[ProgressUpdate]:
        if not data:
            return None

        update = data.decode("utf-8", errors="replace")
        match = _PROGRESS.search(update)
        if match is not None:
            return ProgressUpdate(operation=match.group(1), percentage=int(match.group(2)))
        return None


_FIRMWARE_UPDATE_ERRORS = (
    "open error",
    "file size error",
    "file read error",
    "file version error",
    "file CRC error",
    "failed",
    "Failed",
)


class UpdateFirmwareProcessor:
    @staticmethod
    def run(result: InvocationResult) -> None:
        if result.exit_code == 0 and "Reflash... OK" in result.std_err:
            return

        for line in result.std_err.split("\n"):
            for error in _FIRMWARE_UPDATE_ERRORS:
                if error in line:
                    raise FirmwareUpdateError(line)

        ensure_no_error(result)
        raise UnknownError("Failed to update firmware")
