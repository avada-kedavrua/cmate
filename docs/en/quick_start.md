# CMate Quick Start

This guide walks you through writing and running a complete `.cmate` rule file from scratch.

## Prerequisites

```bash
# Install cmate
pip install cmate

# Verify installation
cmate --help
```

## Your First Rule File

### Scenario

You have a web service config file `server.json` and need to validate port, timeout, and other parameters with different requirements per deployment environment.

### Step 1: Prepare a config file

Create `server.json`:

```json
{
  "server": {
    "port": 8080,
    "host": "0.0.0.0",
    "timeout": 3000,
    "max_connections": 200,
    "ssl": false
  },
  "logging": {
    "level": "info",
    "file": "/var/log/app.log"
  }
}
```

### Step 2: Write a rule file

Create `server_check.cmate`:

```
[metadata]
name = 'Web Service Config Check'
version = '1.0'
description = 'Validate service port, timeout, and security settings'
---

[targets]
cfg: 'Web service config file' @ 'json'
---

[contexts]
env: 'Deployment environment, options: dev / staging / production'
---

[global]
min_port = 1024
max_timeout = 30000

if ${context::env} == 'production':
    min_port = 8000
    max_timeout = 10000
fi
---

[par cfg]
# --- Port validation ---
assert ${cfg::server.port} > ${min_port}, 'Port must be above the minimum', error
assert ${cfg::server.port} < 65536, 'Port must be below 65536', error

# --- Timeout validation ---
assert ${cfg::server.timeout} >= 1000, 'Timeout should be at least 1000ms', warning
assert ${cfg::server.timeout} <= ${max_timeout}, 'Timeout exceeds maximum', info

# --- Connection limit ---
assert ${cfg::server.max_connections} >= 10, 'Max connections too low', error
assert ${cfg::server.max_connections} <= 10000, 'Max connections too high', warning

# --- Security (production only) ---
if ${context::env} == 'production':
    assert ${cfg::server.ssl} == true, 'SSL must be enabled in production', error
    assert ${cfg::server.host} != '0.0.0.0', 'Avoid binding to all interfaces in production', warning
fi

# --- Logging ---
assert ${cfg::logging.level} in ['debug', 'info', 'warning', 'error'], 'Invalid log level', error
```

### Step 3: Run

```bash
# Dev environment
cmate run server_check.cmate -c cfg:server.json -C env:dev

# Production environment
cmate run server_check.cmate -c cfg:server.json -C env:production
```

In `dev` mode, all checks pass. In `production` mode, SSL and host binding will trigger failures.

## Going Further

### Inspect rule dependencies

See what configs and context variables a rule file needs without running it:

```bash
cmate inspect server_check.cmate
```

Example output:

```
Overview
--------
  name : Web Service Config Check
  version : 1.0

Context Variables
-----------------
  env : ['dev', 'staging', 'production']
    Deployment environment

Config Targets
--------------
  cfg
  ----
    type : .json
    description : Web service config file

Usage: -c <rule_name>:<file_path>  -C <context>:<value>
```

### Collect rules only

List all rules without executing — useful for debugging:

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production --collect-only
```

Output:

```
collected 9 items
<Target cfg>
  <test_20 ${cfg::server.port} > ${min_port}>
  <test_21 ${cfg::server.port} < 65536>
  ...
```

### Filter by severity

Run only `warning` and above:

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -s warning
```

### Filter by line number

Run only rules on lines 20 and 24:

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -k 20,24
```

### Fail fast

Stop on the first failure:

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -x
```

### Verbose output

Show each rule on its own line with status:

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -v
```

### Export JSON results

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production --output-path ./results
```

Results are saved to `./results/cmate_<timestamp>_output.json`.

## Validating Environment Variables

cmate can validate current shell environment variables directly:

```
[targets]
env_config: 'Environment variable config' @ 'json'
---

[par env]
assert ${OMP_NUM_THREADS} == '10', 'OMP thread count should be 10', info
```

Pass `env` as a target at runtime (no file path needed):

```bash
cmate run env_check.cmate -c env
```

## Looping Over List Fields

```
[par cfg]
for host in ${cfg::server.allowed_hosts}:
    assert ${host} != '', 'Hostname must not be empty', error
    assert len(${host}) < 256, 'Hostname too long', warning
done
```

## The `alert` Statement

`alert` differs from `assert` — it doesn't evaluate a condition. It flags a field for manual review:

```
[par cfg]
alert ${cfg::server.model_path}, 'Please verify the model path is correct', warning
```

Alerts don't affect the pass/fail count and are shown in a separate `ALERTS` section in the output.

## DSL Syntax Reference

| Syntax | Example | Description |
|--------|---------|-------------|
| Data access | `${config::key.path}` | namespace::jsonpath style |
| Comparison | `==`, `!=`, `<`, `>`, `<=`, `>=` | Standard comparison |
| Regex match | `=~` | `${val} =~ '^[a-z]+$'` |
| Membership | `in` | `${val} in ['a', 'b']` |
| Logical | `and`, `or`, `not` | Boolean combinators |
| Arithmetic | `+`, `-`, `*`, `/`, `//`, `%`, `**` | Standard arithmetic |
| Conditional | `if ... elif ... else ... fi` | Shell-style branching |
| Loop | `for x in <iterable>: ... done` | Shell-style loop |
| Assertion | `assert <expr>, 'msg', severity` | severity: error/warning/info |
| Alert | `alert <expr>, 'msg', severity` | Flag field, no condition check |
| Function call | `len()`, `int()`, `str()`, `range()` | Built-in + custom functions |

## Real-World Example: LLM Inference Config

Validating vLLM-Ascend environment variables (see `presets/vllm.cmate`):

```
[metadata]
name = 'VLLM-Ascend Config Check'
version = '1.0'
---

[par env]
assert ${OMP_PROC_BIND} == 'false', 'OpenMP thread binding affects performance', info
assert ${OMP_NUM_THREADS} == '10', 'Recommended OMP thread count is 10', info
assert ${VLLM_USE_V1} == '1', 'VLLM V1 engine switch, defaults to V0 if unset', error

if ${context::deploy_mode} == 'ep':
    assert ${VLLM_WORKER_MULTIPROC_METHOD} == 'fork', 'Required for PD disaggregation', error
fi
```

Run:

```bash
cmate run presets/vllm.cmate -c env -C deploy_mode:ep
```

This example illustrates CMate's core value: encoding expert knowledge about "which variables should have what values in which scenarios" into distributable rule files.

## Next Steps

- Browse the `presets/` directory for more real-world rule file examples
- Define your own validation functions in `cmate/custom_fn.py`
- Use `cmate inspect` to understand any rule file's dependency structure
