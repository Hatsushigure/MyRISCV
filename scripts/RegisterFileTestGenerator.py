"""Generate Logisim-evolution test vectors for the register file."""

import argparse
import random
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

MASK32 = 0xFFFFFFFF
REGISTER_COUNT = 32
ZERO_REGISTER = 0
DEFAULT_COUNT = 1024
DEFAULT_SEED = 20260808
DEFAULT_OUTPUT = Path(__file__).parents[1] / "vectors" / "RegisterFileTest.txt"


@dataclass(frozen=True, slots=True)
class Vector:
    output_address_0: int
    output_address_1: int
    write_enable: int
    write_address: int
    write_data: int
    clk: int
    output_data_0: int
    output_data_1: int


def _validate_register(address: int) -> int:
    if not 0 <= address < REGISTER_COUNT:
        raise ValueError(f"register address out of range: {address}")
    return address


def _make_vector(
    registers: list[int],
    read_address_0: int,
    read_address_1: int,
    write_enable: int,
    write_address: int,
    write_data: int,
    clk: int,
) -> Vector:
    read_address_0 = _validate_register(read_address_0)
    read_address_1 = _validate_register(read_address_1)
    write_address = _validate_register(write_address)
    return Vector(
        output_address_0=read_address_0,
        output_address_1=read_address_1,
        write_enable=write_enable,
        write_address=write_address,
        write_data=write_data & MASK32,
        clk=clk,
        output_data_0=registers[read_address_0],
        output_data_1=registers[read_address_1],
    )


def _emit_clock_cycle(
    vectors: list[Vector],
    registers: list[int],
    read_address_0: int,
    read_address_1: int,
    write_enable: int,
    write_address: int,
    write_data: int,
) -> None:
    """Emit stable-low setup and rising-edge rows for one register operation."""
    write_enable = int(bool(write_enable))
    vectors.append(
        _make_vector(
            registers,
            read_address_0,
            read_address_1,
            write_enable,
            write_address,
            write_data,
            0,
        )
    )

    if write_enable and write_address != ZERO_REGISTER:
        registers[write_address] = write_data & MASK32

    vectors.append(
        _make_vector(
            registers,
            read_address_0,
            read_address_1,
            write_enable,
            write_address,
            write_data,
            1,
        )
    )


def _directed_operations() -> list[tuple[int, int, int, int, int]]:
    return [
        (0, 1, 0, 0, 0x00000000),  # initial read; all registers start at 0
        (0, 0, 1, 0, 0x12345678),  # writes to hard-wired x0 are ignored
        (0, 1, 1, 1, 0x89ABCDEF),
        (1, 0, 1, 31, 0xFFFFFFFF),
        (31, 0, 0, 31, 0x00000000),  # disabled write must not change x31
        (31, 1, 1, 31, 0x80000000),
        (31, 31, 1, 0, 0xCAFEBABE),  # another ignored write to x0
        (0, 31, 0, 0, 0x00000000),
    ]


def generate_vectors(count: int, rng: random.Random) -> list[Vector]:
    if count < 1:
        raise ValueError("count must be at least 1")

    registers = [0] * REGISTER_COUNT
    vectors: list[Vector] = []
    operations = _directed_operations()[:count]

    while len(operations) < count:
        write_address = rng.randrange(REGISTER_COUNT)
        operations.append(
            (
                rng.randrange(REGISTER_COUNT),
                rng.randrange(REGISTER_COUNT),
                int(rng.random() < 0.75),
                write_address,
                rng.getrandbits(32),
            )
        )

    for operation in operations:
        _emit_clock_cycle(vectors, registers, *operation)
    return vectors


def format_vector(vector: Vector) -> str:
    return (
        f"{vector.output_address_0:05b} {vector.output_address_1:05b} "
        f"{vector.write_enable} {vector.write_address:05b} "
        f"0x{vector.write_data:08X} {vector.clk} "
        f"0x{vector.output_data_0:08X} 0x{vector.output_data_1:08X}"
    )


def write_vectors(
    stream: TextIO, vectors: Iterable[Vector], count: int, seed: int
) -> None:
    stream.write(f"# RegisterFile32 Test Vectors ({count} clock cycles)\n")
    stream.write(f"# Reproducible random seed: {seed}\n")
    stream.write(
        "# Each operation is emitted as CLK=0 setup followed by CLK=1 rising edge.\n"
    )
    stream.write(
        "# <set>/<seq> keep Logisim from resetting the circuit between rows.\n"
    )
    stream.write(
        "output_address_0[5] output_address_1[5] write_enable[1] "
        "write_address[5] write_data[32] CLK[1] "
        "output_data_0[32] output_data_1[32] <set> <seq>\n"
    )
    stream.writelines(
        f"{format_vector(vector)} 1 {seq}\n"
        for seq, vector in enumerate(vectors, start=1)
    )


def _parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid integer: {value}") from error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="number of clock cycles; each cycle emits CLK=0 and CLK=1 rows",
    )
    parser.add_argument(
        "--seed",
        type=_parse_int,
        default=DEFAULT_SEED,
        help="random seed (decimal or 0x-prefixed; default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="output path, or '-' for stdout (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.count < 1:
        print("error: --count must be at least 1", file=sys.stderr)
        return 2

    vectors = generate_vectors(args.count, random.Random(args.seed))
    if str(args.output) == "-":
        write_vectors(sys.stdout, vectors, args.count, args.seed)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="ascii", newline="\n") as stream:
            write_vectors(stream, vectors, args.count, args.seed)
        print(
            f"Generated {len(vectors)} vectors for {args.count} clock cycles in {args.output}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
