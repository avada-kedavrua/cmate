# CMate 快速上手

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
  env : ['dev', 'staging', 'production']
    部署环境

Config Targets
--------------
  cfg
  ----
    type : .json
    description : Web 服务配置文件

Usage: -c <rule_name>:<file_path>  -C <context>:<value>
```

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

cmate 支持直接校验当前 shell 环境变量：

```
[targets]
env_config: '环境变量配置' @ 'json'
---

[par env]
assert ${OMP_NUM_THREADS} == '10', '建议设置 OMP 线程数为 10', info
```

运行时通过 `-c env` 传入（无需指定文件路径）：

```bash
cmate run env_check.cmate -c env
```

## 使用循环校验列表字段

```
[par cfg]
for host in ${cfg::server.allowed_hosts}:
    assert ${host} != '', '主机名不能为空', error
    assert len(${host}) < 256, '主机名过长', warning
done
```

## alert 语句

`alert` 与 `assert` 不同 —— 它不做条件判断，只是将一个字段标记出来供人工确认：

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
| 成员测试 | `in` | `${val} in ['a', 'b']` |
| 逻辑运算 | `and`, `or`, `not` | 布尔组合 |
| 算术运算 | `+`, `-`, `*`, `/`, `//`, `%`, `**` | 标准算术 |
| 条件分支 | `if ... elif ... else ... fi` | Shell 风格 |
| 循环 | `for x in <iterable>: ... done` | Shell 风格 |
| 断言 | `assert <expr>, 'msg', severity` | severity: error/warning/info |
| 提醒 | `alert <expr>, 'msg', severity` | 标记字段，不判断条件 |
| 函数调用 | `len()`, `int()`, `str()`, `range()` | 内置 + 自定义函数 |

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
