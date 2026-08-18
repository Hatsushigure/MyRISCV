import argparse
import sys
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from assembler.assembler import Assembler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="myriscv-assembler",
        description="Assemble a source file into a binary file.",
    )
    parser.add_argument("source", type=Path, help="assembly source file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output binary file (default: source path with a .bin suffix)",
    )
    parser.add_argument(
        "--isa",
        type=Path,
        help="ISA definition file (default: bundled MyRISCV ISA)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path = args.output or args.source.with_suffix(".bin")

    try:
        if args.isa is None:
            isa_resource = resources.files("assembler").joinpath("isa.json")
            with resources.as_file(isa_resource) as isa_path:
                assembler = Assembler(isa_path)
        else:
            assembler = Assembler(args.isa)

        with args.source.open("r", encoding="utf-8") as source:
            binary = assembler.assembly(source)
        output_path.write_bytes(binary)
    except (OSError, TypeError, ValueError, UnicodeError) as error:
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 1

    return 0
