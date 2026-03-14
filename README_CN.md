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
git clone https://gitcode.com/AvadaKedavrua/cmate.git
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

自定义输出路径或禁用生成：

```bash
# 自定义路径
cmate run rules.cmate -c env --env-script /tmp/my_env.sh

# 禁用生成
cmate run rules.cmate -c env --no-env-script
```

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
  --env-script    环境变量脚本输出路径（默认 set_env.sh）
  --no-env-script 禁用环境变量脚本生成

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
git clone https://gitcode.com/AvadaKedavrua/cmate.git
cd cmate
pip install -e ".[dev]"

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
