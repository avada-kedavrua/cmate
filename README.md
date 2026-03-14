# CMate

<p align="center">
  <b>配置管理与测试引擎 (Configuration Management and Testing Engine)</b>
</p>

<p align="center">
  <a href="#安装">安装</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#使用指南">使用指南</a> •
  <a href="#贡献">贡献</a> •
  <a href="#许可证">许可证</a>
</p>

---

## 简介

CMate 是一个强大的配置验证和测试引擎，专为复杂配置文件的自动化验证而设计。它提供了一种声明式的规则定义语言，让您能够轻松编写配置验证规则，并支持多种数据源和灵活的表达式计算。

### 核心特性

- **声明式规则语言**: 使用简洁的 DSL 编写验证规则
- **多数据源支持**: 支持 JSON、YAML 等多种配置格式
- **灵活表达式**: 支持算术运算、逻辑运算、正则匹配等
- **条件控制流**: 支持 if/elif/else 条件分支和 for 循环
- **环境变量管理**: 自动生成环境变量设置脚本
- **详细报告**: 提供清晰的验证结果和错误信息

## 安装

### 环境要求

- Python 3.7+

### 使用 pip 安装

```bash
pip install cmate
```

### 从源码安装

```bash
git clone https://github.com/your-repo/cmate.git
cd cmate
pip install -e .
```

## 快速开始

### 1. 创建规则文件

创建一个名为 `example.cmate` 的规则文件：

```cmate
[metadata]
name = '示例配置检查'
version = '1.0'
---

[dependency]
config: '主配置文件' @ 'json'
---

[global]
# 设置默认值
default_port = 8080
---

[par config]
# 验证配置项
assert ${config::port} > 0, '端口必须是正整数', error
assert ${config::host} != '', '主机名不能为空', error
assert ${config::timeout} >= 1000, '超时时间应大于等于1000ms', warning
```

### 2. 创建配置文件

创建一个 `config.json`：

```json
{
  "port": 8080,
  "host": "localhost",
  "timeout": 5000
}
```

### 3. 运行验证

```bash
cmate run example.cmate -c config:config.json
```

## 使用指南

### 查看规则信息

使用 `inspect` 命令查看规则文件定义的依赖和上下文：

```bash
cmate inspect example.cmate
```

### 运行验证

```bash
# 基本用法
cmate run <rule_file> -c <name>:<path>

# 指定多个配置
cmate run example.cmate -c config:app.json -c env:env.yaml

# 设置上下文变量
cmate run example.cmate -c config:app.json -C mode:production

# 仅收集规则而不执行
cmate run example.cmate -c config:app.json --collect-only

# 失败即停止
cmate run example.cmate -c config:app.json --fail-fast

# 详细输出
cmate run example.cmate -c config:app.json --verbose
```

### 规则语法

#### 元数据段

```cmate
[metadata]
name = '规则名称'
version = '1.0'
author = 'Your Name'
---
```

#### 依赖段

```cmate
[dependency]
config: '配置文件描述' @ 'json'
env: '环境变量配置'
---
```

#### 全局段

```cmate
[global]
# 变量赋值
max_connections = 100
timeout = 30

# 条件赋值
if ${context::env} == 'production':
    timeout = 60
fi

# 循环赋值
for item in [1, 2, 3]:
    value = ${item} * 2
done
---
```

#### 分区段

```cmate
[par config]
# 简单断言
assert ${config::enabled} == true, '服务必须启用'

# 带严重级别的断言
assert ${config::port} > 1024, '端口应大于1024', warning
assert ${config::port} < 65536, '端口必须小于65536', error

# 条件断言
if ${context::strict_mode}:
    assert ${config::ssl} == true, '严格模式下必须启用SSL', error
fi

# 循环断言
for item in ${config::allowed_hosts}:
    assert ${item} != '', '主机名不能为空'
done
```

### 支持的表达式

- **比较运算**: `==`, `!=`, `<`, `>`, `<=`, `>=`, `=~` (正则匹配), `in`
- **逻辑运算**: `and`, `or`, `not`
- **算术运算**: `+`, `-`, `*`, `/`, `//`, `%`, `**`
- **数据访问**: `${namespace::path.to.value}`
- **函数调用**: `len()`, `int()`, `str()`, `range()`, 等

## 项目结构

```
cmate/
├── cmate/              # 核心源代码
│   ├── cmate.py       # 主程序入口
│   ├── lexer.py       # 词法分析器
│   ├── parser.py      # 语法分析器
│   ├── visitor.py     # AST 访问器
│   ├── _ast.py        # AST 节点定义
│   ├── data_source.py # 数据源管理
│   ├── util.py        # 工具函数
│   ├── custom_fn.py   # 自定义函数
│   └── _test.py       # 测试框架
├── tests/             # 单元测试
├── presets/           # 预设规则
└── pyproject.toml     # 项目配置
```

## 贡献

我们欢迎所有形式的贡献，包括但不限于：

- 提交问题和建议
- 改进文档
- 修复 bug
- 添加新功能

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/your-repo/cmate.git
cd cmate

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/

# 运行代码检查
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

## 致谢

感谢所有为 CMate 做出贡献的开发者。

---

<p align="center">
  <b>CMate - 让配置验证更简单</b>
</p>
