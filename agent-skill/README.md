# CMate Conversion Skill

An AI skill that converts structured data files (Excel, CSV, JSON, YAML, Markdown tables) into [CMate](https://github.com/avada-kedavrua/cmate) `.cmate` rule files for configuration validation.

## What It Does

Instead of learning the CMate DSL syntax, you can:
1. Maintain your configuration requirements in a familiar format (Excel, CSV, etc.)
2. Let the AI convert them into executable `.cmate` validation rules
3. Run `cmate run` to validate your actual configurations

## Installation

### Claude Desktop / Claude Code

1. Download `Cmate-Skill.zip`
2. Extract it to get the `Cmate-Skill/` folder
3. Place the folder in your skills directory:
   - **Claude Desktop**: Add to your project's skills folder or reference in your MCP config
   - **Claude Code**: Place in `/mnt/skills/user/` or your project's `.claude/skills/` directory

### OpenClaw / Other MCP-compatible Agents

1. Download and extract `Cmate-Skill.zip`
2. Register the skill folder according to your agent's skill/plugin system
3. The skill auto-triggers when you mention converting files to cmate format

## Usage

### Basic Usage

Upload your spreadsheet or CSV file and ask:

```
Convert this Excel file to a cmate rule file
```

or

```
Generate cmate validation rules from this CSV
```

### What Your Input File Should Look Like

At minimum, your table needs two columns:

| Variable | Expected Value |
|---|---|
| OMP_NUM_THREADS | 10 |
| VLLM_USE_V1 | 1 |

The skill also recognizes optional columns for operators, conditions, severity levels, messages, and namespaces. Column names are detected flexibly — both English and Chinese headers are supported.

### Full-Featured Example

| Variable | Expected | Operator | Condition | Severity | Description |
|---|---|---|---|---|---|
| OMP_NUM_THREADS | 10 | == | | info | Thread count |
| SSL_ENABLED | true | == | env == production | error | SSL required |
| server.port | 1024 | >= | | error | Port minimum |
| log_level | debug,info,warn,error | in | | error | Valid levels |

### Supported Source Formats

| Format | Extensions | Notes |
|---|---|---|
| Excel | `.xlsx`, `.xls` | Multi-sheet supported (each sheet → different namespace) |
| CSV | `.csv` | Standard comma-separated |
| JSON | `.json` | Array of objects, each object = one rule |
| YAML | `.yaml`, `.yml` | Same structure as JSON |
| Markdown | `.md` | Pipe-delimited tables |

### Output

The skill generates a `.cmate` file with proper syntax including:
- `[metadata]` section with auto-generated name and version
- `[targets]` declarations for config file namespaces
- `[contexts]` declarations for scenario variables
- `[par <target>]` sections with `assert` statements
- Conditional `if/elif/else/fi` blocks from the condition column
- Proper severity levels and messages

Plus a ready-to-run command like:
```bash
cmate run output.cmate -c config:app.json -C deploy_mode:production
```

## Skill Structure

```
Cmate-Skill/
├── SKILL.md                          # Main skill instructions
├── references/
│   ├── cmate-syntax.md               # Complete CMate DSL reference
│   └── column-mapping.md             # Column detection algorithm
└── examples/
    ├── env-vars-excel.md             # Excel env var checklist → .cmate
    ├── json-config-csv.md            # CSV config requirements → .cmate
    └── multi-scenario.md             # Multi-scenario deployment matrix → .cmate
```

## Requirements

- **CMate**: `pip install cmate` (for running the generated rules)
- **Python**: >= 3.7
- No additional dependencies needed for the skill itself — it's a pure prompt-based skill

## License

This skill is part of the CMate project, licensed under [Mulan PSL v2](http://license.coscl.org.cn/MulanPSL2).
