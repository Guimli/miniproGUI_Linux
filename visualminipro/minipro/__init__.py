"""Minipro integration layer.

Views -> MiniproAPI -> MiniproInvoker -> minipro CLI binary
"""

from .api import MiniproAPI, ReadOptions, WriteOptions
from .errors import (
    ChipIdMismatch,
    DeviceNotFound,
    ExecutableNotFound,
    FirmwareUpdateError,
    IncorrectFileSize,
    InvalidChip,
    IOErrorResult,
    LogicICTestError,
    MiniproAPIError,
    ProgrammerInfoUnavailable,
    ProgrammerNotFound,
    ReadError,
    UnknownError,
    UnsupportedChip,
    VerificationFailed,
)
from .invoker import InvocationResult, MiniproInvoker, ProcessInvoker, find_minipro
from .model import ProgrammerModel
from .processors import (
    APP_VERSION,
    DeviceDetails,
    KeyValuePair,
    LogicICTestResult,
    ProgrammerInfo,
    ProgressUpdate,
    SupportedDevices,
    VisualMiniproInfo,
)

__all__ = [
    "APP_VERSION",
    "DeviceDetails",
    "ExecutableNotFound",
    "InvocationResult",
    "KeyValuePair",
    "LogicICTestResult",
    "MiniproAPI",
    "MiniproAPIError",
    "MiniproInvoker",
    "ProcessInvoker",
    "ProgrammerInfo",
    "ProgrammerModel",
    "ProgressUpdate",
    "ReadOptions",
    "SupportedDevices",
    "VisualMiniproInfo",
    "WriteOptions",
    "find_minipro",
]
