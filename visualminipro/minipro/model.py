"""Programmer model enum.

Port of MiniproUI/Minipro/ProgrammerModel.swift (Visual Minipro 1.5.8).
"""

from enum import Enum

from .errors import ProgrammerInfoUnavailable


class ProgrammerModel(Enum):
    TL866A = "TL866A"
    TL866CS = "TL866CS"
    TL866II_PLUS = "TL866II+"
    T48 = "T48"
    T56 = "T56"
    T76 = "T76"

    @property
    def is_algo_based(self) -> bool:
        """T56 and T76 need an algorithm database extracted from the Xgpro software."""
        return self in (ProgrammerModel.T56, ProgrammerModel.T76)

    @property
    def supports_firmware_update(self) -> bool:
        return self in (
            ProgrammerModel.TL866II_PLUS,
            ProgrammerModel.T48,
            ProgrammerModel.T56,
            ProgrammerModel.T76,
        )

    @staticmethod
    def parse(value: str) -> "ProgrammerModel":
        upper = value.upper()
        for model in ProgrammerModel:
            if model.value.upper() == upper:
                return model
        raise ProgrammerInfoUnavailable()
