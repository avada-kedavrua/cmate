# Example: Environment Variable Checklist (Excel → .cmate)

## Source File: `env_checklist.xlsx`

The user uploads an Excel file with this table:

| Variable | Expected Value | Scenario | Severity | Description |
|---|---|---|---|---|
| OMP_NUM_THREADS | 10 | | info | Recommended OpenMP thread count |
| OMP_PROC_BIND | false | | info | OpenMP thread binding config |
| PYTORCH_NPU_ALLOC_CONF | expandable_segments:True | | warning | Enable torch_npu virtual memory |
| VLLM_USE_V1 | 1 | | error | Must use V1 engine |
| HCCL_BUFFSIZE | 1024 | | info | HCCL communication buffer size |
| VLLM_WORKER_MULTIPROC_METHOD | fork | deploy_mode == ep | error | Required for PD disaggregation |
| VLLM_ASCEND_EXTERNAL_DP_LB_ENABLED | 1 | deploy_mode == ep | info | Distributed DP switch |

## Column Detection

The skill detects:
- `Variable` → **variable** (env var name)
- `Expected Value` → **expected value**
- `Scenario` → **condition** (maps to context variable)
- `Severity` → **severity**
- `Description` → **message**
- No namespace column → auto-detect: all UPPER_CASE → `env` namespace

## Generated File: `env_checklist.cmate`

```
[metadata]
name = 'Environment Variable Checklist'
version = '1.0'
description = 'Auto-generated from env_checklist.xlsx'
---

[contexts]
deploy_mode: 'Deployment mode'
---

[par env]
# General environment variables
assert ${OMP_NUM_THREADS} == '10', 'Recommended OpenMP thread count', info
assert ${OMP_PROC_BIND} == 'false', 'OpenMP thread binding config', info
assert ${PYTORCH_NPU_ALLOC_CONF} == 'expandable_segments:True', 'Enable torch_npu virtual memory', warning
assert ${VLLM_USE_V1} == '1', 'Must use V1 engine', error
assert ${HCCL_BUFFSIZE} == '1024', 'HCCL communication buffer size', info

# deploy_mode == ep
if ${context::deploy_mode} == 'ep':
    assert ${VLLM_WORKER_MULTIPROC_METHOD} == 'fork', 'Required for PD disaggregation', error
    assert ${VLLM_ASCEND_EXTERNAL_DP_LB_ENABLED} == '1', 'Distributed DP switch', info
fi
```

## Run Command

```bash
cmate run env_checklist.cmate -c env -C deploy_mode:ep
```

## Key Conversion Decisions

1. **All values quoted as strings**: Environment variables are always strings in shell, so `10` becomes `'10'`
2. **Condition parsing**: `deploy_mode == ep` → extracted `deploy_mode` as context variable, `ep` as the comparison value
3. **Grouping**: Rules with same condition grouped into one `if` block
4. **Ordering**: Unconditional rules first, then conditional blocks
5. **No `[targets]` needed**: `env` is a built-in target
