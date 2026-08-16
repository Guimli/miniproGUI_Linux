"""Xgpro software bundle (.rar) extraction.

Port of MiniproUI/Utilities/XgproSoftwareExtractor.swift (Visual Minipro 1.5.8).

The vendor ships a RAR containing a self-extracting installer, hence the two
passes: the first unwraps the outer archive to stdout, the second extracts the
payload it contains. On Debian, bsdtar comes from the `libarchive-tools`
package rather than macOS's built-in /usr/bin/bsdtar.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger("visualminipro.extractor")


class XgproSoftwareExtractorError(Exception):
    pass


class ToolUnavailable(XgproSoftwareExtractorError):
    def __str__(self) -> str:
        return (
            "bsdtar was not found. Install it with:\n"
            "  sudo apt install libarchive-tools"
        )


class ExtractionFailed(XgproSoftwareExtractorError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return f"Failed to extract the software bundle: {self.message}"


def _find_bsdtar() -> str | None:
    return shutil.which("bsdtar") or (
        "/usr/bin/bsdtar" if Path("/usr/bin/bsdtar").is_file() else None
    )


class XgproSoftwareExtractor:
    @staticmethod
    def extract_rar(input_path: Path, output_directory: Path) -> None:
        from ..minipro.invoker import ProcessInvoker

        bsdtar = _find_bsdtar()
        if bsdtar is None:
            raise ToolUnavailable()

        output_directory.mkdir(parents=True, exist_ok=True)

        first_pass = ProcessInvoker.invoke(
            executable=bsdtar,
            arguments=["-x", "--to-stdout", "-f", str(input_path)],
        )
        if first_pass.exit_code != 0:
            raise ExtractionFailed(first_pass.std_err)

        second_pass = ProcessInvoker.invoke(
            executable=bsdtar,
            arguments=["-x", "-f", "-"],
            stdin_data=first_pass.std_out,
            cwd=str(output_directory),
        )
        if second_pass.exit_code != 0:
            raise ExtractionFailed(second_pass.std_err)

        logger.info("Extracted %s to %s", input_path, output_directory)
