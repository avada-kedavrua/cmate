# CMate 快速入门

本指南将带你从零开始编写并运行一个完整的 `.cmate` 规则文件。

## 前置准备

```bash
# 安装 cmate
pip install cmate

# 验证安装
cmate --help
```

## 第一个规则文件

### 场景

假设你有一个 Web 服务配置文件 `server.json`，需要校验端口、超时等参数，且不同部署环境有不同的要求。

### Step 1: 准备配置文件

创建 `server.json`：

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

### Step 2: 编写规则文件

创建 `server_check.cmate`：

```
[metadata]
name = 'Web 服务配置检查'
version = '1.0'
description = '校验服务端口、超时及安全配置'
---

[targets]
cfg: 'Web 服务配置文件' @ 'json'
---

[contexts]
env: '部署环境，可选值: dev / staging / production'
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
# --- 端口校验 ---
assert ${cfg::server.port} > ${min_port}, '端口号不应低于最低要求', error
assert ${cfg::server.port} < 65536, '端口号必须小于 65536', error

# --- 超时校验 ---
assert ${cfg::server.timeout} >= 1000, '超时时间至少 1000ms', warning
assert ${cfg::server.timeout} <= ${max_timeout}, '超时时间超过上限', info

# --- 连接数校验 ---
assert ${cfg::server.max_connections} >= 10, '最大连接数不应小于 10', error
assert ${cfg::server.max_connections} <= 10000, '最大连接数过大', warning

# --- 安全校验（仅 production 环境） ---
if ${context::env} == 'production':
    assert ${cfg::server.ssl} == true, '生产环境必须启用 SSL', error
    assert ${cfg::server.host} != '0.0.0.0', '生产环境不建议监听所有地址', warning
fi

# --- 日志校验 ---
assert ${cfg::logging.level} in ['debug', 'info', 'warning', 'error'], '日志级别不合法', error
```

### Step 3: 运行

```bash
# 开发环境校验
cmate run server_check.cmate -c cfg:server.json -C env:dev

# 生产环境校验
cmate run server_check.cmate -c cfg:server.json -C env:production
```

在 `dev` 环境下全部通过；在 `production` 环境下，SSL 未启用和监听地址会触发失败。

## 进阶用法

### 查看规则依赖

在不运行的情况下，查看规则文件需要哪些配置和上下文：

```bash
cmate inspect server_check.cmate
```

输出示例：

```
Overview
--------
  name : Web 服务配置检查
  version : 1.0

Context Variables
-----------------
  env : ['production']
    部署环境，可选值: dev / staging / production

Config Targets
--------------
  cfg
  ----
    type : .json
    description : Web 服务配置文件

Usage: -c <rule_name>:<file_path>  -C <context>:<value>
```

> **说明**：`Context Variables` 下的选项列表只显示规则文件中实际出现在 `if/elif` 条件
> 里的字面量值（如 `${context::env} == 'production'`），描述文字中提及的值不会被收录。

### 仅收集规则

列出所有规则，不执行，方便调试：

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production --collect-only
```

输出：

```
collected 9 items
<Target cfg>
  <test_20 ${cfg::server.port} > ${min_port}>
  <test_21 ${cfg::server.port} < 65536>
  ...
```

### 按严重级别过滤

只运行 `warning` 及以上级别的规则：

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -s warning
```

### 按行号筛选

只运行第 20 和 24 行的规则：

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -k 20,24
```

### 失败即停

遇到第一个失败就终止：

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -x
```

### 详细输出

每条规则单独一行显示状态：

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production -v
```

### 导出 JSON 结果

```bash
cmate run server_check.cmate -c cfg:server.json -C env:production --output-path ./results
```

结果文件保存至 `./results/cmate_<timestamp>_output.json`。

## 校验环境变量

`env` 是用于读取当前 shell 环境变量的内置目标，**不需要也不能**在 `[targets]` 中声明。直接编写 `[par env]` 段落，运行时传入 `-c env` 即可：

```
[par env]
assert ${OMP_NUM_THREADS} == '10', '建议设置 OMP 线程数为 10', info
assert ${CUDA_VISIBLE_DEVICES} != '', '必须指定 GPU 设备', error
```

运行：

```bash
cmate run env_check.cmate -c env
```

在 `[par env]` 中，不带命名空间的变量引用（如 `${OMP_NUM_THREADS}`）会自动解析为 `env` 命名空间，等价于 `${env::OMP_NUM_THREADS}`。

## 校验 LLM 推理服务配置（vLLM / SGLang）

命令行参数本质上也是配置，只是表达形式不同。vLLM 和 SGLang 都原生支持通过 `--config` 加载 YAML 配置文件，因此 CMate 可以直接校验推理服务的启动配置，无需额外的 CLI 解析。

### 为什么推荐 YAML 优先？

核心思路是：**以 YAML 配置文件作为唯一真实来源，同时用于启动服务和 CMate 校验。** 这从根本上避免了参数别名归一化的问题（例如 `--tp` vs `--tensor-parallel-size` vs `tensor_parallel_size`）。

### Step 1: 创建 YAML 配置文件

```yaml
# vllm_serve.yaml — 同时用于部署和校验
model: deepseek-v3
tensor-parallel-size: 8
gpu-memory-utilization: 0.95
max-model-len: 32768
dtype: auto
trust-remote-code: true
```

### Step 2: 编写校验规则

创建 `vllm_check.cmate`：

```
[metadata]
name = 'vLLM 推理服务配置检查'
version = '1.0'
---

[targets]
vllm_serve: 'vLLM 启动配置' @ 'yaml'
---

[contexts]
model_type: '模型类型，如 deepseek / general'
gpu_type: 'GPU 型号，如 A100 / A800 / 910B'
---

[par env]
assert ${VLLM_USE_V1} == '1', '必须使用 V1 引擎', error

if ${context::model_type} == 'deepseek':
    assert ${PYTORCH_NPU_ALLOC_CONF} == 'expandable_segments:True', 'DeepSeek 需要开启虚拟内存', warning
fi

[par vllm_serve]
# 基本校验
assert ${vllm_serve::tensor-parallel-size} >= 1, 'TP 大小必须为正数', error
assert ${vllm_serve::gpu-memory-utilization} > 0, 'GPU 显存利用率必须为正数', error
assert ${vllm_serve::gpu-memory-utilization} <= 0.98, 'GPU 显存利用率过高，有 OOM 风险', warning

# 模型相关规则
if ${context::model_type} == 'deepseek':
    assert ${vllm_serve::max-model-len} >= 8192, 'DeepSeek 需要更长的上下文窗口', warning
    assert ${vllm_serve::trust-remote-code} == true, 'DeepSeek 需要 trust-remote-code', error
fi

# GPU 相关规则
if ${context::gpu_type} == 'A100':
    assert ${vllm_serve::gpu-memory-utilization} <= 0.95, 'A100 建议 GPU 利用率', info
fi
```

### Step 3: 部署并校验

```bash
# 用同一个 YAML 部署
vllm serve --config vllm_serve.yaml

# 校验
cmate run vllm_check.cmate -c vllm_serve:vllm_serve.yaml -c env -C model_type:deepseek gpu_type:A100
```

### SGLang 用法相同

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

### Key Name 匹配

vLLM 和 SGLang 的 YAML 配置文件均使用 **长格式 kebab-case** 名称（如 `tensor-parallel-size`）。你的 `.cmate` 规则必须使用完全相同的 key 名。这就是为什么推荐 YAML 优先的原因 — key 名天然一致。

如果手动将 CLI 参数转为 YAML，要注意短别名（如 `-tp`）不会自动展开为 `tensor-parallel-size`，会导致校验静默失效。

### CLI 参数转 YAML（备选方案）

对于不支持 `--config` 的命令（如 `vllm bench serve`），可以用简单的转换脚本：

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

> **注意**：转换时请始终使用 `--long-form-names`。短参数（如 `-tp`）不会被自动归一化。

## 使用循环校验列表字段

```
[par cfg]
for host in ${cfg::server.allowed_hosts}:
    assert ${host} != '', '主机名不能为空', error
    assert len(${host}) < 256, '主机名过长', warning
done
```

对于键值对列表，还支持元组解包：

```
[par cfg]
for key, value in ${cfg::env_pairs}:
    assert ${value} != '', '值不能为空', error
done
```

## alert 语句

`alert` 与 `assert` 不同 —— 它不做条件判断，只是将一个字段标记出来供人工确认。字段必须是 `${namespace::path}` 形式的引用，不接受任意表达式。严重级别省略时默认为 `warning`。

```
[par cfg]
alert ${cfg::server.model_path}, '请确认模型路径正确', warning
```

alert 不影响最终的 pass/fail 计数，在输出中以 `ALERTS` 区域单独展示。

## DSL 语法速查

| 语法 | 示例 | 说明 |
|------|------|------|
| 数据访问 | `${config::key.path}` | namespace::jsonpath 风格 |
| 比较 | `==`, `!=`, `<`, `>`, `<=`, `>=` | 标准比较 |
| 正则匹配 | `=~` | `${val} =~ '^[a-z]+$'` |
| 成员测试 | `in`, `not in` | `${val} in ['a', 'b']` |
| 逻辑运算 | `and`, `or`, `not` | 布尔组合 |
| 算术运算 | `+`, `-`, `*`, `/`, `//`, `%`, `**` | 标准算术 |
| 条件分支 | `if ... elif ... else ... fi` | Shell 风格 |
| 循环 | `for x in <iterable>: ... done` | Shell 风格；支持 `for x, y in ...` 元组解包 |
| 循环控制 | `break`, `continue` | 退出或跳过当次循环 |
| 断言 | `assert <expr>, 'msg'[, severity]` | severity: error/warning/info；省略时默认 `error` |
| 提醒 | `alert ${ns::path}, 'msg'[, severity]` | 标记字段，不判断条件；省略时默认 `warning` |
| 函数调用 | `len()`, `int()`, `str()`, `range()` | 内置 + 自定义函数 |
| 单例值 | `true`, `false`, `None`, `NA` | `NA` 为字段缺失时的哨兵值 |

## 实际案例：大模型推理配置

以 vLLM-Ascend 环境变量校验为例（见 `presets/vllm.cmate`）：

```
[metadata]
name = 'VLLM-Ascend 配置项检查'
version = '1.0'
---

[par env]
assert ${OMP_PROC_BIND} == 'false', 'OpenMP 多线程绑核配置性能', info
assert ${OMP_NUM_THREADS} == '10', 'OpenMP 并行数建议设置为 10', info
assert ${VLLM_USE_V1} == '1', 'VLLM V1 engine 开关，不配置默认走 V0', error

if ${context::deploy_mode} == 'ep':
    assert ${VLLM_WORKER_MULTIPROC_METHOD} == 'fork', 'PD 分离场景下必要', error
fi
```

运行：

```bash
cmate run presets/vllm.cmate -c env -C deploy_mode:ep
```

这个例子展示了 CMate 的核心价值：将"什么环境下哪些变量应设什么值"这种专家经验编码为可分发的规则文件。

## 下一步

- 浏览 `presets/` 目录查看更多真实规则文件示例
- 在 `cmate/custom_fn.py` 中定义你自己的校验函数
- 通过 `cmate inspect` 了解任意规则文件的依赖结构
