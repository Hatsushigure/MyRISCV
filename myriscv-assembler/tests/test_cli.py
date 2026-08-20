import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from assembler.assembler import Assembler
from assembler.cli import _format_logisim_hex, main
from assembler.instruction_error import InstructionError
from assembler.isa_processor import IsaProcessor
from assembler.validation_error import ValidationError


class TestCli(unittest.TestCase):
    def test_assembles_standard_load_and_store_addressing(self) -> None:
        isa_path = Path(__file__).parents[1] / "src" / "assembler" / "isa.json"
        assembler = Assembler(isa_path)

        self.assertEqual(
            assembler.assembly(io.StringIO("lw x5, -4(x6)\nsw x5,-4 ( x6 )\n")),
            bytes.fromhex("83 22 C3 FF 23 2E 53 FE"),
        )

    def test_rejects_legacy_load_store_operand_order(self) -> None:
        isa_path = Path(__file__).parents[1] / "src" / "assembler" / "isa.json"
        processor = IsaProcessor(isa_path)

        with self.assertRaisesRegex(InstructionError, "does not match pattern"):
            processor.generate_instruction("lw x5, x6, -4")

    def test_isa_processor_raises_instruction_error(self) -> None:
        isa_path = Path(__file__).parents[1] / "src" / "assembler" / "isa.json"
        processor = IsaProcessor(isa_path)

        with self.assertRaisesRegex(
            InstructionError, "Undefined instruction 'not_an_instruction'"
        ):
            processor.generate_instruction("not_an_instruction")

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

    def test_writes_default_logisim_hex_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            source_path.write_text("addi x0, x0, 0\n", encoding="utf-8")

            self.assertEqual(main([str(source_path)]), 0)
            self.assertEqual(
                source_path.with_suffix(".hex").read_text(encoding="ascii"),
                "v3.0 hex words addressed\n00: 13 00 00 00\n",
            )

    def test_writes_explicit_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            output_path = Path(temp_dir) / "firmware.img"
            source_path.write_text("lui x0, 0xFFFFF000\n", encoding="utf-8")

            self.assertEqual(
                main([str(source_path), "--output", str(output_path)]), 0
            )
            self.assertEqual(
                output_path.read_text(encoding="ascii"),
                "v3.0 hex words addressed\n00: 37 F0 FF FF\n",
            )

    def test_splits_output_into_four_byte_lane_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            output_path = Path(temp_dir) / "firmware.img"
            source_path.write_text(
                "addi x0, x0, 0\nlui x0, 0xFFFFF000\n", encoding="utf-8"
            )

            self.assertEqual(
                main(
                    [
                        str(source_path),
                        "--output",
                        str(output_path),
                        "--split-output",
                    ]
                ),
                0,
            )
            self.assertFalse(output_path.exists())
            self.assertEqual(
                (Path(temp_dir) / "firmware.0.img").read_text(encoding="ascii"),
                "v3.0 hex words addressed\n00: 13 37\n",
            )
            self.assertEqual(
                (Path(temp_dir) / "firmware.1.img").read_text(encoding="ascii"),
                "v3.0 hex words addressed\n00: 00 F0\n",
            )
            self.assertEqual(
                (Path(temp_dir) / "firmware.2.img").read_text(encoding="ascii"),
                "v3.0 hex words addressed\n00: 00 FF\n",
            )
            self.assertEqual(
                (Path(temp_dir) / "firmware.3.img").read_text(encoding="ascii"),
                "v3.0 hex words addressed\n00: 00 FF\n",
            )

    def test_writes_eight_bytes_per_addressed_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            source_path.write_text("addi x0, x0, 0\n" * 3, encoding="utf-8")

            self.assertEqual(main([str(source_path)]), 0)
            self.assertEqual(
                source_path.with_suffix(".hex").read_text(encoding="ascii"),
                "v3.0 hex words addressed\n"
                "00: 13 00 00 00 13 00 00 00\n"
                "08: 13 00 00 00\n",
            )

    def test_formats_hexadecimal_addresses_in_uppercase(self) -> None:
        formatted = _format_logisim_hex(bytes(0xA1))

        self.assertIn("A0: 00\n", formatted)

    def test_does_not_write_output_when_assembly_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "invalid.s"
            output_path = source_path.with_suffix(".hex")
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

    def test_reports_invalid_argument_type_in_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "program.s"
            isa_path = Path(temp_dir) / "isa.json"
            source_path.write_text("", encoding="utf-8")
            isa_path.write_text(
                json.dumps(
                    {
                        "registers": {},
                        "templates": {},
                        "instructions": [
                            {
                                "pattern": "broken {target:label}",
                                "template": "unused",
                                "template_binds": {},
                            }
                        ],
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
                f"{isa_path}: error: instructions[0].pattern: contains invalid "
                "argument '{target:label}'; expected '{name:reg}' or "
                "'{name:positive-bits}'\n",
            )

    def test_reports_invalid_instruction_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            isa_path = Path(temp_dir) / "isa.json"
            isa_path.write_text(
                json.dumps(
                    {
                        "registers": {},
                        "templates": {},
                        "instructions": [
                            {
                                "pattern": "broken {target:reg}, {offset}",
                                "template": "unused",
                                "template_binds": {},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValidationError,
                r"instructions\[0\].pattern: contains invalid argument",
            ):
                IsaProcessor(isa_path)


if __name__ == "__main__":
    unittest.main()
