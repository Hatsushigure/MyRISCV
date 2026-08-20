import unittest

from assembler.enums.instruction_argument_type import InstructionArgumentType
from assembler.instruction_error import InstructionError
from assembler.instruction_pattern import InstructionPattern
from assembler.validation_error import ValidationError


class TestInstructionPattern(unittest.TestCase):
    def test_extracts_name_types_and_named_arguments(self) -> None:
        pattern = InstructionPattern(
            "sw {value:reg}, {offset:12}({base:reg})"
        )

        self.assertEqual(pattern.name, "sw")
        self.assertEqual(
            pattern.arguments["value"].type, InstructionArgumentType.REGISTER
        )
        self.assertEqual(pattern.arguments["offset"].bits, 12)
        self.assertEqual(
            pattern.match("sw x5,  -4 ( x6 )"),
            {"value": ("x5", 3), "offset": ("-4", 8), "base": ("x6", 13)},
        )

    def test_rejects_argument_without_type(self) -> None:
        with self.assertRaisesRegex(
            ValidationError, "contains invalid argument.*expected"
        ):
            InstructionPattern("addi {rd}", path="pattern")

    def test_rejects_non_positive_constant_width(self) -> None:
        with self.assertRaisesRegex(ValidationError, "bit width must be positive"):
            InstructionPattern("addi {immediate:0}", path="pattern")

    def test_rejects_duplicate_argument(self) -> None:
        with self.assertRaisesRegex(ValidationError, "duplicate argument 'rd'"):
            InstructionPattern("add {rd:reg}, {rd:reg}", path="pattern")

    def test_requires_instruction_name(self) -> None:
        with self.assertRaisesRegex(ValidationError, "begin with an instruction name"):
            InstructionPattern("{rd:reg}", path="pattern")

    def test_requires_whitespace_after_instruction_name(self) -> None:
        with self.assertRaisesRegex(ValidationError, "separated.*by whitespace"):
            InstructionPattern("addi{rd:reg}", path="pattern")

    def test_reports_missing_next_argument(self) -> None:
        pattern = InstructionPattern(
            "addi {rd:reg}, {rs1:reg}, {immediate:12}"
        )

        with self.assertRaisesRegex(InstructionError, "Missing argument 'immediate'"):
            pattern.match("addi x1, x2")

    def test_requires_whitespace_between_whitespace_separated_arguments(self) -> None:
        pattern = InstructionPattern("pair {left:reg} {right:reg}")

        with self.assertRaises(InstructionError):
            pattern.match("pair leftright")


if __name__ == "__main__":
    unittest.main()
