# CMate

<p align="center">
  <b>你的配置校验伴侣 — Config Mate</b>
</p>

<p align="center">
  <a href="#简介">简介</a> &bull;
  <a href="#安装">安装</a> &bull;
  <a href="#快速开始">快速开始</a> &bull;
  <a href="docs/zh/quick_start.md">详细指南</a> &bull;
  <a href="README_en.md">English</a> &bull;
  <a href="#许可证">许可证</a>
</p>

---

## 简介

**CMate**（**C**onfig **Mate**）是一个面向配置文件的声明式校验引擎。名字灵感来源于国际象棋中的 *Check Mate*（将杀）—— 它是你的配置"校验伴侣"，帮你精准拦截配置问题。

### 为什么需要 CMate?

配置文件的正确性校验只是基本诉求。真正的痛点在于：**同一套配置字段，在不同的部署场景下，最优值可能完全不同。**

以大模型推理服务为例：PD 混部和 PD 分离场景下，同一个参数的推荐值可能截然不同；DeepSeek 模型和通用模型需要检查的字段集也不一样。这些"哪些字段在什么场景下应该设什么值"的组合逻辑，通常只存在于专家经验中，难以沉淀和传递。

CMate 通过 **context（上下文变量）** 来管理场景切换，通过 **severity（严重级别）** 来区分推荐配置和强制要求，将这些经验编码为可分发、可执行的 `.cmate` 规则文件。

### 核心特性

- **直觉化 DSL**：语法借鉴 Python、Shell 和 JsonPath，每写一条校验规则就像写一行单元测试
- **上下文驱动**：通过 `-C` 传入 context 变量，同一份规则文件可适配不同部署场景
- **三级严重度**：`error`（强制）/ `warning`（告警）/ `info`（推荐），按需过滤执行
- **多数据源**：支持 JSON、YAML 配置文件及环境变量作为校验目标
- **环境变量脚本生成**：自动根据 `[par env]` 规则生成 `set_env.sh`，一键 `source` 即可设置或还原环境变量
- **pytest 风格输出**：收集、执行、报告的展示风格借鉴 pytest，对开发者友好
- **条件与循环**：支持 `if/elif/else/fi` 条件分支和 `for/done` 循环
- **可扩展函数**：内置 `len()`、`int()`、`str()` 等函数，支持在 `custom_fn.py` 中自定义扩展

## 安装

### 环境要求

- Python >= 3.7

### pip 安装

```bash
pip install cmate
```

### 从源码安装

```bash
git clone https://github.com/avada-kedavrua/cmate.git # or https://gitcode.com/AvadaKedavrua/cmate.git
cd cmate
pip install -e .
```

## 快速开始

> 完整的快速上手教程请查看 [详细指南](docs/zh/quick_start.md)。

创建规则文件 `demo.cmate`：

```
[metadata]
name = '服务端口配置检查'
version = '1.0'
---

[targets]
config: '应用配置文件' @ 'json'
---

[contexts]
env: '部署环境，可选值: dev / staging / production'
---

[global]
min_port = 1024
if ${context::env} == 'production':
    min_port = 8000
fi
---

[par config]
assert ${config::port} > ${min_port}, '端口号过低', error
assert ${config::host} != '', '主机名不能为空', error
assert ${config::timeout} >= 1000, '建议超时时间 >= 1000ms', info
```

准备 `app.json`：

```json
{
  "port": 8080,
  "host": "localhost",
  "timeout": 5000
}
```

运行：

```bash
cmate run demo.cmate -c config:app.json -C env:production
```

## 环境变量脚本生成

当规则文件中包含 `[par env]` 段时，`cmate run` 会自动在当前目录生成 `set_env.sh` 脚本。该脚本根据规则中的期望值，一键设置或还原环境变量：

```bash
# 应用规则推荐的环境变量
source set_env.sh

# 还原为运行 cmate 之前的值
source set_env.sh 0
```

生成脚本只需要：

```bash
cmate run rules.cmate -c env
```

## 校验 LLM 推理服务配置（vLLM / SGLang）

命令行参数本质上也是配置，只是表达形式不同。CMate 校验的是配置文件，而 vLLM 和 SGLang 都原生支持通过 `--config` 加载 YAML 配置文件。这意味着你可以直接用 CMate 校验推理服务的启动配置，无需额外的 CLI 解析。

### 最佳实践：以 YAML 配置文件作为唯一真实来源

不要把参数散落在启动脚本中，而是维护一份 YAML 配置文件，同时用于启动服务和 CMate 校验：

```yaml
# vllm_serve.yaml
model: deepseek-v3
tensor-parallel-size: 8
gpu-memory-utilization: 0.95
max-model-len: 32768
dtype: auto
trust-remote-code: true
```

用同一个文件启动和校验：

```bash
# 部署
vllm serve --config vllm_serve.yaml

# 校验
cmate run vllm_rules.cmate -c vllm_serve:vllm_serve.yaml -C model_type:deepseek
```

SGLang 同理：

```yaml
# sglang_serve.yaml
model-path: deepseek-v3
host: 0.0.0.0
port: 30000
tensor-parallel-size: 8
mem-fraction-static: 0.9
```

```bash
# 部署
python -m sglang.launch_server --config sglang_serve.yaml

# 校验
cmate run sglang_rules.cmate -c sglang_serve:sglang_serve.yaml
```

### 示例规则文件

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
gpu_type: 'GPU 型号，如 A100 / A800'
---

[par env]
assert ${VLLM_USE_V1} == '1', '必须使用 V1 引擎', error

[par vllm_serve]
assert ${vllm_serve::tensor-parallel-size} >= 1, 'TP 大小必须为正数', error
assert ${vllm_serve::gpu-memory-utilization} <= 0.98, 'GPU 显存利用率过高', warning

if ${context::model_type} == 'deepseek':
    assert ${vllm_serve::max-model-len} >= 8192, 'DeepSeek 需要更长的上下文', warning
    assert ${vllm_serve::trust-remote-code} == true, 'DeepSeek 需要 trust-remote-code', error
fi
```

### Key Name 匹配：为什么推荐 YAML 优先

**重要**：YAML 配置文件中的 key 名必须与 `.cmate` 规则文件中使用的 key 名完全一致。vLLM 和 SGLang 的 YAML 配置均使用 **长格式 kebab-case** 名称（如 `tensor-parallel-size`），规则文件中也应使用相同的名称。

如果你使用 CLI 短别名（如 `-tp 8` 而不是 `--tensor-parallel-size 8`）并手动转换为 YAML，key 名可能与规则文件不匹配，导致校验静默失效。这就是为什么推荐以 YAML 配置文件作为唯一真实来源：它从根本上消除了别名归一化问题。

| 方式 | Key 名一致性 | 是否推荐？ |
|------|-------------|-----------|
| YAML 配置文件（`--config`） | 有保障 — YAML 和规则使用相同的 key | ✅ 推荐 |
| 手动 CLI 转 YAML | 存在别名不匹配风险（`tp` vs `tensor-parallel-size`） | ⚠️ 需谨慎 |

### 纯 CLI 场景的转换方式

如果确实需要校验没有 YAML 配置文件的命令（如 `vllm bench serve`），可以用简单脚本将 CLI 参数转为 YAML：

```python
# cli2yaml.py — 将 CLI 参数转换为 YAML
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

使用方式：

```bash
python cli2yaml.py --model deepseek-v3 --tensor-parallel-size 8 --trust-remote-code > cli_args.yaml
cmate run rules.cmate -c vllm_serve:cli_args.yaml
```

> **注意**：短参数（如 `-tp`）不会被自动归一化为标准长格式（`tensor-parallel-size`）。转换 CLI 参数时，请始终使用 `--long-form-names` 以确保与 CMate 规则匹配。

## 规则文件语法

一个 `.cmate` 文件由以下几个段落（section）组成，段落之间用 `---` 分隔：

### `[metadata]` — 元数据

```
[metadata]
name = '规则集名称'
version = '1.0'
authors = [{"name": "作者"}]
description = '规则集描述'
---
```

### `[targets]` — 校验目标声明

声明规则文件需要哪些配置文件作为输入，格式为 `名称: '描述' @ '格式'`：

```
[targets]
config: '主配置文件' @ 'json'
env_config: '环境变量配置' @ 'yaml'
---
```

运行时通过 `-c` 传入实际文件路径：`cmate run rules.cmate -c config:app.json`

特殊目标 `env` 表示读取当前环境变量，无需指定文件。

### `[contexts]` — 上下文变量声明

声明规则文件接受哪些上下文变量，用于按场景切换校验逻辑：

```
[contexts]
deploy_mode: '部署模式，可选值: pd_mix / pd_disaggregation / ep'
model_type: '模型类型，如 deepseek / general'
---
```

运行时通过 `-C` 传入：`cmate run rules.cmate -c config:app.json -C deploy_mode:ep`

在规则中通过 `${context::变量名}` 引用。

### `[global]` — 全局变量

定义全局变量和条件赋值逻辑，可在后续 `[par]` 段中引用：

```
[global]
max_connections = 100

if ${context::env} == 'production':
    max_connections = 500
fi
---
```

### `[par <target>]` — 分区校验规则

`par` 是 partition 的缩写，每个分区对应一个 target，在其中编写 `assert` 断言：

```
[par config]
# 基本断言：assert <表达式>, '消息', <严重级别>
assert ${config::enabled} == true, '服务必须启用', error
assert ${config::port} > 1024, '端口建议大于 1024', info

# 条件断言
if ${context::deploy_mode} == 'production':
    assert ${config::ssl} == true, '生产环境必须启用 SSL', error
fi

# 循环断言
for host in ${config::allowed_hosts}:
    assert ${host} != '', '主机名不能为空', error
done

# alert 语句：标记字段供人工确认，不做条件判断
alert ${config::model_path}, '请确认模型路径正确', warning
```

### 严重级别

| 级别 | 含义 | 输出标记 |
|------|------|----------|
| `error` | 强制要求，不满足即失败 | `[NOK]` |
| `warning` | 告警，建议修复 | `[WARNING]` |
| `info` | 推荐配置，供参考 | `[RECOMMEND]` |

通过 `-s` 参数可过滤最低级别：`cmate run rules.cmate -c config:app.json -s warning` 将只执行 `warning` 和 `error` 级别的规则。

### 数据访问与表达式

```
# 访问配置值（namespace::jsonpath 风格）
${config::server.port}
${config::items[0].name}
${context::deploy_mode}

# 比较运算: ==, !=, <, >, <=, >=, =~（正则匹配）, in
# 逻辑运算: and, or, not
# 算术运算: +, -, *, /, //, %, **
# 内置函数: len(), int(), str(), range(), path_exists(), is_port_in_use() 等
```

## CLI 参考

```bash
# 运行校验
cmate run <rule_file> [选项]
  -c, --configs   配置文件: '<名称>:<路径>[@<格式>]' 或 'env'
  -C, --contexts  上下文变量: '<名称>:<值>'
  -s, --severity  最低严重级别过滤: info | warning | error（默认 info）
  -x, --fail-fast 遇到第一个失败立即停止
  -v, --verbose   详细输出
  -k, --lines     按行号筛选规则: '10,20,30'
  -co, --collect-only  仅收集并列出规则，不执行
  --output-path   JSON 结果文件输出目录

# 查看规则文件信息
cmate inspect <rule_file> [选项]
  -f, --format    输出格式: text | json（默认 text）
```

## 项目结构

```
cmate/
├── cmate/
│   ├── cmate.py        # CLI 入口与核心调度
│   ├── lexer.py        # 词法分析器
│   ├── parser.py       # 语法分析器
│   ├── _ast.py         # AST 节点定义
│   ├── visitor.py      # AST 遍历与求值
│   ├── _test.py        # 测试运行器（pytest 风格输出）
│   ├── data_source.py  # 数据源管理（namespace::path 键值存储）
│   ├── custom_fn.py    # 可扩展自定义函数
│   └── util.py         # 工具函数
├── presets/            # 预置规则文件示例
├── tests/             # 单元测试
└── pyproject.toml     # 项目配置
```

## 贡献

欢迎提交 Issue 和 Pull Request。

```bash
# 开发环境
git clone https://github.com/avada-kedavrua/cmate.git # or https://gitcode.com/AvadaKedavrua/cmate.git
cd cmate
pip install -e .

# 运行测试
pytest tests/

# 代码检查
lintrunner -a
```

## 许可证

CMate 采用 [Mulan PSL v2](http://license.coscl.org.cn/MulanPSL2) 许可证。

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
