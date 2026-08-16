"""Process invocation layer.

Port of MiniproUI/Utilities/ProcessInvoker.swift and
MiniproUI/Minipro/MiniproInvoker.swift (Visual Minipro 1.5.8).

Linux differences from the macOS original:
  * The macOS app ships `minipro` inside its bundle and resolves it via
    Bundle.main.path(forAuxiliaryExecutable:). Here it is a system tool, so we
    look it up on PATH (with the usual /usr/local/bin fallback).
  * Swift structured concurrency (async/await + DispatchQueue) is replaced by a
    plain blocking call that GUI code runs on a worker thread; progress is
    marshalled back to the GTK main loop by the caller.
"""

from __future__ import annotations

import logging
import os
import selectors
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .errors import ExecutableNotFound

logger = logging.getLogger("visualminipro.invoker")
libusb_logger = logging.getLogger("visualminipro.libusb")

ProgressCallback = Callable[[bytes], None]

# Candidate locations, in the order minipro's `make install` and the distro
# packages use.
_MINIPRO_FALLBACKS = (
    "/usr/local/bin/minipro",
    "/usr/bin/minipro",
)


@dataclass
class InvocationResult:
    exit_code: int
    std_out: bytes
    std_err: str

    @property
    def std_out_string(self) -> str:
        return self.std_out.decode("utf-8", errors="replace")

    def __repr__(self) -> str:
        return (
            f"exitCode: {self.exit_code}\n"
            f"stdOut: {_shorten(self.std_out_string)}\n"
            f"stdErr: {_shorten(self.std_err)}"
        )


def _shorten(string: str, max_length: int = 500) -> str:
    if len(string) <= max_length:
        return string
    half = max_length // 2
    return f"{string[:half]}...{string[-half:]}"


def find_minipro() -> Optional[str]:
    """Locate the minipro executable, or None if it is not installed."""
    found = shutil.which("minipro")
    if found:
        return found
    for candidate in _MINIPRO_FALLBACKS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


class ProcessInvoker:
    """Runs a subprocess, capturing stdout as bytes and streaming stderr.

    stdout is kept binary because `minipro --read -` writes the chip contents
    there. stderr carries all human-readable output *and* the progress
    indicators, so it is read incrementally and handed to `on_progress`.
    """

    @staticmethod
    def invoke(
        executable: str,
        arguments: Sequence[str],
        stdin_data: Optional[bytes] = None,
        cwd: Optional[str] = None,
        on_progress: Optional[ProgressCallback] = None,
        env: Optional[dict] = None,
    ) -> InvocationResult:
        logger.info("invoking %s with arguments: %s", os.path.basename(executable), list(arguments))

        process = subprocess.Popen(
            [executable, *arguments],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []

        def write_stdin() -> None:
            try:
                if stdin_data:
                    process.stdin.write(stdin_data)
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass

        # minipro can block writing to stdout while we are still feeding stdin
        # (large --write payloads), so stdin runs on its own thread.
        stdin_thread = threading.Thread(target=write_stdin, daemon=True)
        stdin_thread.start()

        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        open_streams = 2

        while open_streams > 0:
            for key, _ in selector.select():
                stream = key.fileobj
                chunk = os.read(stream.fileno(), 65536)
                if not chunk:
                    selector.unregister(stream)
                    open_streams -= 1
                    continue
                if key.data == "stdout":
                    stdout_chunks.append(chunk)
                else:
                    stderr_chunks.append(chunk)
                    if on_progress is not None:
                        on_progress(chunk)

        selector.close()
        stdin_thread.join(timeout=5)
        process.wait()
        try:
            process.stdout.close()
            process.stderr.close()
        except OSError:
            pass

        result = InvocationResult(
            exit_code=process.returncode,
            std_out=b"".join(stdout_chunks),
            std_err=b"".join(stderr_chunks).decode("utf-8", errors="replace"),
        )
        logger.info("invocation completed %r", result)
        return result


class MiniproInvoker:
    LIBUSB_HEADER = "[timestamp] [threadID] facility level [function call] <message>"
    LIBUSB_SEPARATOR = "-" * 80

    @staticmethod
    def invoke(
        arguments: Sequence[str],
        stdin_data: Optional[bytes] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> InvocationResult:
        executable = find_minipro()
        if executable is None:
            logger.error("minipro executable not found")
            raise ExecutableNotFound(os.environ.get("PATH", ""))

        result = ProcessInvoker.invoke(
            executable=executable,
            arguments=arguments,
            stdin_data=stdin_data,
            on_progress=on_progress,
            env=os.environ.copy(),
        )
        return MiniproInvoker.filter_libusb_lines(result)

    @staticmethod
    def filter_libusb_lines(result: InvocationResult) -> InvocationResult:
        """Route libusb debug chatter to the log so it never reaches the parsers."""
        normal_lines: list[str] = []
        for line in result.std_err.split("\n"):
            if "] libusb: " in line:
                libusb_logger.info("%s", line)
            elif line == MiniproInvoker.LIBUSB_HEADER or line == MiniproInvoker.LIBUSB_SEPARATOR:
                pass  # libusb preamble - discard
            else:
                normal_lines.append(line)
        return InvocationResult(
            exit_code=result.exit_code,
            std_out=result.std_out,
            std_err="\n".join(normal_lines),
        )
