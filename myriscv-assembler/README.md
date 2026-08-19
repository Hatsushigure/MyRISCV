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

Assemble a source file to a Logisim addressed hex image with the installed
command:

```powershell
myriscv-assembler program.s
```

The default output is `program.hex`. Its contents use Logisim's
`v3.0 hex words addressed` text format, with eight bytes per row. Use `-o` to
select another path and `--isa` to replace the bundled ISA definition:

```powershell
myriscv-assembler program.s -o firmware.hex
myriscv-assembler program.s --isa custom-isa.json
```

Use `--split-output` to write four byte-lane hex images instead of one combined
image. Each successive byte is assigned to lanes 0 through 3, so bytes
`1 2 3 4 5 6 7 8` become `1 5`, `2 6`, `3 7`, and `4 8` respectively:

```powershell
myriscv-assembler program.s --split-output
```

This creates `program.0.hex`, `program.1.hex`, `program.2.hex`, and
`program.3.hex`. An explicit output such as `-o firmware.img` creates
`firmware.0.img` through `firmware.3.img`.

The module entry point is also available:

```powershell
python -m assembler program.s
```
