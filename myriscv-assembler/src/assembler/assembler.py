import re
from pathlib import Path
from typing import TextIO

from assembler.assembly_error import AssemblyError
from assembler.instruction_error import InstructionError
from assembler.isa_processor import IsaProcessor


class Assembler:
    INSTRUCTION_REGEX = re.compile(
        r"^\s*(\S+)(?:\s+(\S+))?(?:\s*,\s*(\S+))?(?:\s*,\s*(\S+))?(?:\s*;.*)?$"
    )
    COMMENT_ONLY_REGEX = re.compile(r"^\s*(?:;.*)?$")

    _isa_processor: IsaProcessor

    def __init__(self, isa_path: Path) -> None:
        self._isa_processor = IsaProcessor(isa_path)

    def assembly(self, code: TextIO) -> bytes:
        result: bytes = b""
        for line_number, line in enumerate(code, start=1):
            line = line.rstrip("\r\n")
            if self.COMMENT_ONLY_REGEX.match(line) is not None:
                continue

            match = self.INSTRUCTION_REGEX.match(line)
            if match is None:
                column = len(line) - len(line.lstrip()) + 1
                raise AssemblyError(
                    "Invalid instruction", line=line_number, column=column
                )

            name, arg_0, arg_1, arg_2 = match.groups()
            assert name is not None

            args = [arg for arg in (arg_0, arg_1, arg_2) if arg is not None]
            try:
                result += self._isa_processor.generate_instruction(name, args)
            except InstructionError as error:
                column = match.start(1) + 1
                if error.argument_index is not None:
                    group = error.argument_index + 2
                    if group <= 4 and match.start(group) >= 0:
                        column = match.start(group) + 1
                    elif error.argument_index >= len(args):
                        column = len(line) + 1
                raise AssemblyError(
                    str(error), line=line_number, column=column
                ) from error

        return result
