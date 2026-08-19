import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from assembler.cli import main
from assembler.instruction_error import InstructionError
from assembler.isa_processor import IsaProcessor
from assembler.validation_error import ValidationError


class TestCli(unittest.TestCase):
    def test_isa_processor_raises_instruction_error(self) -> None:
        isa_path = Path(__file__).parents[1] / "src" / "assembler" / "isa.json"
        processor = IsaProcessor(isa_path)

        with self.assertRaisesRegex(
            InstructionError, "Undefined instruction 'not_an_instruction'"
        ):
            processor.generate_instruction("not_an_instruction", [])

    def test_isa_processor_raises_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isa_path = Path(temp_dir) / "isa.json"
            isa_path.write_text(
                json.dumps(
                    {"registers": [], "templates": {}, "instructions": {}}
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValidationError, "registers: must be a map"
            ):
                IsaProcessor(isa_path)

    def test_writes_default_binary_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            source_path.write_text("addi x0, x0, 0\n", encoding="utf-8")

            self.assertEqual(main([str(source_path)]), 0)
            self.assertEqual(
                source_path.with_suffix(".bin").read_bytes(), bytes.fromhex("13000000")
            )

    def test_writes_explicit_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            output_path = Path(temp_dir) / "firmware.img"
            source_path.write_text("lui x0, 0xFFFFF000\n", encoding="utf-8")

            self.assertEqual(
                main([str(source_path), "--output", str(output_path)]), 0
            )
            self.assertEqual(output_path.read_bytes(), bytes.fromhex("37f0ffff"))

    def test_does_not_write_output_when_assembly_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalid.s"
            output_path = source_path.with_suffix(".bin")
            source_path.write_text("not_an_instruction\n", encoding="utf-8")

            self.assertEqual(main([str(source_path)]), 1)
            self.assertFalse(output_path.exists())

    def test_reports_source_location_for_unknown_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalid.s"
            source_path.write_text("  not_an_instruction\n", encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                self.assertEqual(main([str(source_path)]), 1)

            self.assertEqual(
                stderr.getvalue(),
                f"{source_path}:1:3: error: Undefined instruction "
                "'not_an_instruction'\n",
            )

    def test_reports_operand_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalid.s"
            source_path.write_text(
                "; valid comment\naddi x0, invalid, 0\n", encoding="utf-8"
            )
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                self.assertEqual(main([str(source_path)]), 1)

            self.assertEqual(
                stderr.getvalue(),
                f"{source_path}:2:10: error: Unknown register 'invalid'\n",
            )

    def test_reports_line_end_for_missing_operand(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalid.s"
            source_path.write_text("addi x0, x0\n", encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                self.assertEqual(main([str(source_path)]), 1)

            self.assertEqual(
                stderr.getvalue(),
                f"{source_path}:1:12: error: Missing argument 'immediate'\n",
            )

    def test_reports_json_location_for_invalid_custom_isa(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            isa_path = Path(temp_dir) / "isa.json"
            source_path.write_text("addi x0, x0, 0\n", encoding="utf-8")
            isa_path.write_text('{\n  "registers":,\n}', encoding="utf-8")
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                self.assertEqual(
                    main([str(source_path), "--isa", str(isa_path)]), 1
                )

            self.assertEqual(
                stderr.getvalue(),
                f"{isa_path}:2:15: error: Expecting value\n",
            )

    def test_reports_field_path_for_invalid_isa_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            isa_path = Path(temp_dir) / "isa.json"
            source_path.write_text("", encoding="utf-8")
            isa_path.write_text(
                json.dumps(
                    {
                        "registers": {},
                        "templates": {"broken": {"arguments": []}},
                        "instructions": {},
                    }
                ),
                encoding="utf-8",
            )
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                self.assertEqual(
                    main([str(source_path), "--isa", str(isa_path)]), 1
                )

            self.assertEqual(
                stderr.getvalue(),
                f"{isa_path}: error: templates.broken.arguments: must be a map\n",
            )

    def test_reports_deep_field_path_for_invalid_argument_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            isa_path = Path(temp_dir) / "isa.json"
            source_path.write_text("", encoding="utf-8")
            isa_path.write_text(
                json.dumps(
                    {
                        "registers": {},
                        "templates": {},
                        "instructions": {
                            "broken": {
                                "arguments": {"target": {"type": "label"}},
                                "template": "unused",
                                "template_binds": {},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                self.assertEqual(
                    main([str(source_path), "--isa", str(isa_path)]), 1
                )

            self.assertEqual(
                stderr.getvalue(),
                f"{isa_path}: error: instructions.broken.arguments.target.type: "
                "must be 'register' or 'constant'\n",
            )


if __name__ == "__main__":
    unittest.main()
