# Column Mapping Reference

This document describes how to detect and map columns from user-provided tabular data to CMate rule components.

## Detection Algorithm

### Step 1: Normalize Column Names

Before matching, normalize all column headers:
1. Convert to lowercase
2. Strip whitespace and underscores
3. Remove special characters except alphanumeric and Chinese characters

Example: `"Expected Value "` → `"expectedvalue"`, `"变量名"` → `"变量名"`

### Step 2: Match Columns

Match normalized headers against these patterns (first match wins):

#### Variable / Path (REQUIRED)
The field being validated — an environment variable name, config key, or JSON path.

| Priority | Patterns (normalized) |
|---|---|
| 1 | `variable`, `var`, `envvar`, `environmentvariable` |
| 2 | `field`, `key`, `configkey`, `parameter`, `param` |
| 3 | `path`, `jsonpath`, `configpath` |
| 4 | `name`, `paramname`, `variablename` |
| 5 | `变量`, `变量名`, `配置项`, `参数`, `参数名`, `环境变量` |

#### Expected Value (REQUIRED)
The value the field should have.

| Priority | Patterns |
|---|---|
| 1 | `expected`, `expectedvalue`, `value`, `val` |
| 2 | `recommended`, `recommendedvalue`, `default`, `defaultvalue` |
| 3 | `target`, `targetvalue`, `shouldbe` |
| 4 | `期望值`, `推荐值`, `目标值`, `值`, `预期值` |

#### Operator (OPTIONAL)
How to compare. Defaults to `==` if not present.

| Priority | Patterns |
|---|---|
| 1 | `operator`, `op`, `comparison`, `comparator` |
| 2 | `check`, `checktype`, `condition_type` |
| 3 | `比较符`, `操作符`, `运算符` |

Recognized operator values and their mappings:
| User Input | CMate Operator |
|---|---|
| `==`, `eq`, `equals`, `equal`, `等于` | `==` |
| `!=`, `ne`, `notequal`, `not_equal`, `不等于` | `!=` |
| `>`, `gt`, `greater`, `greaterthan`, `大于` | `>` |
| `<`, `lt`, `less`, `lessthan`, `小于` | `<` |
| `>=`, `gte`, `ge`, `大于等于` | `>=` |
| `<=`, `lte`, `le`, `小于等于` | `<=` |
| `in`, `oneof`, `isin`, `包含`, `属于` | `in` |
| `not in`, `notin`, `notcontain`, `不包含` | `not in` |
| `=~`, `regex`, `match`, `matches`, `正则` | `=~` |
| `exists`, `pathexists`, `fileexists`, `路径存在` | use `path_exists()` function |

#### Condition / Scenario (OPTIONAL)
When this rule applies. Maps to `if` blocks and `[contexts]` entries.

| Priority | Patterns |
|---|---|
| 1 | `condition`, `when`, `scenario`, `context` |
| 2 | `applieswhen`, `prerequisite`, `ifcondition` |
| 3 | `deploymode`, `mode`, `environment`, `env` (when not the variable column) |
| 4 | `条件`, `场景`, `适用场景`, `前提条件`, `生效条件` |

Condition value formats:
- Simple: `deploy_mode == 'ep'` → `if ${context::deploy_mode} == 'ep':`
- Combined: `deploy_mode == 'ep' and npu_type == 'A2'` → `if ${context::deploy_mode} == 'ep' and ${context::npu_type} == 'A2':`
- Plain value: `production` → requires asking user which context variable this belongs to

#### Severity (OPTIONAL)
Rule importance level. Defaults to `error` if not present.

| Priority | Patterns |
|---|---|
| 1 | `severity`, `level`, `priority` |
| 2 | `importance`, `type`, `ruletype` |
| 3 | `级别`, `严重度`, `优先级`, `重要性` |

Severity value mappings:
| User Input | CMate Severity |
|---|---|
| `error`, `err`, `mandatory`, `required`, `must`, `critical`, `high`, `强制`, `必须`, `错误` | `error` |
| `warning`, `warn`, `recommended`, `should`, `medium`, `alert`, `告警`, `警告`, `建议修复` | `warning` |
| `info`, `information`, `optional`, `suggestion`, `recommend`, `may`, `low`, `提示`, `推荐`, `信息` | `info` |

#### Message / Description (OPTIONAL)
Human-readable explanation of the rule. Auto-generated if not present.

| Priority | Patterns |
|---|---|
| 1 | `message`, `msg`, `description`, `desc` |
| 2 | `reason`, `explanation`, `note`, `comment` |
| 3 | `说明`, `描述`, `消息`, `原因`, `备注` |

Auto-generation template when missing:
- `"<variable> should be <operator> <expected_value>"`
- Example: `"OMP_NUM_THREADS should be == '10'"`

#### Namespace / Target (OPTIONAL)
Which config source this rule validates. Defaults based on variable naming.

| Priority | Patterns |
|---|---|
| 1 | `namespace`, `ns`, `target`, `source` |
| 2 | `file`, `configfile`, `sourcefile` |
| 3 | `命名空间`, `目标`, `来源`, `配置文件` |

Auto-detection when missing:
- If variable looks like `UPPER_CASE_NAME` → assume `env` namespace
- If variable contains dots (e.g., `server.port`) → assume a config file namespace
- If variable starts with a namespace prefix (e.g., `config::key`) → extract namespace
- Otherwise → ask the user

### Step 3: Handle Ambiguity

If the algorithm cannot confidently map columns:

1. **Show the detected mapping** to the user for confirmation
2. **Ask about unmapped columns** — they might contain useful info
3. **Ask about missing required columns** — the user might need to specify them manually

### Step 4: Handle Special Values

When processing cell values:

- **Empty cells**: Skip the row or use a default, depending on which column is empty
- **Multiple values in one cell** (comma-separated): Convert to list for `in` operator
  - Example: cell value `"10, 20, 30"` → `in ['10', '20', '30']`
- **Boolean strings**: `"true"/"false"/"yes"/"no"` → convert appropriately
- **Numeric strings**: Preserve as strings for env vars (they're always strings in shell), convert to numbers for config files
- **`N/A`, `NA`, `-`, `null`**: Map to `NA` singleton

## Grouping Rules for Output

### By Namespace
Group all rules targeting the same namespace into one `[par <namespace>]` section.

### By Condition
Within a partition, group rules with the same condition into `if` blocks:

```
[par env]
# Rules without conditions come first
assert ${COMMON_VAR} == 'val', 'Always required', error

# Then grouped by condition
if ${context::deploy_mode} == 'ep':
    assert ${EP_VAR1} == 'val1', 'EP specific', error
    assert ${EP_VAR2} == 'val2', 'EP specific', info
fi

if ${context::deploy_mode} == 'pd_mix':
    assert ${PD_VAR} == 'val', 'PD mix specific', error
fi
```

### Ordering
1. Unconditional rules first
2. Conditional rules grouped by condition
3. Within each group, order by: error → warning → info
4. Within same severity, preserve original row order from the source file
