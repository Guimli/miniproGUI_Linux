"""About-box information.

Port of MiniproUI/Minipro/ResponseProcessors/VisualMiniproInfoProcessor.swift
(Visual Minipro 1.5.8).

Linux difference: the macOS build stamped its own git commit/branch/date into
the bundle at build time. Here the app version is a module constant and the
minipro build details still come from `minipro --version`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..invoker import InvocationResult
from .utils import KeyValuePair, extract_info

APP_VERSION = "1.5.8"
UPSTREAM_REFERENCE = "moozzyk/MiniproUI @ 1.5.8"

_MINIPRO_VERSION = re.compile(r"minipro version\s+(\S+)")
_MINIPRO_COMMIT_KEYS = ["Commit date", "Git commit", "Git branch"]


@dataclass
class VisualMiniproInfo:
    details: list[KeyValuePair] = field(default_factory=list)
    version: str = APP_VERSION


class VisualMiniproInfoProcessor:
    @staticmethod
    def run(result: InvocationResult) -> VisualMiniproInfo:
        return VisualMiniproInfo(
            details=VisualMiniproInfoProcessor._app_details()
            + VisualMiniproInfoProcessor._minipro_details(result)
        )

    @staticmethod
    def _app_details() -> list[KeyValuePair]:
        return [
            KeyValuePair(key="Version", value=APP_VERSION),
            KeyValuePair(key="Ported from", value=UPSTREAM_REFERENCE),
        ]

    @staticmethod
    def _minipro_details(result: InvocationResult) -> list[KeyValuePair]:
        result_lines = [line for line in result.std_err.split("\n") if line]
        commit_info = [
            KeyValuePair(key=f"minipro {pair.key.lower()}", value=pair.value)
            for pair in extract_info(result_lines, _MINIPRO_COMMIT_KEYS)
        ]
        return VisualMiniproInfoProcessor._extract_minipro_version(result.std_err) + commit_info

    @staticmethod
    def _extract_minipro_version(std_err: str) -> list[KeyValuePair]:
        match = _MINIPRO_VERSION.search(std_err)
        if match is not None:
            return [KeyValuePair(key="minipro version", value=match.group(1))]
        return []
