"""Typed errors raised by the response processors.

Port of MiniproUI/Minipro/ResponseProcessors/MiniproAPIError.swift (Visual Minipro 1.5.8).
"""


class MiniproAPIError(Exception):
    """Base class mirroring the Swift MiniproAPIError enum."""

    def __str__(self) -> str:
        return self.description

    @property
    def description(self) -> str:
        return "Unknown error"


class ProgrammerNotFound(MiniproAPIError):
    @property
    def description(self) -> str:
        return "Programmer not found"


class ProgrammerInfoUnavailable(MiniproAPIError):
    @property
    def description(self) -> str:
        return "Programmer info unavailable"


class DeviceNotFound(MiniproAPIError):
    def __init__(self, device_id: str):
        super().__init__(device_id)
        self.device_id = device_id

    @property
    def description(self) -> str:
        return f"Chip not found: {self.device_id}"


class ReadError(MiniproAPIError):
    def __init__(self, exit_code: int):
        super().__init__(exit_code)
        self.exit_code = exit_code

    @property
    def description(self) -> str:
        return f"Unknown read error. Exit code: {self.exit_code}"


class UnsupportedChip(MiniproAPIError):
    @property
    def description(self) -> str:
        return "Unsupported chip"


class InvalidChip(MiniproAPIError):
    def __init__(self, expected: str, actual: str):
        super().__init__(expected, actual)
        self.expected = expected
        self.actual = actual

    @property
    def description(self) -> str:
        return f"Invalid Chip ID: expected {self.expected}, actual {self.actual}"


class UnknownError(MiniproAPIError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    @property
    def description(self) -> str:
        return f"Unknown error: {self.message}"


class IOErrorResult(MiniproAPIError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    @property
    def description(self) -> str:
        return f"IO error: {self.message}"


class ChipIdMismatch(MiniproAPIError):
    def __init__(self, expected: str, actual: str):
        super().__init__(expected, actual)
        self.expected = expected
        self.actual = actual

    @property
    def description(self) -> str:
        return f"Chip ID mismatch: expected {self.expected}, actual {self.actual}"


class FirmwareUpdateError(MiniproAPIError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    @property
    def description(self) -> str:
        return f"Firmware update error: {self.message}"


class IncorrectFileSize(MiniproAPIError):
    def __init__(self, expected: int, actual: int):
        super().__init__(expected, actual)
        self.expected = expected
        self.actual = actual

    @property
    def description(self) -> str:
        return f"Incorrect file size: expected {self.expected}, actual {self.actual}"


class VerificationFailed(MiniproAPIError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    @property
    def description(self) -> str:
        return self.message


class LogicICTestError(MiniproAPIError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    @property
    def description(self) -> str:
        return self.message


class ExecutableNotFound(MiniproAPIError):
    """Linux-specific: the `minipro` CLI could not be located on PATH.

    Replaces the Swift InvocationError.executableNotFound, which resolved the
    binary from the macOS app bundle via Bundle.main.path(forAuxiliaryExecutable:).
    """

    def __init__(self, searched: str = ""):
        super().__init__(searched)
        self.searched = searched

    @property
    def description(self) -> str:
        base = (
            "The 'minipro' command-line tool was not found.\n\n"
            "Install it with:\n"
            "  git clone https://gitlab.com/DavidGriffith/minipro.git\n"
            "  cd minipro && make && sudo make install"
        )
        if self.searched:
            return f"{base}\n\nSearched: {self.searched}"
        return base
