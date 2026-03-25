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
  env : ['production']
    Deployment environment, options: dev / staging / production

Config Targets
--------------
  cfg
  ----
    type : .json
    description : Web service config file

Usage: -c <rule_name>:<file_path>  -C <context>:<value>
```

> [!Note]
> The options list under `Context Variables` shows values that appear in actual
> `if/elif` conditions in the rule file (e.g. `${context::env} == 'production'`). Values
> only mentioned in descriptions are not included.

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

`env` is a built-in target that reads your current shell environment variables. It does **not** need to be declared in `[targets]`. Write a `[par env]` section and pass `-c env` at runtime:

```
[par env]
assert ${OMP_NUM_THREADS} == '10', 'Recommended OMP thread count is 10', info
assert ${CUDA_VISIBLE_DEVICES} != '', 'GPU device must be set', error
```

Run:

```bash
cmate run env_check.cmate -c env
```

Inside `[par env]`, unqualified variable names like `${OMP_NUM_THREADS}` resolve to the `env` namespace automatically, equivalent to `${env::OMP_NUM_THREADS}`.

## Validating LLM Serving Configurations (vLLM / SGLang)

CLI arguments are configuration — just expressed in a different syntax. Both vLLM and SGLang natively support YAML config files via `--config`, so CMate can validate your serving configurations directly without any CLI parsing.

### Why YAML-First?

The key insight is: **use a YAML config file as the single source of truth for both launching the service and validating with CMate.** This eliminates a whole class of problems around argument alias normalization (e.g., `--tp` vs `--tensor-parallel-size` vs `tensor_parallel_size`).

### Step 1: Create a YAML config file

```yaml
# vllm_serve.yaml — used for both deployment and validation
model: deepseek-v3
tensor-parallel-size: 8
gpu-memory-utilization: 0.95
max-model-len: 32768
dtype: auto
trust-remote-code: true
```

### Step 2: Write validation rules

Create `vllm_check.cmate`:

```
[metadata]
name = 'vLLM Serving Config Check'
version = '1.0'
---

[targets]
vllm_serve: 'vLLM serving configuration' @ 'yaml'
---

[contexts]
model_type: 'Model type, e.g. deepseek / general'
gpu_type: 'GPU type, e.g. A100 / A800 / 910B'
---

[par env]
assert ${VLLM_USE_V1} == '1', 'Must use V1 engine', error

if ${context::model_type} == 'deepseek':
    assert ${PYTORCH_NPU_ALLOC_CONF} == 'expandable_segments:True', 'Enable virtual memory for DeepSeek', warning
fi

[par vllm_serve]
# Basic validation
assert ${vllm_serve::tensor-parallel-size} >= 1, 'TP size must be positive', error
assert ${vllm_serve::gpu-memory-utilization} > 0, 'GPU memory utilization must be positive', error
assert ${vllm_serve::gpu-memory-utilization} <= 0.98, 'GPU memory utilization too high, risk of OOM', warning

# Model-specific rules
if ${context::model_type} == 'deepseek':
    assert ${vllm_serve::max-model-len} >= 8192, 'DeepSeek needs longer context window', warning
    assert ${vllm_serve::trust-remote-code} == true, 'DeepSeek requires trust-remote-code', error
fi

# GPU-specific rules
if ${context::gpu_type} == 'A100':
    assert ${vllm_serve::gpu-memory-utilization} <= 0.95, 'Recommended GPU utilization for A100', info
fi
```

### Step 3: Deploy and validate

```bash
# Deploy with the same YAML
vllm serve --config vllm_serve.yaml

# Validate
cmate run vllm_check.cmate -c vllm_serve:vllm_serve.yaml -c env -C model_type:deepseek gpu_type:A100
```

### SGLang works the same way

```yaml
# sglang_serve.yaml
model-path: deepseek-v3
host: 0.0.0.0
port: 30000
tensor-parallel-size: 8
mem-fraction-static: 0.9
```

```bash
python -m sglang.launch_server --config sglang_serve.yaml
cmate run sglang_check.cmate -c sglang_serve:sglang_serve.yaml
```

### Key Name Matching

Both vLLM and SGLang use **long-form kebab-case** names (e.g., `tensor-parallel-size`) in their YAML config files. Your `.cmate` rules must use the exact same key names. This is why YAML-first is the recommended approach — the names are guaranteed to match.

If you convert CLI arguments to YAML manually, be aware that short aliases like `-tp` will not automatically expand to `tensor-parallel-size`, causing silent validation misses.

### Converting CLI Arguments to YAML (Fallback)

For commands that don't support `--config` (e.g., `vllm bench serve`), use a simple converter:

```python
# cli2yaml.py
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

```bash
python cli2yaml.py --model deepseek-v3 --tensor-parallel-size 8 > cli_args.yaml
cmate run rules.cmate -c vllm_serve:cli_args.yaml
```

> **Note**: Always use `--long-form-names` when converting. Short flags like `-tp` are not normalized automatically.

## Looping Over List Fields

```
[par cfg]
for host in ${cfg::server.allowed_hosts}:
    assert ${host} != '', 'Hostname must not be empty', error
    assert len(${host}) < 256, 'Hostname too long', warning
done
```

For lists of key-value pairs, tuple unpacking is also supported:

```
[par cfg]
for key, value in ${cfg::env_pairs}:
    assert ${value} != '', 'Value must not be empty', error
done
```

## The `alert` Statement

`alert` differs from `assert` — it doesn't evaluate a condition. It flags a field for manual review. The field must be a `${namespace::path}` reference; arbitrary expressions are not accepted. Severity defaults to `warning` if omitted.

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
| Membership | `in`, `not in` | `${val} in ['a', 'b']` |
| Logical | `and`, `or`, `not` | Boolean combinators |
| Arithmetic | `+`, `-`, `*`, `/`, `//`, `%`, `**` | Standard arithmetic |
| Conditional | `if ... elif ... else ... fi` | Shell-style branching |
| Loop | `for x in <iterable>: ... done` | Shell-style loop; supports `for x, y in ...` tuple unpacking |
| Loop control | `break`, `continue` | Exit or skip loop iteration |
| Assertion | `assert <expr>, 'msg'[, severity]` | severity: error/warning/info; defaults to `error` |
| Alert | `alert ${ns::path}, 'msg'[, severity]` | Flag field, no condition check; defaults to `warning` |
| Function call | `len()`, `int()`, `str()`, `range()` | Built-in + custom functions |
| Singletons | `true`, `false`, `None`, `NA` | `NA` is the sentinel for missing/inapplicable values |

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
