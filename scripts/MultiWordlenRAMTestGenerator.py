"""Generate Logisim-evolution vectors for the multi-width RAM.

The circuit intentionally leaves the upper bits undefined for byte/halfword
reads, so those bits are marked ``x`` (ignored) in the expected output. Every
operation uses exactly one low/high clock pair. RAM output is checked only
while both OE and CLK are high.
"""

import argparse
import dataclasses
import random
import sys
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import TextIO

DEFAULT_COUNT = 1024
DEFAULT_SEED = 42
DEFAULT_OUTPUT = Path(__file__).parents[1] / "vectors" / "MultiWordlenRAMTest.txt"
RAM_SIZE = 1 << 26


class Width(IntEnum):
    EIGHT = 0
    SIXTEEN = 1
    THIRTY_TWO = 2
    INVALID = 3


@dataclass(frozen=True, kw_only=True, slots=True)
class Vector:
    funct3: int
    output_enable: bool
    write_enable: bool
    address: int
    write_data: int
    clk: bool
    output_data: int


ram: dict[int, int] = {}


def generate_vectors(count: int) -> Generator[Vector]:
    for _ in range(count):
        width = random.choice(list(Width))
        zero_extend = random.choice((True, False))
        output_enable = random.choices((True, False), (9, 1))[0]
        write_enable = random.choice((True, False))
        address = random.randint(0, RAM_SIZE - 1) & (0xFFFFFFFF << width)
        write_data = random.randint(0, 0xFFFFFFFF)
        clk = False
        output_data = 0
        yield Vector(
            funct3=width | (int(not zero_extend) << 2),
            output_enable=output_enable,
            write_enable=write_enable,
            address=address,
            write_data=write_data,
            clk=clk,
            output_data=output_data,
        )


def process_vectors(vectors: Iterable[Vector]) -> Generator[Vector]:
    for vector in vectors:
        # All input before rise will be ignored
        yield Vector(
            funct3=random.randint(0, 7),
            output_enable=random.choice((True, False)),
            write_enable=random.choice((True, False)),
            address=random.randint(0, RAM_SIZE - 1),
            write_data=random.randint(0, 0xFFFFFFFF),
            clk=False,
            output_data=0,
        )

        yield vector

        vector = dataclasses.replace(vector, clk=True)
        zero_extend = (vector.funct3 >> 2) & 1
        width = Width(vector.funct3 & 3)
        match width:
            case Width.EIGHT:
                if vector.write_enable:
                    ram[vector.address] = vector.write_data & 0xFF
                if vector.output_enable:
                    output_data = ram.get(vector.address, 0)
                    vector = dataclasses.replace(
                        vector,
                        output_data=output_data
                        | (0 if zero_extend else (output_data >> 7) * 0xFFFFFF00),
                    )
            case Width.SIXTEEN:
                if vector.write_enable:
                    ram[vector.address] = vector.write_data & 0xFF
                    ram[vector.address + 1] = (vector.write_data >> 8) & 0xFF
                if vector.output_enable:
                    output_data = ram.get(vector.address, 0) | (
                        ram.get(vector.address + 1, 0) << 8
                    )
                    vector = dataclasses.replace(
                        vector,
                        output_data=output_data
                        | (0 if zero_extend else (output_data >> 15) * 0xFFFF0000),
                    )
            case Width.THIRTY_TWO:
                if vector.write_enable:
                    ram[vector.address] = vector.write_data & 0xFF
                    ram[vector.address + 1] = (vector.write_data >> 8) & 0xFF
                    ram[vector.address + 2] = (vector.write_data >> 16) & 0xFF
                    ram[vector.address + 3] = (vector.write_data >> 24) & 0xFF
                if vector.output_enable:
                    output_data = (
                        ram.get(vector.address, 0)
                        | (ram.get(vector.address + 1, 0) << 8)
                        | (ram.get(vector.address + 2, 0) << 16)
                        | (ram.get(vector.address + 3, 0) << 24)
                    )
                    vector = dataclasses.replace(vector, output_data=output_data)
            case Width.INVALID:  # Invalid operation make no changes and always output 0
                vector = dataclasses.replace(vector, output_data=0)
        yield vector

        # All input after rise will be ignored
        yield Vector(
            funct3=random.randint(0, 7),
            output_enable=vector.output_enable,
            write_enable=random.choice((True, False)),
            address=random.randint(0, RAM_SIZE - 1),
            write_data=random.randint(0, 0xFFFFFFFF),
            clk=True,
            output_data=vector.output_data,
        )


def format_vector(vector: Vector) -> str:
    output_data: str = ""
    if (not vector.clk) or (not vector.output_enable):
        output_data = "   <DC>   "
    else:
        output_data = f"0x{vector.output_data:08X}"
    return (
        f"{int(vector.funct3):03b} "
        f"{int(vector.output_enable)} "
        f"{int(vector.write_enable)} "
        f"0x{vector.address:08X} "
        f"0x{vector.write_data:08X} "
        f"{int(vector.clk)} "
        f"{output_data}"
    )


def write_vectors(file: TextIO, vectors: Iterable[Vector]) -> None:
    file.write(
        "funct3[3] output_enable[1] write_enable[1] address[32] write_data[32] CLK[1] "
        "output_data[32] <set> <seq>\n"
    )
    file.writelines(f"{format_vector(v)} 1 {seq}\n" for seq, v in enumerate(vectors, 1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n", "--count", type=int, default=DEFAULT_COUNT, help="number of clock cycles"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="output path, or '-' for stdout",
    )
    args = parser.parse_args(argv)
    if args.count < 1:
        print("error: --count must be at least 1", file=sys.stderr)
        return 2

    random.seed(args.seed)

    vectors = process_vectors(generate_vectors(args.count))
    if str(args.output) == "-":
        write_vectors(sys.stdout, vectors)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="\n") as stream:
            write_vectors(stream, vectors)
        print(
            f"Generated {args.count * 4} vectors for {args.count} clock cycles "
            f"in {args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
