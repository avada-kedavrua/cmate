# Example: LLM Serving Config Validation (YAML → .cmate)

## Background

CLI arguments for tools like vLLM and SGLang are just configuration expressed in a different syntax. Both tools natively support YAML config files via `--config`, making YAML the ideal single source of truth for both deployment and CMate validation.

This example shows how to generate `.cmate` rules for validating a vLLM serving configuration, combining environment variables and YAML config file checks.

## Source File: `vllm_serving_checklist.xlsx`

The user uploads an Excel file with two sheets.

### Sheet 1: "Environment Variables"

| Variable | Expected Value | Scenario | Severity | Description |
|---|---|---|---|---|
| VLLM_USE_V1 | 1 | | error | Must use V1 engine |
| OMP_NUM_THREADS | 10 | | info | Recommended thread count |
| PYTORCH_NPU_ALLOC_CONF | expandable_segments:True | model_type == deepseek | warning | Enable virtual memory for DeepSeek |
| HCCL_OP_EXPANSION_MODE | AIV | model_type == deepseek | error | Communication algorithm placement |

### Sheet 2: "Serving Config"

| Parameter | Expected | Operator | Scenario | Severity | Description |
|---|---|---|---|---|---|
| tensor-parallel-size | 1 | >= | | error | TP size must be positive |
| gpu-memory-utilization | 0.98 | <= | | warning | GPU memory utilization too high |
| gpu-memory-utilization | 0 | > | | error | Must be positive |
| max-model-len | 8192 | >= | model_type == deepseek | warning | DeepSeek needs longer context |
| trust-remote-code | true | == | model_type == deepseek | error | DeepSeek requires trust-remote-code |
| dtype | auto | == | | info | Recommended dtype setting |
| gpu-memory-utilization | 0.95 | <= | gpu_type == A100 | info | Recommended for A100 |

## Column Detection (Sheet 1)

- `Variable` → **variable** (UPPER_CASE → `env` namespace)
- `Expected Value` → **expected value**
- `Scenario` → **condition**
- `Severity` → **severity**
- `Description` → **message**

## Column Detection (Sheet 2)

- `Parameter` → **variable** (kebab-case → serving config namespace)
- `Expected` → **expected value**
- `Operator` → **operator**
- `Scenario` → **condition**
- `Severity` → **severity**
- `Description` → **message**
- kebab-case keys → serving config namespace (user specifies: `vllm_serve`)

## Key Design Decisions

### Why YAML Target Instead of CLI Parsing?

The skill asks the user:
> "These look like vLLM serving parameters. Both vLLM and SGLang support YAML config files via `--config`. I recommend using the YAML config as the validation target. What should I name this target? (e.g., `vllm_serve`)"

User responds: `vllm_serve`

### Key Name Convention

The rule file uses the **exact same key names** that vLLM uses in its YAML config:
- `tensor-parallel-size` ✅ (kebab-case, matches YAML)
- `tensor_parallel_size` ❌ (snake_case, doesn't match)
- `tp` ❌ (CLI short alias, doesn't match)

This is critical: if the YAML config says `tensor-parallel-size: 8` but the rule says `${vllm_serve::tp}`, the validation silently misses.

### Numeric vs String Values

Serving config values from YAML are typed (unlike env vars which are always strings):
- `tensor-parallel-size: 8` → numeric, no quotes in rule: `>= 1`
- `trust-remote-code: true` → boolean, no quotes: `== true`
- `dtype: auto` → string, quoted: `== 'auto'`

## Generated File: `vllm_serving_check.cmate`

```
[metadata]
name = 'vLLM Serving Configuration Check'
version = '1.0'
description = 'Auto-generated from vllm_serving_checklist.xlsx'
---

[targets]
vllm_serve: 'vLLM serving configuration' @ 'yaml'
---

[contexts]
model_type: 'Model type'
gpu_type: 'GPU type'
---

[par env]
# General environment variables
assert ${VLLM_USE_V1} == '1', 'Must use V1 engine', error
assert ${OMP_NUM_THREADS} == '10', 'Recommended thread count', info

# model_type == deepseek
if ${context::model_type} == 'deepseek':
    assert ${PYTORCH_NPU_ALLOC_CONF} == 'expandable_segments:True', 'Enable virtual memory for DeepSeek', warning
    assert ${HCCL_OP_EXPANSION_MODE} == 'AIV', 'Communication algorithm placement', error
fi
---

[par vllm_serve]
# Basic validation
assert ${vllm_serve::tensor-parallel-size} >= 1, 'TP size must be positive', error
assert ${vllm_serve::gpu-memory-utilization} > 0, 'Must be positive', error
assert ${vllm_serve::gpu-memory-utilization} <= 0.98, 'GPU memory utilization too high', warning
assert ${vllm_serve::dtype} == 'auto', 'Recommended dtype setting', info

# model_type == deepseek
if ${context::model_type} == 'deepseek':
    assert ${vllm_serve::max-model-len} >= 8192, 'DeepSeek needs longer context', warning
    assert ${vllm_serve::trust-remote-code} == true, 'DeepSeek requires trust-remote-code', error
fi

# gpu_type == A100
if ${context::gpu_type} == 'A100':
    assert ${vllm_serve::gpu-memory-utilization} <= 0.95, 'Recommended for A100', info
fi
```

## YAML Config File (Validation Target)

The user should maintain this YAML file as the single source of truth:

```yaml
# vllm_serve.yaml — used for both deployment and validation
model: deepseek-v3
tensor-parallel-size: 8
gpu-memory-utilization: 0.95
max-model-len: 32768
dtype: auto
trust-remote-code: true
```

## Run Commands

```bash
# Deploy with the same YAML
vllm serve --config vllm_serve.yaml

# Validate with CMate
cmate run vllm_serving_check.cmate \
    -c vllm_serve:vllm_serve.yaml \
       env \
    -C model_type:deepseek gpu_type:A100
```

## SGLang Variant

The same approach works for SGLang. The only differences:
- Target name: `sglang_serve` instead of `vllm_serve`
- Key names follow SGLang conventions (e.g., `model-path` instead of `model`, `mem-fraction-static` instead of `gpu-memory-utilization`)

```
[targets]
sglang_serve: 'SGLang serving configuration' @ 'yaml'
---

[par sglang_serve]
assert ${sglang_serve::tensor-parallel-size} >= 1, 'TP size must be positive', error
assert ${sglang_serve::mem-fraction-static} <= 0.95, 'Memory fraction too high', warning
```

```bash
python -m sglang.launch_server --config sglang_serve.yaml
cmate run sglang_check.cmate -c sglang_serve:sglang_serve.yaml env
```

## Key Conversion Decisions

1. **YAML-first approach**: Serving config validated as YAML file, not parsed from CLI
2. **Kebab-case keys**: Match vLLM/SGLang YAML format exactly (`tensor-parallel-size`, not `tp`)
3. **Typed values**: YAML values are typed (numbers, booleans), unlike env vars which are always strings
4. **Separate partitions**: Environment variables in `[par env]`, serving config in `[par vllm_serve]`
5. **Alias warning**: If user mentions `-tp` or other short flags, warn about key name mismatch
6. **Combined validation**: A single `.cmate` file can validate both env vars AND the serving YAML config together
