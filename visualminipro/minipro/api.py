"""Public interface for all programmer operations.

Port of MiniproUI/Minipro/MiniproAPI.swift (Visual Minipro 1.5.8).

Every method invokes MiniproInvoker and delegates parsing to a processor.
Calls block, so GUI code runs them on a worker thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .invoker import MiniproInvoker
from .processors import (
    DeviceDetails,
    DeviceDetailsProcessor,
    DeviceIdProcessor,
    LogicICTestProcessor,
    LogicICTestResult,
    ProgrammerInfo,
    ProgrammerInfoProcessor,
    ProgressUpdate,
    ProgressUpdateProcessor,
    ReadProcessor,
    SupportedDevices,
    SupportedDevicesProcessor,
    UpdateFirmwareProcessor,
    VisualMiniproInfo,
    VisualMiniproInfoProcessor,
    WriteProcessor,
)

ProgressHandler = Callable[[ProgressUpdate], None]


@dataclass
class WriteOptions:
    ignore_file_size_mismatch: bool = False
    ignore_chip_id_mismatch: bool = False
    skip_verification: bool = False
    unprotect_before_write: bool = False
    protect_after_write: bool = False


@dataclass
class ReadOptions:
    ignore_chip_id_mismatch: bool = False


def _progress_bridge(handler: Optional[ProgressHandler]):
    """Turn raw stderr chunks into ProgressUpdate callbacks."""
    if handler is None:
        return None

    def on_chunk(data: bytes) -> None:
        update = ProgressUpdateProcessor.run(data)
        if update is not None:
            handler(update)

    return on_chunk


class MiniproAPI:
    @staticmethod
    def _ensure_programmer_connected() -> None:
        MiniproAPI.get_programmer_info()

    @staticmethod
    def get_programmer_info() -> ProgrammerInfo:
        # No --infoic passed because we never use/show supported
        # information returned based on Info IC database (supported chip count)
        result = MiniproInvoker.invoke(["--version"])
        return ProgrammerInfoProcessor.run(result)

    @staticmethod
    def get_supported_devices(infoic_path: Path, logicic_path: Path) -> SupportedDevices:
        MiniproAPI._ensure_programmer_connected()
        result = MiniproInvoker.invoke(["--list", "--infoic", str(infoic_path)])
        return SupportedDevicesProcessor.run(result, infoic_path, logicic_path)

    @staticmethod
    def get_device_details(device: str, infoic_path: Path) -> DeviceDetails:
        MiniproAPI._ensure_programmer_connected()
        result = MiniproInvoker.invoke(["--get_info", device, "--infoic", str(infoic_path)])
        return DeviceDetailsProcessor.run(result)

    @staticmethod
    def test_logic_ic(device: str, algorithm_xml_path: Optional[Path]) -> LogicICTestResult:
        arguments = ["--logic_test", "--device", device]
        if algorithm_xml_path is not None:
            arguments += ["--algorithms", str(algorithm_xml_path)]
        result = MiniproInvoker.invoke(arguments)
        return LogicICTestProcessor.run(result, device)

    @staticmethod
    def read_device_id(
        device: str, algorithm_xml_path: Optional[Path], infoic_path: Path
    ) -> str:
        arguments = ["--device", device, "--read_id", "--infoic", str(infoic_path)]
        if algorithm_xml_path is not None:
            arguments += ["--algorithms", str(algorithm_xml_path)]
        result = MiniproInvoker.invoke(arguments)
        return DeviceIdProcessor.run(result)

    @staticmethod
    def read(
        device: str,
        algorithm_xml_path: Optional[Path],
        read_options: ReadOptions,
        infoic_path: Path,
        progress_update: Optional[ProgressHandler] = None,
    ) -> bytes:
        arguments = ["--device", device, "--read", "-", "--infoic", str(infoic_path)]
        if algorithm_xml_path is not None:
            arguments += ["--algorithms", str(algorithm_xml_path)]
        if read_options.ignore_chip_id_mismatch:
            arguments.append("--no_id_error")

        result = MiniproInvoker.invoke(arguments, on_progress=_progress_bridge(progress_update))
        return ReadProcessor.run(result)

    @staticmethod
    def write(
        device: str,
        data: bytes,
        algorithm_xml_path: Optional[Path],
        write_options: WriteOptions,
        infoic_path: Path,
        progress_update: Optional[ProgressHandler] = None,
    ) -> None:
        arguments = ["--device", device, "--write", "-", "--infoic", str(infoic_path)]
        if algorithm_xml_path is not None:
            arguments += ["--algorithms", str(algorithm_xml_path)]
        if write_options.ignore_file_size_mismatch:
            arguments.append("--no_size_error")
        if write_options.ignore_chip_id_mismatch:
            arguments.append("--no_id_error")
        if write_options.skip_verification:
            arguments.append("--skip_verify")
        if write_options.unprotect_before_write:
            arguments.append("--unprotect")
        if write_options.protect_after_write:
            arguments.append("--protect")

        result = MiniproInvoker.invoke(
            arguments, stdin_data=data, on_progress=_progress_bridge(progress_update)
        )
        WriteProcessor.run(result, write_options)

    @staticmethod
    def update_firmware(
        firmware_file_path: str, progress_update: Optional[ProgressHandler] = None
    ) -> None:
        result = MiniproInvoker.invoke(
            ["--update", firmware_file_path],
            stdin_data=b"y",
            on_progress=_progress_bridge(progress_update),
        )
        UpdateFirmwareProcessor.run(result)

    @staticmethod
    def get_visual_minipro_info() -> VisualMiniproInfo:
        result = MiniproInvoker.invoke(["--version"])
        return VisualMiniproInfoProcessor.run(result)
