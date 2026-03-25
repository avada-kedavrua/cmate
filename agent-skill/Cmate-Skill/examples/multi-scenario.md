# Example: Multi-Scenario Deployment Matrix (Excel → .cmate)

## Source File: `deployment_matrix.xlsx`

The user uploads an Excel file with two sheets.

### Sheet 1: "Environment Variables"

| 参数 | 推荐值 | 场景 | 级别 | 说明 |
|---|---|---|---|---|
| MINDIE_LOG_TO_FILE | 1 | | info | 建议将日志写入文件 |
| MINDIE_LOG_LEVEL | info | | info | 日志级别建议为 info |
| PYTORCH_NPU_ALLOC_CONF | expandable_segments:True | model_type == deepseek | warning | 需要开启虚拟内存 |
| HCCL_OP_EXPANSION_MODE | AIV | model_type == deepseek | error | 通信算法编排位置 |
| NPU_MEMORY_FRACTION | 0.92 | model_type == deepseek, npu_type == A2 | info | NPU 显存比 |
| NPU_MEMORY_FRACTION | 0.96 | model_type == deepseek, npu_type == A3 | info | NPU 显存比 |
| OMP_NUM_THREADS | 10 | npu_type == A2 | info | OpenMP 并行数 |
| OMP_NUM_THREADS | 16 | npu_type == A3 | info | OpenMP 并行数 |

### Sheet 2: "Config File"

| 配置项 | 期望值 | 比较符 | 场景 | 级别 | 说明 |
|---|---|---|---|---|---|
| ServerConfig.inferMode | standard | in:standard,Standard | | error | 推理模式 |
| BackendConfig.ModelDeployConfig.maxSeqLen | maxInputTokenLen | >= | | error | 不应小于 maxInputTokenLen |
| BackendConfig.ScheduleConfig.maxPrefillBatchSize | 1 | >= | | error | prefill 最大 batch size |
| BackendConfig.ModelDeployConfig.ModelConfig[0].modelWeightPath | | exists | | error | 模型权重路径需要存在 |
| ServerConfig.httpsEnabled | false | == | | info | 如需安全证书建议开启 |

## Column Detection (Sheet 1)

- `参数` → **variable** (Chinese: 参数)
- `推荐值` → **expected value** (Chinese: 推荐值)
- `场景` → **condition** (Chinese: 场景)
- `级别` → **severity** (Chinese: 级别)
- `说明` → **message** (Chinese: 说明)
- All UPPER_CASE variables → `env` namespace

## Column Detection (Sheet 2)

- `配置项` → **variable** (Chinese: 配置项)
- `期望值` → **expected value** (Chinese: 期望值)
- `比较符` → **operator** (Chinese: 比较符)
- `场景` → **condition**
- `级别` → **severity**
- `说明` → **message**
- Dotted paths → config namespace (user specifies: `mies_config`)

## Special Handling

1. **Comma-separated conditions**: `model_type == deepseek, npu_type == A2` → combined `and` condition
2. **Same variable, different conditions**: `NPU_MEMORY_FRACTION` appears twice with different conditions → becomes `if/elif` chain
3. **`in:` prefix in operator column**: `in:standard,Standard` → `in ['standard', 'Standard']`
4. **Cross-reference value**: `maxInputTokenLen` as expected value → `${mies_config::BackendConfig.ModelDeployConfig.maxInputTokenLen}`
5. **`exists` operator**: → `path_exists()` function call

## Generated File: `deployment_matrix.cmate`

```
[metadata]
name = '部署配置矩阵校验'
version = '1.0'
description = 'Auto-generated from deployment_matrix.xlsx'
---

[targets]
mies_config: 'MindIE Service 主配置文件' @ 'json'
---

[contexts]
model_type: '模型类型'
npu_type: 'NPU 硬件类型'
---

[par env]
# 通用环境变量
assert ${MINDIE_LOG_TO_FILE} in ['1', 'true'], '建议将日志写入文件', info
assert ${MINDIE_LOG_LEVEL} in ['info', 'INFO'], '日志级别建议为 info', info

# model_type == deepseek
if ${context::model_type} == 'deepseek':
    assert ${PYTORCH_NPU_ALLOC_CONF} == 'expandable_segments:True', '需要开启虚拟内存', warning
    assert ${HCCL_OP_EXPANSION_MODE} == 'AIV', '通信算法编排位置', error

    if ${context::npu_type} == 'A2':
        assert ${NPU_MEMORY_FRACTION} == '0.92', 'NPU 显存比', info
    elif ${context::npu_type} == 'A3':
        assert ${NPU_MEMORY_FRACTION} == '0.96', 'NPU 显存比', info
    fi
fi

# npu_type specific (outside deepseek condition)
if ${context::npu_type} == 'A2':
    assert ${OMP_NUM_THREADS} == '10', 'OpenMP 并行数', info
elif ${context::npu_type} == 'A3':
    assert ${OMP_NUM_THREADS} == '16', 'OpenMP 并行数', info
fi
---

[par mies_config]
assert ${ServerConfig.inferMode} in ['standard', 'Standard'], '推理模式', error
assert ${BackendConfig.ModelDeployConfig.maxSeqLen} >= ${BackendConfig.ModelDeployConfig.maxInputTokenLen}, '不应小于 maxInputTokenLen', error
assert ${BackendConfig.ScheduleConfig.maxPrefillBatchSize} >= 1, 'prefill 最大 batch size', error
assert path_exists(${BackendConfig.ModelDeployConfig.ModelConfig[0].modelWeightPath}), '模型权重路径需要存在', error
assert ${ServerConfig.httpsEnabled} == false, '如需安全证书建议开启', info
```

## Run Command

```bash
# Check with DeepSeek on A2 hardware
cmate run deployment_matrix.cmate -c mies_config:config.json -c env -C model_type:deepseek -C npu_type:A2

# Check with general model on A3 hardware
cmate run deployment_matrix.cmate -c mies_config:config.json -c env -C model_type:general -C npu_type:A3
```

## Key Conversion Decisions

1. **Nested conditions**: `model_type == deepseek, npu_type == A2` parsed as nested `if` inside the `deepseek` block (because A2/A3 only matters when model is deepseek for NPU_MEMORY_FRACTION)
2. **Conflicting same-variable rules**: `OMP_NUM_THREADS` has different values for A2 vs A3 → converted to `if/elif` chain
3. **Cross-reference expressions**: `maxInputTokenLen` recognized as a config path reference → `${mies_config::...}` instead of a literal string
4. **Multi-sheet handling**: Each sheet maps to a different namespace (`env` and `mies_config`)
5. **Chinese column names**: Fully supported through the column detection algorithm
6. **`in:` shorthand**: Parsed as `in` operator with comma-separated values
