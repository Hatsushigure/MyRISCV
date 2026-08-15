#!/usr/bin/env python
"""Generate Logisim-evolution test vectors for the RV32I ALU Controller."""

import argparse
import dataclasses
import random
import sys
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

DEFAULT_COUNT = 1024
DEFAULT_SEED = 42
DEFAULT_OUTPUT = Path(__file__).parents[1] / "vectors" / "ALUControllerTest.txt"
ALU_OPERATIONS = {
    "LUI": 0b0110111,
    "LOAD": 0b0000011,
    "STORE": 0b0100011,
    "OP-IMM": 0b0010011,
    "OP": 0b0110011,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class Vector:
    opcode: int
    funct3_in: int
    funct7: int
    rs1_data: int
    rs2_data: int
    immediate: int
    special_bit: bool
    is_R: bool
    funct3: int
    A: int
    B: int


def generate_vectors(count: int, rng: random.Random) -> Generator[Vector]:
    for _ in range(count):
        funct7 = rng.randint(0, 0b1111111)
        yield Vector(
            opcode=rng.choice(list(ALU_OPERATIONS.values())),
            funct3_in=rng.randint(0, 0b111),
            funct7=funct7,
            rs1_data=rng.randint(0, 0xFFFFFFFF),
            rs2_data=rng.randint(0, 0xFFFFFFFF),
            immediate=rng.randint(0, 0xFFFFFFFF),
            special_bit=bool((funct7 >> 5) & 1),
            is_R=True,
            funct3=0,
            A=0,
            B=0,
        )


def process_vector(vector: Vector) -> Vector:
    if vector.opcode == ALU_OPERATIONS["LUI"]:
        return dataclasses.replace(
            vector, is_R=False, funct3=0, A=0, B=vector.immediate
        )
    elif vector.opcode in (ALU_OPERATIONS["LOAD"], ALU_OPERATIONS["STORE"]):
        return dataclasses.replace(
            vector, is_R=False, funct3=0, A=vector.rs1_data, B=vector.immediate
        )
    elif vector.opcode == ALU_OPERATIONS["OP-IMM"]:
        return dataclasses.replace(
            vector,
            is_R=False,
            funct3=vector.funct3_in,
            A=vector.rs1_data,
            B=vector.immediate,
        )
    elif vector.opcode == ALU_OPERATIONS["OP"]:
        return dataclasses.replace(
            vector,
            is_R=True,
            funct3=vector.funct3_in,
            A=vector.rs1_data,
            B=vector.rs2_data,
        )
    else:
        raise ValueError(f"Unknown opcode for ALU: {vector.opcode}")


def format_vector(vector: Vector):
    return " ".join(
        (
            f"{vector.opcode:07b}",
            f"{vector.funct3_in:03b}",
            f"{vector.funct7:07b}",
            f"0x{vector.rs1_data:08X}",
            f"0x{vector.rs2_data:08X}",
            f"0x{vector.immediate:08X}",
            f"{vector.special_bit:1b}",
            f"{vector.is_R:1b}",
            f"{vector.funct3:03b}",
            f"0x{vector.A:08X}",
            f"0x{vector.B:08X}",
        )
    )


def write_vectors(stream: TextIO, vectors: Iterable[Vector], seed: int):
    stream.writelines(
        (
            "# RV32I ALU Controller Test Vectors\n",
            f"# Reproducable seed: {seed}\n",
            "opcode[7] funct3_in[3] funct7[7] rs1_data[32] rs2_data[32] immediate[32] ",
            "special_bit[1] is_R[1] funct3[3] A[32] B[32]\n",
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
