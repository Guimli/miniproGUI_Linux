"""Response processors: parse minipro's output into typed results or errors."""

from .app_info import APP_VERSION, VisualMiniproInfo, VisualMiniproInfoProcessor
from .device_details import DeviceDetails, DeviceDetailsProcessor
from .logic_ic_test import LogicICTestProcessor, LogicICTestResult
from .programmer_info import ProgrammerInfo, ProgrammerInfoProcessor
from .simple import (
    DeviceIdProcessor,
    ProgressUpdate,
    ProgressUpdateProcessor,
    ReadProcessor,
    UpdateFirmwareProcessor,
    WriteProcessor,
)
from .supported_devices import SupportedDevices, SupportedDevicesProcessor
from .utils import KeyValuePair, ensure_no_error, extract_info

__all__ = [
    "APP_VERSION",
    "DeviceDetails",
    "DeviceDetailsProcessor",
    "DeviceIdProcessor",
    "KeyValuePair",
    "LogicICTestProcessor",
    "LogicICTestResult",
    "ProgrammerInfo",
    "ProgrammerInfoProcessor",
    "ProgressUpdate",
    "ProgressUpdateProcessor",
    "ReadProcessor",
    "SupportedDevices",
    "SupportedDevicesProcessor",
    "UpdateFirmwareProcessor",
    "VisualMiniproInfo",
    "VisualMiniproInfoProcessor",
    "WriteProcessor",
    "ensure_no_error",
    "extract_info",
]
