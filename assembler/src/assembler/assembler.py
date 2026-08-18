import re
from pathlib import Path
from typing import TextIO

from assembler.isa_processor import ISAProcessor


class Assembler:
    INSTRUCTION_REGEX = re.compile(
        r"^\s*(\S+)(?:\s+(\S+))?(?:\s*,\s*(\S+))?(?:\s*,\s*(\S+))?(?:\s*;.*)?$"
    )
    COMMENT_ONLY_REGEX = re.compile(r"^\s*(?:;.*)?$")

    _isa_processor: ISAProcessor

    def __init__(self, isa_path: Path) -> None:
        self._isa_processor = ISAProcessor(isa_path)

    def assembly(self, code: TextIO) -> bytes:
        result: bytes = b""
        for line in code:
            line = line.strip("\n")
            if self.COMMENT_ONLY_REGEX.match(line) is not None:
                continue

            match = self.INSTRUCTION_REGEX.match(line)
            if match is None:
                raise ValueError("Invalid instruction")

            name, arg_0, arg_1, arg_2 = match.groups()
            assert name is not None

            args = [arg for arg in (arg_0, arg_1, arg_2) if arg is not None]
            result += self._isa_processor.generate_instruction(name, args)

        return result
