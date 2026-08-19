import argparse
import json
import sys
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from assembler.assembler import Assembler
from assembler.assembly_error import AssemblyError
from assembler.validation_error import ValidationError


def _print_error(
    program: str,
    error: object,
    *,
    path: Path | None = None,
    line: int | None = None,
    column: int | None = None,
) -> None:
    location = str(path) if path is not None else program
    if line is not None:
        location += f":{line}"
        if column is not None:
            location += f":{column}"
    print(f"{location}: error: {error}", file=sys.stderr)


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
    isa_error_path = args.isa

    try:
        if args.isa is None:
            isa_resource = resources.files("assembler").joinpath("isa.json")
            with resources.as_file(isa_resource) as isa_path:
                isa_error_path = isa_path
                assembler = Assembler(isa_path)
        else:
            assembler = Assembler(args.isa)
    except json.JSONDecodeError as error:
        _print_error(
            parser.prog,
            error.msg,
            path=isa_error_path,
            line=error.lineno,
            column=error.colno,
        )
        return 1
    except ValidationError as error:
        _print_error(parser.prog, error, path=isa_error_path)
        return 1
    except (OSError, UnicodeError) as error:
        _print_error(parser.prog, error, path=isa_error_path)
        return 1

    try:
        with args.source.open("r", encoding="utf-8") as source:
            binary = assembler.assembly(source)
    except AssemblyError as error:
        _print_error(
            parser.prog,
            error,
            path=args.source,
            line=error.line,
            column=error.column,
        )
        return 1
    except (OSError, UnicodeError) as error:
        _print_error(parser.prog, error, path=args.source)
        return 1

    try:
        output_path.write_bytes(binary)
    except OSError as error:
        _print_error(parser.prog, error, path=output_path)
        return 1

    return 0
