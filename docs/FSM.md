# 六状态多周期 CPU 控制器

本设计使用 7 个状态完成 RV32I 基本指令。RAM 为同步读，数据输出在取指状态末的
上升沿更新；寄存器堆和指令译码器为组合逻辑。`DECODE` 阶段直接使用稳定的 RAM
输出进行译码，并在该阶段末锁存 `IR`。ALU 结果和加载数据仍经过中间寄存器，
避免把 ALU、RAM 与寄存器堆写回串成过长的组合路径。

状态转换总览：

```text
                         +-> ALU_WB --------+
                         |                  |
FETCH -> DECODE -> EXEC -+                  +-> FETCH
   |                     |                  |
   |                     +-> MEM -> LOAD_WB-+
   |                              |
   |                              +----------+  (STORE)
   |
   +----------> CTRL -----------------------+
```

## 1. 状态编码

状态寄存器使用 3 bit。复位时进入 `FETCH`。

| 编码 | 状态 | 作用 |
| --- | --- | --- |
| `000` | `FETCH` | 启动同步 RAM 读、保存指令地址、顺序更新 PC |
| `001` | `DECODE` | 直接译码稳定的 RAM 输出，并锁存 IR |
| `010` | `EXEC` | ALU 运算或计算访存地址 |
| `011` | `ALU_WB` | 将 `ALUOut` 写回寄存器 |
| `100` | `MEM` | 读取或写入数据 RAM |
| `101` | `LOAD_WB` | 扩展加载结果并写回寄存器 |
| `110` | `CTRL` | 处理 JAL、JALR 和 BRANCH |

`111` 为非法状态，下一拍无条件回到 `FETCH`，且不得产生任何写使能。

## 2. 中间寄存器

| 寄存器 | 宽度 | 写入状态 | 内容 |
| --- | --- | --- | --- |
| `IR` | 32 bit | `DECODE` | DECODE 阶段末锁存的 RAM 输出指令 |
| `instr_pc` | 32 bit | `FETCH` | 当前指令的地址，即更新前的 `PC` |
| `ALUOut` | 32 bit | `EXEC` | ALU 运算结果或有效地址 |
| `MDR` | 32 bit | `MEM` 中的 LOAD | RAM 组合读出的原始数据 |

DECODE 阶段的 `opcode`、`rd`、`funct3`、`funct7`、`rs1`、`rs2` 和立即数直接从
稳定的 `RAM_output` 解码；其余状态全部从 `IR` 解码。寄存器堆读口是组合读口，
不需要保存 `rs1_data` 和 `rs2_data`。

## 3. 控制信号默认值

组合控制器应先设置以下默认值，再按状态覆盖：

```text
IR_write                  = false
instr_pc_write            = false
ALUOut_write              = false
MDR_write                 = false
PC_write                  = false
Register_File_write_enable = false
RAM_output_enable         = false
RAM_write_enable          = false
next_state                = FETCH
```

这样可以保证未使用状态、非法指令以及未显式处理的 `funct3` 不会修改 PC、寄存器
或 RAM。对合法指令，`x0` 的写入仍由寄存器堆自身忽略。

## 4. FETCH：启动取指

RAM 地址选择当前 `PC`，宽度固定为 word。由于 RAM 为同步读，FETCH 阶段只启动
读取，不尝试把同一上升沿刚产生的 RAM 输出写入 IR。

```text
RAM_address       = PC
RAM_width         = WORD
RAM_output_enable = true
instr_pc_next     = PC
instr_pc_write    = true
PC_next           = PC + 4
PC_write          = true
next_state        = DECODE
```

在 FETCH 结束的上升沿，RAM 输出更新为 `RAM[PC]`，`instr_pc` 保存更新前的 PC，
同时 PC 变为 `PC + 4`。下一状态固定为 `DECODE`。

## 5. DECODE：译码并锁存指令

DECODE 整个周期内 RAM 输出保持为 FETCH 请求的指令。译码器输入选择
`RAM_output`，而不是旧的 `IR`：

```text
decoder_input = RAM_output
IR_next       = RAM_output
IR_write      = true
```

在 DECODE 结束的上升沿，`IR` 锁存该指令，同时状态寄存器根据译码结果更新。此后
RAM 输出即使因后续访存而变化，EXEC、MEM、CTRL 使用的字段仍来自 IR。

| opcode 类型 | 下一状态 |
| --- | --- |
| OP、OP-IMM、LUI、AUIPC、LOAD、STORE | `EXEC` |
| JAL、JALR、BRANCH | `CTRL` |
| MISC-MEM（FENCE/FENCE.I） | `FETCH`（无副作用实现） |
| SYSTEM 或其他/非法 opcode | `FETCH`（无异常单元时按非法指令处理） |

非法 opcode 按一条无副作用的 4-byte 指令跳过；如果以后加入异常单元，应将该项改
为异常入口状态。

## 6. EXEC：运算和地址计算

所有进入本状态的指令共用 ALU。ALU 的输出在拍末写入 `ALUOut`。

```text
ALUOut_next  = ALU_result
ALUOut_write = true
```

| 指令类型 | `ALU_A` | `ALU_B` | ALU 操作 | 下一状态 |
| --- | --- | --- | --- | --- |
| OP | `rs1_data` | `rs2_data` | 由 `funct3`、`funct7[5]` 决定 | `ALU_WB` |
| OP-IMM | `rs1_data` | I-immediate | 由 `funct3` 和移位编码决定 | `ALU_WB` |
| LUI | `0` | U-immediate | ADD | `ALU_WB` |
| AUIPC | `instr_pc` | U-immediate | ADD | `ALU_WB` |
| LOAD | `rs1_data` | I-immediate | ADD | `MEM` |
| STORE | `rs1_data` | S-immediate | ADD | `MEM` |

OP 的 SUB/SRA 由 `funct7[5]` 区分；OP-IMM 中只有右移立即数需要用 `IR[30]`
区分 SRLI/SRAI。其余立即数运算不能因为立即数的第 10 位为 1 而误选 SUB/SRA。

## 7. ALU_WB：ALU 结果写回

```text
Register_File_write_address = IR.rd
Register_File_write_data    = ALUOut
Register_File_write_enable  = true
next_state                  = FETCH
```

本状态只允许写寄存器，不写 PC 或 RAM。

## 8. MEM：数据内存访问

```text
RAM_address = ALUOut
RAM_width   = IR.funct3[1:0]
```

RAM 的 2 bit 宽度信号不能直接连接完整的 3 bit `funct3`。映射如下：

| `funct3[1:0]` | RAM 宽度 | LOAD | STORE |
| --- | --- | --- | --- |
| `00` | byte | LB/LBU | SB |
| `01` | half word | LH/LHU | SH |
| `10` | word | LW | SW |
| `11` | 非法 | 无 | 无 |

### LOAD

```text
RAM_output_enable = true
RAM_write_enable  = false
MDR_next          = RAM_output
MDR_write         = true
next_state        = LOAD_WB
```

### STORE

```text
RAM_output_enable = false
RAM_write_data    = rs2_data
RAM_write_enable  = valid_store_funct3
next_state        = FETCH
```

`valid_store_funct3` 只在 `000`、`001`、`010` 时为真。STORE 在本状态的时钟沿写
RAM，不经过写回状态。

## 9. LOAD_WB：加载扩展和写回

加载扩展由完整的 `funct3` 决定：

| `funct3` | 指令 | 写回值 |
| --- | --- | --- |
| `000` | LB | `sign_extend(MDR[7:0])` |
| `001` | LH | `sign_extend(MDR[15:0])` |
| `010` | LW | `MDR[31:0]` |
| `100` | LBU | `zero_extend(MDR[7:0])` |
| `101` | LHU | `zero_extend(MDR[15:0])` |
| 其他 | 非法 | 不写回 |

```text
Register_File_write_address = IR.rd
Register_File_write_data    = load_extended_data
Register_File_write_enable  = valid_load_funct3
next_state                  = FETCH
```

其中 `valid_load_funct3` 只在表中的五种合法编码时为真。

## 10. CTRL：跳转和分支

进入本状态时，PC 已在 `FETCH` 中变为 `instr_pc + 4`。

### JAL

```text
Register_File_write_address = IR.rd
Register_File_write_data    = instr_pc + 4
Register_File_write_enable  = true

PC_next  = instr_pc + J-immediate
PC_write = true
```

### JALR

```text
Register_File_write_address = IR.rd
Register_File_write_data    = instr_pc + 4
Register_File_write_enable  = true

PC_next  = (rs1_data + I-immediate) & 0xfffffffe
PC_write = true
```

JALR 的目标地址 bit 0 必须清零。

### BRANCH

```text
CMP_funct3 = IR.funct3
CMP_A      = rs1_data
CMP_B      = rs2_data

if branch_condition_true:
    PC_next  = instr_pc + B-immediate
    PC_write = true
else:
    PC_write = false
```

条件不成立时，保留 `FETCH` 已计算的 `instr_pc + 4`。六种合法条件为 BEQ、BNE、
BLT、BGE、BLTU、BGEU；其他 `funct3` 不写 PC。`CTRL` 完成后统一返回 `FETCH`。

## 11. 指令状态轨迹

| 指令类型 | 状态轨迹 | 拍数 |
| --- | --- | --- |
| OP、OP-IMM、LUI、AUIPC | `FETCH -> DECODE -> EXEC -> ALU_WB -> FETCH` | 4 |
| LOAD | `FETCH -> DECODE -> EXEC -> MEM -> LOAD_WB -> FETCH` | 5 |
| STORE | `FETCH -> DECODE -> EXEC -> MEM -> FETCH` | 4 |
| JAL、JALR、BRANCH | `FETCH -> DECODE -> CTRL -> FETCH` | 3 |

表中的拍数不重复计算下一条指令的 `FETCH`。

## 12. 验证清单

### ALU 和 U 型指令

| 初始条件 | 指令 | 预期结果 |
| --- | --- | --- |
| `x1=7, x2=3` | `ADD x3,x1,x2` | `x3=10`，轨迹 `FETCH/DECODE/EXEC/ALU_WB` |
| `x1=7, x2=3` | `SUB x3,x1,x2` | `x3=4`，确认 `funct7[5]` 生效 |
| `x1=7` | `ADDI x3,x1,-2` | `x3=5`，不得误选 SUB |
| `x1=0x80000000` | `SRAI x3,x1,4` | `x3=0xf8000000` |
| 任意 | `LUI x3,0x12345` | `x3=0x12345000` |
| `instr_pc=0x100` | `AUIPC x3,0x2` | `x3=0x2100`，使用 `instr_pc` 而非已加 4 的 PC |

### LOAD 和 STORE

令目标地址的四个字节为 `80 ff 34 12`：

| 指令 | 预期写回值 |
| --- | --- |
| LB（地址 + 0） | `0xffffff80` |
| LBU（地址 + 0） | `0x00000080` |
| LH（地址 + 0） | `0xffffff80`（小端序半字 `0xff80`） |
| LHU（地址 + 0） | `0x0000ff80` |
| LW（地址 + 0） | `0x1234ff80` |

分别执行 SB、SH、SW，确认只更新目标 1、2、4 个字节，STORE 不产生寄存器写使能。

### 控制流

- JAL：`instr_pc=0x100`、偏移 `0x20` 时，目标 PC 为 `0x120`，链接值为 `0x104`。
- JALR：`rs1=0x200`、立即数 `3` 时，目标 PC 为 `0x202`，bit 0 被清零。
- 对 BEQ、BNE、BLT、BGE、BLTU、BGEU 各测试 taken 和 not-taken：taken 使用
  `instr_pc + B-immediate`，not-taken 保留 `instr_pc + 4`。
- 特别用 `0xffffffff` 与 `1` 比较，确认 BLT 使用有符号比较、BLTU 使用无符号比较。

### 写使能互斥

- `FETCH` 只启动 RAM 读，并写 `instr_pc`、PC；不得写 IR。
- `DECODE` 只写 IR；译码输入必须是稳定的 RAM 输出。
- `EXEC` 只写 `ALUOut`。
- `ALU_WB` 和 `LOAD_WB` 只写寄存器堆。
- STORE 的 `MEM` 只写 RAM；LOAD 的 `MEM` 只写 `MDR`。
- `CTRL` 中 JAL/JALR 可在同一拍写寄存器堆和 PC；BRANCH 最多只写 PC。
- 每条合法或非法路径最终都回到 `FETCH`。
