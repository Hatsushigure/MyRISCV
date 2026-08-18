from enum import StrEnum, auto


class InstructionArgumentType(StrEnum):
    REGISTER = auto()
    CONSTANT = auto()
