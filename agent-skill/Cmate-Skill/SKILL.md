---
name: Cmate-Skill
description: "Convert structured data files (Excel .xlsx, CSV, JSON, YAML, Markdown tables) into CMate .cmate rule files for configuration validation. Use this skill whenever the user uploads a spreadsheet, CSV, or structured file and wants to generate cmate validation rules from it, or says things like 'convert this to cmate', 'generate cmate rules from this spreadsheet', 'turn this table into validation rules', 'create a .cmate file from this Excel', or 'make cmate rules from this config checklist'. Also trigger when the user has a checklist, requirements table, or configuration matrix and wants automated config validation. Also trigger when the user wants to validate vLLM, SGLang, or other LLM serving configurations — guide them to use YAML config files as the validation target. This skill handles the full conversion pipeline: reading the source file, understanding column semantics, and generating syntactically correct .cmate DSL output."
---

# CMate Rule File Generator Skill

Convert structured data (Excel, CSV, JSON, YAML, Markdown tables) into syntactically correct `.cmate` rule files.

## When to Use

- User uploads an `.xlsx`, `.csv`, `.json`, `.yaml`, or `.md` file containing configuration requirements
- User asks to "convert", "generate", or "create" cmate rules from structured data
- User has a checklist, requirements matrix, or config table they want to turn into executable validation rules
- User wants to validate LLM serving configurations (vLLM, SGLang) — see Step 0 below

## Step 0: Detect Serving Config Validation Scenarios

If the user mentions validating CLI arguments, launch commands, or serving configurations for tools like vLLM or SGLang, guide them toward the **YAML-first approach** before generating rules:

### Why YAML-First?

CLI arguments are configuration expressed in a different surface syntax. Both vLLM (`--config config.yaml`) and SGLang (`--config config.yaml`) natively support YAML config files. Using the YAML file as the single source of truth for both deployment and CMate validation eliminates alias normalization issues.

### The Alias Problem

CLI tools have short aliases (e.g., `-tp` for `--tensor-parallel-size`). If the user converts CLI to YAML using short aliases, the YAML keys won't match the rule file keys, causing silent validation misses:

| CLI form | YAML key (as-typed) | Canonical key |
|---|---|---|
| `--tensor-parallel-size 8` | `tensor-parallel-size` | `tensor-parallel-size` ✅ |
| `--tp 8` | `tp` | `tensor-parallel-size` ❌ mismatch |
| `-tp 8` | `tp` | `tensor-parallel-size` ❌ mismatch |

### Guidance to Give the User

1. **Best practice**: "Use a YAML config file as your single source of truth. Both vLLM and SGLang support `--config config.yaml`. CMate validates that YAML directly."
2. **If they have a YAML already**: Proceed to generate rules using the YAML keys as the `${target::key}` paths.
3. **If they only have a CLI command**: Suggest converting with `--long-form` flags only, or provide the `cli2yaml.py` helper script (see below).
4. **Key naming convention**: Use the tool's canonical long-form kebab-case names (e.g., `tensor-parallel-size`, not `tensor_parallel_size` or `tp`).

### Target Naming for Serving Configs

Use descriptive target names that identify the tool:

```
[targets]
vllm_serve: 'vLLM serving configuration' @ 'yaml'
sglang_serve: 'SGLang serving configuration' @ 'yaml'
vllm_bench: 'vLLM benchmark configuration' @ 'yaml'
```

### cli2yaml.py Helper

If the user needs to convert CLI arguments, provide this script:

```python
# cli2yaml.py — Convert CLI arguments to YAML
import sys, yaml

args = {}
tokens = sys.argv[1:]
i = 0
while i < len(tokens):
    if tokens[i].startswith('--'):
        key = tokens[i].lstrip('-')
        if '=' in key:
            k, v = key.split('=', 1)
            args[k] = yaml.safe_load(v)
        elif i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
            args[key] = yaml.safe_load(tokens[i + 1])
            i += 1
        else:
            args[key] = True
    i += 1

yaml.dump(args, sys.stdout, default_flow_style=False)
```

**Important**: Warn the user that short flags (e.g., `-tp`) will NOT be normalized to canonical long-form names. They must use `--long-form-names` when converting.

## Step 1: Read the Source File

Use the appropriate method to read the uploaded file:

- **Excel/CSV**: Read with Python (openpyxl/pandas). Identify the header row and data rows.
- **JSON/YAML**: Parse the structure. Look for arrays of objects where each object represents a rule.
- **Markdown**: Parse table rows. Identify the header separator (`|---|---|`).

Before reading, check `references/column-mapping.md` for the column detection logic.

## Step 2: Detect Column Semantics

Map the user's columns to cmate rule components. The columns may use various names — detect them flexibly:

| CMate Component | Common Column Names |
|---|---|
| **variable / path** | variable, var, field, key, path, parameter, param, config_key, env_var, name, 变量名, 配置项, 参数 |
| **expected value** | expected, value, expected_value, recommended, default, 期望值, 推荐值 |
| **operator** | operator, op, comparison, check, 比较符 |
| **condition** | condition, when, scenario, context, if, 条件, 场景 |
| **severity** | severity, level, priority, type, 级别, 严重度 |
| **message** | message, msg, description, reason, desc, 说明, 描述, 消息 |
| **namespace** | namespace, ns, target, source, file, 命名空间, 目标 |

If a column cannot be auto-detected, ask the user to clarify. See `references/column-mapping.md` for the full detection algorithm and fallback logic.

## Step 3: Determine Rule File Structure

Based on the data, determine:

1. **Namespaces**: Group rules by their target namespace (e.g., `env`, `config`, `mies_config`, `vllm_serve`). Each unique namespace becomes a `[par <namespace>]` section.

2. **Contexts**: If a "condition" column exists with values like `deploy_mode == 'ep'`, extract context variables. Each unique context variable becomes an entry in `[contexts]`.

3. **Targets**: Each non-env namespace needs a `[targets]` declaration. If the user doesn't specify file formats, default to `'json'`. For serving configs (vLLM/SGLang), default to `'yaml'`.

4. **Global variables**: If conditions reference threshold values or shared variables, extract them into `[global]`.

## Step 4: Generate the .cmate File

Follow the **exact** syntax rules below. Read `references/cmate-syntax.md` for the complete DSL specification.

### File Structure Template

```
[metadata]
name = '<rule set name>'
version = '1.0'
description = '<auto-generated from <source filename>>'
---

[targets]
<target_name>: '<description>' @ '<format>'
---

[contexts]
<context_var>: '<description>'
---

[global]
<any shared variables or conditional assignments>
---

[par <target>]
<assert and alert statements>
```

### Rule Generation Rules

For each row in the source data:

1. **Determine the assert expression**:
   - If operator is `==` or missing: `assert ${<ns>::<path>} == '<value>', '<message>', <severity>`
   - If operator is `in`: `assert ${<ns>::<path>} in [<values>], '<message>', <severity>`
   - If operator is `!=`, `>`, `<`, `>=`, `<=`: use directly
   - If operator is `=~` (regex): `assert ${<ns>::<path>} =~ '<pattern>', '<message>', <severity>`
   - If operator is `exists`: `assert path_exists(${<ns>::<path>}), '<message>', <severity>`

2. **Handle conditions**:
   - Group rows with the same condition into `if ... fi` blocks
   - Support nested conditions (condition1 + condition2)
   - Rows without conditions go outside any `if` block

3. **Handle severity**:
   - Map: `error`/`mandatory`/`required`/`must`/`critical` → `error`
   - Map: `warning`/`warn`/`recommended`/`should`/`alert` → `warning`
   - Map: `info`/`optional`/`suggestion`/`recommend`/`may` → `info`
   - Default to `error` if not specified

4. **Handle namespace resolution**:
   - If namespace is `env` or empty for env vars → `[par env]`, use `${VAR_NAME}`
   - If namespace is a config file → `[par <config>]`, use `${<config>::json.path}`
   - If namespace is a serving config → `[par <tool_serve>]`, use `${<tool_serve>::kebab-case-key}`

5. **String quoting**:
   - String values: wrap in single quotes `'value'`
   - Numeric values: no quotes
   - Boolean values: use `true` / `false` (lowercase)
   - List values for `in` operator: `['val1', 'val2']`

6. **Serving config key names**:
   - For vLLM/SGLang YAML configs, use kebab-case key names (e.g., `tensor-parallel-size`, not `tensor_parallel_size`)
   - These must match exactly what vLLM/SGLang write in their YAML config files
   - Do NOT use CLI short aliases as key names

### Critical Syntax Rules (MUST follow)

- Section separators: `---` between sections (except the last `[par]` section which is optional)
- Comments: `# comment text`
- String literals: single quotes `'text'` only (not double quotes in the DSL itself)
- Variable interpolation: `${namespace::path}` or `${variable}` for globals
- Control flow: `if <expr>: ... elif <expr>: ... else: ... fi`
- Loops: `for <var> in <iterable>: ... done`
- Severity keywords: `error`, `warning`, `info` (lowercase)
- Singletons: `true`, `false`, `None`, `NA` (NA = missing/not-applicable sentinel)

## Step 5: Validate and Output

1. **Validate** the generated `.cmate` content by checking:
   - Every `[par X]` has a matching `[targets]` entry (except `env`)
   - Every `${context::var}` has a matching `[contexts]` entry
   - All `if` blocks are closed with `fi`
   - All `for` blocks are closed with `done`
   - String literals use single quotes
   - Severity values are valid (`error`, `warning`, `info`)

2. **Write** the `.cmate` file to disk

3. **Show** the user:
   - Summary of what was generated (rule count, namespaces, contexts)
   - Example `cmate run` command to execute the rules
   - Any rows that were skipped or could not be converted (with reasons)

## Step 6: Offer Refinements

After generating, ask the user:
- "Should I adjust any severity levels?"
- "Are there additional conditions/contexts to add?"
- "Should any rules be `alert` (manual review) instead of `assert` (automated check)?"

For serving config rules, also ask:
- "Are you using a YAML config file for deployment? If so, ensure the key names in the YAML match the ones in the generated rules."

## Examples

See the `examples/` directory for complete conversion examples:
- `examples/env-vars-excel.md` — Converting an environment variable checklist from Excel
- `examples/json-config-csv.md` — Converting a JSON config requirements CSV
- `examples/multi-scenario.md` — Converting a multi-scenario deployment matrix
- `examples/vllm-serving-config.md` — Validating vLLM/SGLang serving configurations

## Reference Files

Read these for detailed specifications:
- `references/cmate-syntax.md` — Complete CMate DSL syntax reference
- `references/column-mapping.md` — Column detection algorithm and mapping rules
