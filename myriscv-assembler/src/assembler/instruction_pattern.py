import re
from typing import Pattern

from assembler.instruction_argument import InstructionArgument
from assembler.instruction_error import InstructionError
from assembler.validation_error import ValidationError


class InstructionPattern:
    _PLACEHOLDER = re.compile(
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*):(?P<type>reg|[0-9]+)"
    )

    def __init__(self, pattern: str, *, path: str = "") -> None:
        self._source = pattern
        self._arguments: dict[str, InstructionArgument] = {}
        parts = self._parse_parts(pattern, path=path)
        if not parts or parts[0][0] or not parts[0][1].strip():
            raise ValidationError(path, "must begin with an instruction name")

        leading_literal = parts[0][1]
        name_match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)", leading_literal)
        assert name_match is not None
        self._name = name_match.group(1).lower()
        name_suffix = leading_literal[name_match.end() :]
        if name_suffix.strip():
            raise ValidationError(
                path, "instruction name must be followed by whitespace or an argument"
            )
        if len(parts) > 1 and not any(
            character.isspace() for character in name_suffix
        ):
            raise ValidationError(
                path, "instruction name must be separated from arguments by whitespace"
            )

        delimiters = {
            character
            for is_placeholder, value in parts
            if not is_placeholder
            for character in value
            if not character.isalnum() and not character.isspace()
        }
        excluded = "".join(re.escape(character) for character in sorted(delimiters))
        operand = rf"[^\s{excluded}]+"
        regex_parts: list[str] = [r"^\s*"]
        completed_arguments: list[tuple[Pattern[str], str]] = []
        previous_placeholder = False
        for index, (is_placeholder, value) in enumerate(parts):
            if is_placeholder:
                if previous_placeholder:
                    raise ValidationError(path, "must separate adjacent arguments")
                regex_parts.append(rf"(?P<{value}>{operand})")
                if index + 2 < len(parts) and parts[index + 2][0]:
                    completed_arguments.append(
                        (
                            re.compile(
                                "".join(regex_parts) + r"\s*$", re.IGNORECASE
                            ),
                            parts[index + 2][1],
                        )
                    )
                previous_placeholder = True
            else:
                regex_parts.append(self._compile_literal(value))
                previous_placeholder = False
        regex_parts.append(r"\s*$")
        self._regex = re.compile("".join(regex_parts), re.IGNORECASE)
        self._completed_arguments = completed_arguments

    def _parse_parts(
        self, pattern: str, *, path: str
    ) -> list[tuple[bool, str]]:
        parts: list[tuple[bool, str]] = []
        literal_start = 0
        position = 0
        while position < len(pattern):
            if pattern[position] != "{":
                if pattern[position] == "}":
                    raise ValidationError(path, "contains an unmatched '}'")
                position += 1
                continue

            if literal_start < position:
                parts.append((False, pattern[literal_start:position]))
            end = pattern.find("}", position + 1)
            if end < 0:
                raise ValidationError(path, "contains an unmatched '{'")

            placeholder = pattern[position + 1 : end]
            match = self._PLACEHOLDER.fullmatch(placeholder)
            if match is None:
                raise ValidationError(
                    path,
                    f"contains invalid argument '{{{placeholder}}}'; expected "
                    "'{name:reg}' or '{name:positive-bits}'",
                )
            name = match.group("name")
            if name in self._arguments:
                raise ValidationError(path, f"contains duplicate argument '{name}'")
            self._arguments[name] = InstructionArgument.from_spec(
                match.group("type"), path=path
            )
            parts.append((True, name))
            position = end + 1
            literal_start = position

        if literal_start < len(pattern):
            parts.append((False, pattern[literal_start:]))
        return parts

    @staticmethod
    def _compile_literal(literal: str) -> str:
        result: list[str] = []
        position = 0
        while position < len(literal):
            if literal[position].isspace():
                end = position + 1
                while end < len(literal) and literal[end].isspace():
                    end += 1
                previous = literal[position - 1] if position > 0 else ""
                following = literal[end] if end < len(literal) else ""
                adjacent_to_punctuation = any(
                    character and not character.isalnum() and character != "_"
                    for character in (previous, following)
                )
                result.append(r"\s*" if adjacent_to_punctuation else r"\s+")
                position = end
                continue

            character = literal[position]
            if not character.isalnum() and character != "_":
                result.extend((r"\s*", re.escape(character), r"\s*"))
            else:
                result.append(re.escape(character))
            position += 1
        return "".join(result)

    @property
    def arguments(self) -> dict[str, InstructionArgument]:
        return self._arguments.copy()

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> str:
        return self._source

    def match(self, instruction: str) -> dict[str, tuple[str, int]]:
        match = self._regex.fullmatch(instruction)
        if match is None:
            for prefix, next_name in reversed(self._completed_arguments):
                if prefix.fullmatch(instruction) is not None:
                    raise InstructionError(
                        f"Missing argument '{next_name}'",
                        source_offset=len(instruction.rstrip()),
                    )
            raise InstructionError(
                f"Instruction does not match pattern '{self._source}'",
                source_offset=len(instruction.rstrip()),
            )

        return {
            name: (match.group(name), match.start(name))
            for name in self._arguments
        }
