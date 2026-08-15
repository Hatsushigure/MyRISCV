#!/usr/bin/env python
"""Generate Logisim-evolution test vectors for the RV32I Instruction Decoder."""

import argparse
import dataclasses
import random
import sys
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from enum import IntEnum, auto
from pathlib import Path
from typing import TextIO


class OpcodeType(IntEnum):
    I = auto()
    S = auto()
    B = auto()
    J = auto()
    R = auto()
    U = auto()
    INVALID = auto()


@dataclass(frozen=True, slots=True, kw_only=True)
class Vector:
    instruction: int
    opcode: int = 0
    rd: int = 0
    funct3: int = 0
    rs1: int = 0
    rs2: int = 0
    funct7: int = 0
    immediate: int = 0


DEFAULT_COUNT = 1024
DEFAULT_SEED = 42
DEFAULT_OUTPUT = Path(__file__).parents[1] / "vectors" / "InstructionDecoderTest.txt"
VALID_OPCODES = {
    0b0000011: OpcodeType.I,
    0b0100011: OpcodeType.S,
    0b1100011: OpcodeType.B,
    0b1100111: OpcodeType.I,
    0b0001111: OpcodeType.I,
    0b1101111: OpcodeType.J,
    0b0010011: OpcodeType.I,
    0b0110011: OpcodeType.R,
    0b0010111: OpcodeType.U,
    0b0110111: OpcodeType.U,
}
MASK_1B = 0x1
MASK_3B = 0x7
MASK_4B = 0xF
MASK_5B = 0x1F
MASK_6B = 0x3F
MASK_7B = 0x7F
MASK_8B = 0xFF
MASK_11B = 0x7FF


def generate_vectors(count: int, rng: random.Random) -> Generator[Vector]:
    for _ in range(count):
        opcode = rng.choice(list(VALID_OPCODES.keys()))
        yield Vector(instruction=(rng.randint(0, 0x1FFFFFF) << 7) | opcode)


def parse_immediate(instruction: int) -> int:
    opcode = instruction & MASK_7B
    opcode_type = VALID_OPCODES.get(opcode, OpcodeType.INVALID)
    match opcode_type:
        case OpcodeType.I:
            return (
                ((instruction >> 20) & MASK_1B)
                | ((instruction >> 21 & MASK_4B) << 1)
                | ((instruction >> 25 & MASK_6B) << 5)
                | ((instruction >> 31 & MASK_1B) << 11)
                | (((instruction >> 31 & MASK_1B) * MASK_8B) << 12)
                | (((instruction >> 31 & MASK_1B) * MASK_11B) << 20)
                | ((instruction >> 31 & MASK_1B) << 31)
            )
        case OpcodeType.S:
            return (
                ((instruction >> 7) & MASK_1B)
                | ((instruction >> 8 & MASK_4B) << 1)
                | ((instruction >> 25 & MASK_6B) << 5)
                | ((instruction >> 31 & MASK_1B) << 11)
                | (((instruction >> 31 & MASK_1B) * MASK_8B) << 12)
                | (((instruction >> 31 & MASK_1B) * MASK_11B) << 20)
                | ((instruction >> 31 & MASK_1B) << 31)
            )
        case OpcodeType.B:
            return (
                0
                | ((instruction >> 8 & MASK_4B) << 1)
                | ((instruction >> 25 & MASK_6B) << 5)
                | ((instruction >> 7 & MASK_1B) << 11)
                | (((instruction >> 31 & MASK_1B) * MASK_8B) << 12)
                | (((instruction >> 31 & MASK_1B) * MASK_11B) << 20)
                | ((instruction >> 31 & MASK_1B) << 31)
            )
        case OpcodeType.J:
            return (
                0
                | ((instruction >> 21 & MASK_4B) << 1)
                | ((instruction >> 25 & MASK_6B) << 5)
                | ((instruction >> 20 & MASK_1B) << 11)
                | ((instruction >> 12 & MASK_8B) << 12)
                | (((instruction >> 31 & MASK_1B) * MASK_11B) << 20)
                | ((instruction >> 31 & MASK_1B) << 31)
            )
        case OpcodeType.R:
            return 0
        case OpcodeType.U:
            return (
                0
                | 0
                | 0
                | 0
                | ((instruction >> 12 & MASK_8B) << 12)
                | ((instruction >> 20 & MASK_11B) << 20)
                | ((instruction >> 31 & MASK_1B) << 31)
            )
        case OpcodeType.INVALID:
            raise ValueError(f"Unknown opcode {opcode:07b}")


def process_vector(vector: Vector) -> Vector:
    instruction = vector.instruction
    return dataclasses.replace(
        vector,
        opcode=instruction & MASK_7B,
        rd=(instruction >> 7) & MASK_5B,
        funct3=(instruction >> 12) & MASK_3B,
        rs1=(instruction >> 15) & MASK_5B,
        rs2=(instruction >> 20) & MASK_5B,
        funct7=(instruction >> 25) & MASK_7B,
        immediate=parse_immediate(instruction),
    )


def format_vector(vector: Vector) -> str:
    assert vector.opcode in VALID_OPCODES
    opcode_type = VALID_OPCODES.get(vector.opcode)
    return " ".join(
        (
            f"0x{vector.instruction:08X}",
            f"{vector.opcode:07b}",
            "<DC>"
            if opcode_type in (OpcodeType.S, OpcodeType.B)
            else f"{vector.rd:05b}",
            "<DC>"
            if opcode_type in (OpcodeType.U, OpcodeType.J)
            else f"{vector.funct3:03b}",
            "<DC>"
            if opcode_type in (OpcodeType.U, OpcodeType.J)
            else f"{vector.rs1:05b}",
            "<DC>"
            if opcode_type in (OpcodeType.I, OpcodeType.U, OpcodeType.J)
            else f"{vector.rs2:05b}",
            f"{vector.funct7:07b}" if opcode_type == OpcodeType.R else "<DC>",
            "<DC>" if opcode_type == OpcodeType.R else f"0x{vector.immediate:08X}",
        )
    )


def write_vectors(stream: TextIO, vectors: Iterable[Vector], seed: int):
    stream.writelines(
        (
            "# RV32I Instruction Decoder Test Vectors\n",
            f"# Reproducable seed: {seed}\n",
            "instruction[32] opcode[7] rd[5] funct3[3] rs1[5] rs2[5] funct7[7] immediate[32]\n",
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
