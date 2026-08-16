"""Xgpro firmware/algorithm handling for the T56 and T76.

Port of MiniproUI/Utilities/XgproFirmwareUtils.swift (Visual Minipro 1.5.8).

These programmers keep their per-chip programming algorithms outside the
firmware. The vendor ships them inside the Xgpro Windows software; this module
turns the extracted `.alg` files into the algorithm.xml that minipro consumes
via --algorithms.

Linux difference: gzip compression uses Python's gzip module instead of
shelling out to /usr/bin/gzip. mtime is pinned to 0 so repeated runs over the
same bundle produce byte-identical output.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import logging
import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from ..minipro.model import ProgrammerModel
from ..minipro.processors import ProgressUpdate

logger = logging.getLogger("visualminipro.xgpro")

T56_FILE_NAME = "updatet56.dat"
T76_FILE_NAME = "UpdateT76.Dat"

# T76 algorithm file layout
_T76_HEADER_OFFSET = 4
_T76_HEADER_LENGTH = 8
_T76_DESCRIPTION_OFFSET = 16
_T76_DESCRIPTION_LENGTH = 4080
_T76_ALGORITHM_OFFSET = 4096  # == 16 + 4080

# T56 algorithm file layout
_T56_ALGORITHM_OFFSET = 0x220


class XgproFirmwareUtilsError(Exception):
    pass


class FirmwareNotFound(XgproFirmwareUtilsError):
    def __str__(self) -> str:
        return (
            "No firmware file found in the bundle "
            f"(expected {T76_FILE_NAME} or {T56_FILE_NAME})."
        )


class AlgorithmsNotFound(XgproFirmwareUtilsError):
    def __str__(self) -> str:
        return "No algorithm (.alg) files were found in the bundle."


class FileTooSmall(XgproFirmwareUtilsError):
    def __str__(self) -> str:
        return "A file in the bundle is smaller than expected and cannot be read."


class ReadFailed(XgproFirmwareUtilsError):
    def __str__(self) -> str:
        return "Failed to read a file from the bundle."


class UnsupportedProgrammerType(XgproFirmwareUtilsError):
    def __str__(self) -> str:
        return "This programmer does not use algorithm bundles."


@dataclass(frozen=True)
class FirmwareInfo:
    programmer_model: ProgrammerModel
    firmware_version: int
    file_name: str


@dataclass(frozen=True)
class _SoftwareBundleInfo:
    firmware_info: FirmwareInfo
    checksum: str


class SoftwareBundleVerificationStatus(Enum):
    CHECKSUM_MATCH = "checksum_match"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    PROGRAMMER_MODEL_MISMATCH = "programmer_model_mismatch"
    CHECKSUM_NOT_AVAILABLE = "checksum_not_available"
    VERIFICATION_FAILED = "verification_failed"


# Known-good vendor bundles, carried over verbatim from Visual Minipro 1.5.8.
_SOFTWARE_INFO: dict[str, _SoftwareBundleInfo] = {
    "xgpro_T76_V1303A.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T76, 0x10D, T76_FILE_NAME),
        "493024ac8951f733e34b42cac66d873ef77f9e12e3547c6f1e5e295d0061f1aa",
    ),
    "xgpro_T76_V1309.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T76, 0x10E, T76_FILE_NAME),
        "72164362cc986742b101eab1a93e884b93f280f9fc0e2e8b6077fd0ca2ab9745",
    ),
    "xgpro_T76_V1311.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T76, 0x10F, T76_FILE_NAME),
        "aad3cc7678676da2e1b2bb0505d7c58e0c74ca1612f805a994eebe6c11473ea8",
    ),
    "xgpro_T76_V1317.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T76, 0x110, T76_FILE_NAME),
        "15e6c0641c1db3f924608994bd2e21f7580e24fe8d7ab19098edb79b10919169",
    ),
    "xgpro_T76_V1319.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T76, 0x111, T76_FILE_NAME),
        "8541d3d0f47a5d7dc1727e7b6dc41db7bf1132a4b6b549f2947a8cd210c40490",
    ),
    "xgpro_T76_V1321.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T76, 0x112, T76_FILE_NAME),
        "b0c2e0afaea1c2680c0aa8a24f1cb68fd88dc227d08ccc697121948e612e5c8e",
    ),
    "xgproV1304_T48_T56_T866II_Setup.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T56, 0x149, T56_FILE_NAME),
        "821db3ef1cc2b335d8a1e50ad37161032f804c8626cd3c1e7d03695d9aa75b1d",
    ),
    "xgproV1306_T48_T56_T866_Setup.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T56, 0x149, T56_FILE_NAME),
        "2110b1af7b8f0274032cef006c7be23d2c28d375e3392040dc9de09f5d35eba6",
    ),
    "xgproV1310_T48_T56_T866II_Setup.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T56, 0x149, T56_FILE_NAME),
        "f3fb94d483c20e0e28d8a53ffd5e0930ef285cfeea008f23691ed097c8dcd0c9",
    ),
    "xgproV1316_T48_T56_T866II_Setup.rar": _SoftwareBundleInfo(
        FirmwareInfo(ProgrammerModel.T56, 0x149, T56_FILE_NAME),
        "0f2a94baa9d4a2170b07ecfca48e9f6ceb636526b1bb4860e8671d9c0dff2f03",
    ),
}


def _gzip_data(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=9, mtime=0)


def _extract_strings(data: bytes, minimum_length: int) -> list[str]:
    """Printable-ASCII runs of at least `minimum_length` characters.

    A run is only emitted when a non-printable byte terminates it, matching the
    Swift implementation, plus a final flush at end of buffer.
    """
    results: list[str] = []
    current = bytearray()
    for byte in data:
        if 0x20 <= byte <= 0x7E:
            current.append(byte)
        else:
            if len(current) >= minimum_length:
                results.append(current.decode("ascii"))
            current.clear()
    if len(current) >= minimum_length:
        results.append(current.decode("ascii"))
    return results


def _read_uint16_le(data: bytes) -> int:
    if len(data) < 2:
        raise FileTooSmall()
    return struct.unpack("<H", data[:2])[0]


class XgproFirmwareUtils:
    @staticmethod
    def get_firmware_info(folder: Path) -> FirmwareInfo:
        """Identify which programmer an extracted bundle targets."""
        t56_match: Optional[Path] = None
        t76_match: Optional[Path] = None

        for entry in folder.iterdir():
            if entry.name.startswith("."):
                continue
            lowered = entry.name.lower()
            if lowered == T76_FILE_NAME.lower():
                t76_match = entry
            elif lowered == T56_FILE_NAME.lower():
                t56_match = entry

        # The T76 wins when both are present - its bundles are the newer format.
        if t76_match is not None:
            version = XgproFirmwareUtils._extract_firmware_version(t76_match)
            logger.info("Detected T76 firmware file at %s", t76_match)
            return FirmwareInfo(ProgrammerModel.T76, version, t76_match.name)
        if t56_match is not None:
            version = XgproFirmwareUtils._extract_firmware_version(t56_match)
            logger.info("Detected T56 firmware file at %s", t56_match)
            return FirmwareInfo(ProgrammerModel.T56, version, t56_match.name)

        logger.info("No firmware file found in %s", folder)
        raise FirmwareNotFound()

    @staticmethod
    def _extract_firmware_version(file_path: Path) -> int:
        try:
            with open(file_path, "rb") as handle:
                header = handle.read(2)
        except OSError as exc:
            logger.info("Failed to read firmware header from %s: %s", file_path, exc)
            raise ReadFailed() from exc
        if len(header) < 2:
            logger.info("Firmware file too small: %s", file_path)
            raise FileTooSmall()
        version = _read_uint16_le(header)
        logger.info("Extracted firmware version %s from %s", version, file_path)
        return version

    @staticmethod
    def create_algorithm_xml(
        base_folder: Path,
        programmer_model: ProgrammerModel,
        progress_update: Optional[Callable[[ProgressUpdate], None]] = None,
    ) -> str:
        algorithm_folder = XgproFirmwareUtils._resolve_algorithm_directory(
            base_folder, programmer_model
        )
        entries = sorted(
            entry
            for entry in algorithm_folder.iterdir()
            if not entry.name.startswith(".") and entry.suffix.lower() == ".alg"
        )
        if not entries:
            raise AlgorithmsNotFound()

        algorithm_elements: list[str] = []
        for index, entry in enumerate(entries):
            if programmer_model == ProgrammerModel.T76:
                algorithm_elements.append(XgproFirmwareUtils._build_algorithm_element_t76(entry))
            elif programmer_model == ProgrammerModel.T56:
                algorithm_elements.append(XgproFirmwareUtils._build_algorithm_element_t56(entry))
            if progress_update is not None:
                percentage = int(((index + 1) / len(entries)) * 100.0)
                progress_update(ProgressUpdate("Preparing Algorithms", percentage))

        logger.info("Built algorithms XML with %d entries", len(algorithm_elements))
        return XgproFirmwareUtils._build_algorithms_xml(programmer_model, algorithm_elements)

    @staticmethod
    def _build_algorithms_xml(
        programmer_model: ProgrammerModel, algorithm_elements: list[str]
    ) -> str:
        joined = "\n".join(algorithm_elements)
        return (
            "<root>\n"
            '<database type="ALGORITHMS">\n'
            f"<algorithms_{programmer_model.value}>\n"
            f"{joined}\n"
            f"</algorithms_{programmer_model.value}>\n"
            "</database>\n"
            "</root>"
        )

    @staticmethod
    def _resolve_algorithm_directory(
        base_folder: Path, programmer_model: ProgrammerModel
    ) -> Path:
        if programmer_model == ProgrammerModel.T76:
            return base_folder / "algoT76"
        if programmer_model == ProgrammerModel.T56:
            return base_folder / "algorithm"
        logger.info("Unsupported programmer model: %s", programmer_model.value)
        raise UnsupportedProgrammerType()

    @staticmethod
    def _build_algorithm_element(name: str, description: str, bitstream: str) -> str:
        return (
            f'<algorithm name="{name}"\n'
            f'description="{description}"\n'
            f'bitstream="{bitstream}" />'
        )

    @staticmethod
    def _build_algorithm_element_t76(path: Path) -> str:
        logger.info("Processing T76 algorithm file at %s", path)
        algorithm_file = path.read_bytes()
        if len(algorithm_file) < _T76_ALGORITHM_OFFSET:
            logger.info("T76 algorithm file too small: %s", path)
            raise FileTooSmall()
        name = XgproFirmwareUtils._algorithm_name_t76(path)
        description = XgproFirmwareUtils._algorithm_description_t76(algorithm_file)
        bitstream = XgproFirmwareUtils.create_algorithm_bitstream_t76(algorithm_file)
        return XgproFirmwareUtils._build_algorithm_element(name, description, bitstream)

    @staticmethod
    def _algorithm_name_t76(path: Path) -> str:
        return path.stem.replace("T7_", "")

    @staticmethod
    def _algorithm_description_t76(algorithm_file: bytes) -> str:
        section = algorithm_file[_T76_DESCRIPTION_OFFSET:_T76_ALGORITHM_OFFSET]
        description = " ".join(_extract_strings(section, minimum_length=4))
        logger.info("T76 algorithm description: %s", description)
        return description

    @staticmethod
    def create_algorithm_bitstream_t76(data: bytes) -> str:
        """Header bytes 4..12 followed by everything from 4096 on, gzipped + base64."""
        required_size = max(_T76_HEADER_OFFSET + _T76_HEADER_LENGTH, _T76_ALGORITHM_OFFSET)
        if len(data) < required_size:
            logger.info("Algorithm data too small for bitstream: %d bytes", len(data))
            raise FileTooSmall()

        payload = (
            data[_T76_HEADER_OFFSET:_T76_HEADER_OFFSET + _T76_HEADER_LENGTH]
            + data[_T76_ALGORITHM_OFFSET:]
        )
        return base64.b64encode(_gzip_data(payload)).decode("ascii")

    @staticmethod
    def _build_algorithm_element_t56(path: Path) -> str:
        logger.info("Processing T56 algorithm file at %s", path)
        algorithm_file = path.read_bytes()
        if len(algorithm_file) <= _T56_ALGORITHM_OFFSET:
            logger.info("T56 algorithm file too small: %s", path)
            raise FileTooSmall()
        name = path.stem
        description = XgproFirmwareUtils._description_t56(algorithm_file)
        bitstream = base64.b64encode(
            _gzip_data(algorithm_file[_T56_ALGORITHM_OFFSET:])
        ).decode("ascii")
        return XgproFirmwareUtils._build_algorithm_element(name, description, bitstream)

    @staticmethod
    def _description_t56(data: bytes) -> str:
        null_index = data.find(b"\x00")
        section = data if null_index == -1 else data[:null_index]
        try:
            return section.decode("ascii")
        except UnicodeDecodeError:
            return ""

    @staticmethod
    def _verify_software_sha(file_path: Path, expected_checksum: str) -> bool:
        digest = hashlib.sha256()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == expected_checksum

    @staticmethod
    def _software_info_for(file_path: Path) -> Optional[_SoftwareBundleInfo]:
        file_name = file_path.name.lower()
        for known_name, info in _SOFTWARE_INFO.items():
            if known_name.lower() == file_name:
                return info
        return None

    @staticmethod
    def verify_software_bundle(
        file_path: Path, programmer_model: Optional[ProgrammerModel]
    ) -> SoftwareBundleVerificationStatus:
        info = XgproFirmwareUtils._software_info_for(file_path)
        if info is None:
            return SoftwareBundleVerificationStatus.CHECKSUM_NOT_AVAILABLE

        if info.firmware_info.programmer_model != programmer_model:
            return SoftwareBundleVerificationStatus.PROGRAMMER_MODEL_MISMATCH

        try:
            matched = XgproFirmwareUtils._verify_software_sha(file_path, info.checksum)
        except OSError:
            return SoftwareBundleVerificationStatus.VERIFICATION_FAILED
        return (
            SoftwareBundleVerificationStatus.CHECKSUM_MATCH
            if matched
            else SoftwareBundleVerificationStatus.CHECKSUM_MISMATCH
        )

    @staticmethod
    def get_software_name(
        programmer_model: ProgrammerModel, firmware_version: int
    ) -> Optional[str]:
        """The bundle matching this exact firmware, if one is known."""
        matches = sorted(
            name
            for name, info in _SOFTWARE_INFO.items()
            if info.firmware_info.programmer_model == programmer_model
            and info.firmware_info.firmware_version == firmware_version
        )
        return matches[-1] if matches else None

    @staticmethod
    def get_latest_software_name(programmer_model: ProgrammerModel) -> Optional[str]:
        matches = sorted(
            name
            for name, info in _SOFTWARE_INFO.items()
            if info.firmware_info.programmer_model == programmer_model
        )
        return matches[-1] if matches else None
