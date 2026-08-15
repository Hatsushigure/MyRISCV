"""Generate Logisim-evolution test vectors for the RV32I ALU."""

import argparse
import dataclasses
import random
import sys
from collections.abc import Generator, Iterable
from ctypes import c_int32, c_uint8, c_uint32
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

DEFAULT_COUNT = 1024
DEFAULT_SEED = 20260808
DEFAULT_OUTPUT = Path(__file__).parents[1] / "vectors" / "ALUTest.txt"


@dataclass(frozen=True, slots=True, kw_only=True)
class Vector:
    is_R: bool
    special_bit: bool
    funct3: c_uint8
    A: c_int32
    B: c_int32
    result: c_int32


def generate_vectors(count: int, rng: random.Random) -> Generator[Vector]:
    for _ in range(count):
        is_R = rng.choice((False, True))
        special_bit = rng.choice((False, True))
        funct3 = c_uint8(rng.randint(0, 7))
        A = c_int32(rng.randint(0, 0xFFFFFFFF))
        B = c_int32(rng.randint(0, 0xFFFFFFFF))
        yield Vector(
            is_R=is_R,
            special_bit=special_bit,
            funct3=funct3,
            A=A,
            B=B,
            result=c_int32(0),
        )


def add(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(x.value + y.value)


def sub(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(x.value - y.value)


def sll(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(c_uint32(x.value).value << (c_uint32(y.value).value & 0x1F))


def slt(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(x.value < y.value)


def sltu(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(c_uint32(x.value).value < c_uint32(y.value).value)


def xor(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(x.value ^ y.value)


def srl(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(c_uint32(x.value).value >> (c_uint32(y.value).value & 0x1F))


def sra(x: c_int32, y: c_int32) -> c_int32:
    result = x.value
    shamt = c_uint32(y.value).value & 0x1F
    for _ in range(shamt):
        result //= 2
    return c_int32(result)


def or_(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(x.value | y.value)


def and_(x: c_int32, y: c_int32) -> c_int32:
    return c_int32(x.value & y.value)


def process_vector(vector: Vector) -> Vector:
    FUNCTIONS = {
        0b000: add,
        0b001: sll,
        0b010: slt,
        0b011: sltu,
        0b100: xor,
        0b101: srl,
        0b110: or_,
        0b111: and_,
    }

    result: c_int32 = c_int32(0)
    if vector.funct3.value == 0b000 and vector.special_bit and vector.is_R:
        result = sub(vector.A, vector.B)
    elif vector.funct3.value == 0b101 and vector.special_bit:
        result = sra(vector.A, vector.B)
    else:
        result = FUNCTIONS[vector.funct3.value](vector.A, vector.B)

    return dataclasses.replace(vector, result=result)


def format_vector(vector: Vector):
    return " ".join(
        (
            f"{int(vector.is_R):01b}",
            f"{int(vector.special_bit):01b}",
            f"{vector.funct3.value:03b}",
            f"0x{c_uint32(vector.A.value).value:08X}",
            f"0x{c_uint32(vector.B.value).value:08X}",
            f"0x{c_uint32(vector.result.value).value:08X}",
        )
    )


def write_vectors(stream: TextIO, vectors: Iterable[Vector], seed: int):
    stream.writelines(
        (
            "# RV32I ALU Test Vectors\n",
            f"# Reproducible random seed: {seed}\n",
            "is_R[1] special_bit[1] funct3[3] A[32] B[32] result[32]\n",
        )
    )
    stream.writelines(f"{format_vector(process_vector(v))}\n" for v in vectors)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-n", "--count", type=int, default=DEFAULT_COUNT, help="number of vectors"
    )
    parser.add_argument(
        "--seed",
        type=int,
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
        write_vectors(sys.stdout, vectors, args.seed)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="\n") as stream:
            write_vectors(stream, vectors, args.seed)
        print(f"Generated {args.count} vectors in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
