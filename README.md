# CMate

<p align="center">
  <b>Your Config Validation Companion</b>
</p>

<p align="center">
  <a href="#introduction">Introduction</a> &bull;
  <a href="#installation">Installation</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="docs/en/quick_start.md">Guide</a> &bull;
  <a href="README_CN.md">中文</a> &bull;
  <a href="#license">License</a>
</p>

---

## Introduction

**CMate** (**C**onfig **Mate**) is a declarative validation engine for configuration files. The name draws inspiration from the chess term *Check Mate* — it's your configuration "check mate", catching config issues before they reach production.

### Why CMate?

Basic correctness checking is table stakes. The real challenge is: **the same configuration fields may have entirely different optimal values depending on the deployment scenario.**

Take LLM inference services as an example: a PD co-located deployment and a PD disaggregated deployment may require very different recommended values for the same parameter; DeepSeek models and general-purpose models need different validation rule sets. The combinatorial logic of "which fields should have what values under which conditions" typically lives only in expert knowledge — hard to capture and share.

CMate solves this by using **context variables** to manage scenario switching, and **severity levels** to distinguish between recommended and mandatory settings. Expert knowledge gets encoded into distributable, executable `.cmate` rule files.

### Key Features

- **Intuitive DSL**: Syntax inspired by Python, Shell, and JsonPath — writing a validation rule feels like writing a unit test
- **Context-driven**: Pass context variables via `-C` to adapt the same rule file to different deployment scenarios
- **Three severity levels**: `error` (mandatory) / `warning` (alert) / `info` (recommendation), filterable at runtime
- **Multiple data sources**: Validate JSON, YAML config files and environment variables
- **Env script generation**: Automatically generates `set_env.sh` from `[par env]` rules — `source` it to apply or revert environment variables
- **pytest-style output**: Collection, execution, and reporting follow pytest conventions
- **Control flow**: `if/elif/else/fi` conditionals, `for/done` loops, and `break`/`continue`
- **Extensible functions**: Built-in `len()`, `int()`, `str()`, etc., with custom extensions via `custom_fn.py`

## Installation

### Requirements

- Python >= 3.7

### Install via pip

```bash
pip install cmate
```

### Install from source

```bash
git clone https://github.com/avada-kedavrua/cmate.git # or https://gitcode.com/AvadaKedavrua/cmate.git
cd cmate
pip install -e .
```

## Quick Start

> For a full walkthrough, see the [Quick Start Guide](docs/en/quick_start.md).

Create `demo.cmate`:

```
[metadata]
name = 'Server Port Validation'
version = '1.0'
---

[targets]
config: 'Application config file' @ 'json'
---

[contexts]
env: 'Deployment environment, options: dev / staging / production'
---

[global]
min_port = 1024
if ${context::env} == 'production':
    min_port = 8000
fi
---

[par config]
assert ${config::port} > ${min_port}, 'Port number is too low', error
assert ${config::host} != '', 'Hostname must not be empty', error
assert ${config::timeout} >= 1000, 'Recommended timeout >= 1000ms', info
```

Create `app.json`:

```json
{
  "port": 8080,
  "host": "localhost",
  "timeout": 5000
}
```

Run:

```bash
cmate run demo.cmate -c config:app.json -C env:production
```

## Environment Variable Script Generation

When a rule file contains a `[par env]` section, `cmate run` automatically generates a `set_env.sh` script in the current directory. The script sets (or unsets) environment variables to match the expected values declared in your rules:

```bash
# Apply the recommended environment variables
source set_env.sh

# Revert to the values before cmate was run
source set_env.sh 0
```

To invoke the script:

```bash
cmate run rules.cmate -c env
```

## Rule File Syntax

A `.cmate` file consists of sections separated by `---`:

### `[metadata]` — Metadata

```
[metadata]
name = 'Rule set name'
version = '1.0'
authors = [{"name": "Author"}]
description = 'Rule set description'
---
```

### `[targets]` — Validation targets

Declare which configuration files are needed as input. Format: `name: 'description' @ 'format'`:

```
[targets]
config: 'Main config file' @ 'json'
env_config: 'Environment config' @ 'yaml'
---
```

Supply actual file paths at runtime via `-c`: `cmate run rules.cmate -c config:app.json`

The special target `env` is built-in for environment variable validation and **cannot** be declared in `[targets]`. Use it directly as a `[par env]` section and pass `-c env` at runtime.

### `[contexts]` — Context variables

Declare which context variables the rule file accepts for scenario-based branching:

```
[contexts]
deploy_mode: 'Deployment mode, options: pd_mix / pd_disaggregation / ep'
model_type: 'Model type, e.g. deepseek / general'
---
```

Supply values at runtime via `-C`: `cmate run rules.cmate -c config:app.json -C deploy_mode:ep`

Reference in rules with `${context::variable_name}`.

### `[global]` — Global variables

Define global variables and conditional assignment logic, available in subsequent `[par]` sections:

```
[global]
max_connections = 100

if ${context::env} == 'production':
    max_connections = 500
fi
---
```

### `[par <target>]` — Partition rules

`par` is short for *partition*. Each partition corresponds to a target and contains `assert` or `alert` statements:

```
[par config]
# Basic assertion: assert <expression>, 'message'[, <severity>]
# severity defaults to 'error' if omitted
assert ${config::enabled} == true, 'Service must be enabled'
assert ${config::port} > 1024, 'Port should be above 1024', info

# Conditional assertion
if ${context::deploy_mode} == 'production':
    assert ${config::ssl} == true, 'SSL is required in production', error
fi

# Loop assertion
for host in ${config::allowed_hosts}:
    assert ${host} != '', 'Hostname must not be empty', error
done

# Tuple unpacking in loops
for key, value in ${config::env_pairs}:
    assert ${value} != '', 'Value must not be empty', error
done

# alert statement: flag a field for manual review, no condition evaluated
# accepts only ${namespace::path} expressions; severity defaults to 'warning'
alert ${config::model_path}, 'Please verify the model path', warning
```

### Severity Levels

| Level | Meaning | Output Label |
|-------|---------|-------------|
| `error` | Mandatory — failure if not met | `[NOK]` |
| `warning` | Alert — recommended fix | `[WARNING]` |
| `info` | Recommendation — for reference | `[RECOMMEND]` |

Use `-s` to filter minimum severity: `cmate run rules.cmate -c config:app.json -s warning` runs only `warning` and `error` rules.

### Data Access & Expressions

```
# Access config values (namespace::jsonpath style)
${config::server.port}
${config::items[0].name}
${context::deploy_mode}

# Comparison: ==, !=, <, >, <=, >=, =~ (regex match), in, not in
# Logical: and, or, not
# Arithmetic: +, -, *, /, //, %, **
# Singletons: true, false, None, NA  (NA is the sentinel for missing values)
# Built-in functions: len(), int(), str(), range(), path_exists(), is_port_in_use(), etc.
```

## CLI Reference

```bash
# Run validation
cmate run <rule_file> [options]
  -c, --configs       Config files: '<name>:<path>[@<format>]' or 'env'
  -C, --contexts      Context variables: '<name>:<value>'
  -s, --severity      Minimum severity filter: info | warning | error (default: info)
  -x, --fail-fast     Stop on first failure
  -v, --verbose       Verbose output
  -k, --lines         Filter rules by line number: '10,20,30'
  -co, --collect-only List rules without executing
  --output-path       Directory for JSON result output

# Inspect rule file
cmate inspect <rule_file> [options]
  -f, --format    Output format: text | json (default: text)
```

## Project Structure

```
cmate/
├── cmate/
│   ├── cmate.py        # CLI entry point and core orchestration
│   ├── lexer.py        # Lexer (tokenizer)
│   ├── parser.py       # Parser (grammar)
│   ├── _ast.py         # AST node definitions
│   ├── visitor.py      # AST traversal and evaluation
│   ├── _test.py        # Test runner (pytest-style output)
│   ├── data_source.py  # Data source (namespace::path key-value store)
│   ├── custom_fn.py    # Extensible custom functions
│   └── util.py         # Utilities
├── presets/            # Preset rule file examples
├── tests/             # Unit tests
└── pyproject.toml     # Project configuration
```

## Contributing

Issues and Pull Requests are welcome.

```bash
# Development setup
git clone https://github.com/avada-kedavrua/cmate.git # or https://gitcode.com/AvadaKedavrua/cmate.git
cd cmate
pip install -e .

# Run tests
pytest tests/

# Lint
lintrunner -a
```

## License

CMate is licensed under [Mulan PSL v2](http://license.coscl.org.cn/MulanPSL2).

```
Copyright (c) 2025-2026 Huawei Technologies Co.,Ltd.

Licensed under the Mulan PSL v2.
You may obtain a copy of the License at:

    http://license.coscl.org.cn/MulanPSL2

THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
See the Mulan PSL v2 for more details.
```
