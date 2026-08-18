import tempfile
import unittest
from pathlib import Path

from assembler.cli import main


class CLITestCase(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
