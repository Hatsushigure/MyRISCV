# MyRISCV Assembler

Assembler and command-line interface for the MyRISCV instruction set.

## Installation

From this directory, install the package with pip:

```powershell
python -m pip install .
```

Modules are imported from `assembler`, for example
`from assembler.assembler import Assembler`.

For development with Hatch:

```powershell
hatch run test
```

## Usage

Assemble a source file to a binary with the installed command:

```powershell
myriscv-assembler program.s
```

The default output is `program.bin`. Use `-o` to select another path and
`--isa` to replace the bundled ISA definition:

```powershell
myriscv-assembler program.s -o firmware.bin
myriscv-assembler program.s --isa custom-isa.json
```

The module entry point is also available:

```powershell
python -m assembler program.s
```
