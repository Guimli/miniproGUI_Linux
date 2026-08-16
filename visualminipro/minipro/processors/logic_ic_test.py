"""74xx/40xx logic IC test results.

Port of MiniproUI/Minipro/ResponseProcessors/LogicICTestProcessor.swift
(Visual Minipro 1.5.8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..errors import LogicICTestError, UnknownError
from ..invoker import InvocationResult
from .utils import ensure_no_error

_NUM_ERRORS = re.compile(r"Logic test failed: (\S+) errors encountered")
_LOGIC_IC_TEST_ERROR = re.compile(r"Error running the \S+ step of logic test.")


@dataclass
class LogicICTestResult:
    device: str
    num_errors: int
    test_vectors: list[list[str]] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.num_errors == 0


def _parse_test_vector(line: str) -> list[str]:
    """Reduce a vector row to one token per pin.

    minipro marks a failing pin by suffixing it with '-', so those keep two
    characters while passing pins keep one.
    """
    tokens = [token for token in line.split(" ") if token]
    tokens = tokens[1:-1] if len(tokens) >= 2 else []
    return [token[-2:] if token[-1:] == "-" else token[-1:] for token in tokens]


class LogicICTestProcessor:
    @staticmethod
    def run(result: InvocationResult, device: str) -> LogicICTestResult:
        test_error = _LOGIC_IC_TEST_ERROR.search(result.std_err)
        if test_error is not None:
            raise LogicICTestError(test_error.group(0))

        ensure_no_error(result)

        lines = [line for line in result.std_out_string.split("\n") if line]
        if not lines:
            raise UnknownError("Unexpected response format.")

        num_errors_match = _NUM_ERRORS.search(result.std_err)
        try:
            num_errors = int(num_errors_match.group(1)) if num_errors_match else 0
        except ValueError:
            num_errors = 0

        return LogicICTestResult(
            device=device,
            num_errors=num_errors,
            test_vectors=[_parse_test_vector(line) for line in lines[1:]],
        )
