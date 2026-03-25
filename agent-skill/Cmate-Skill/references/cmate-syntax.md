# CMate DSL Syntax Reference

This is the authoritative syntax reference for generating `.cmate` rule files. Every generated file MUST conform to these rules exactly.

## File Structure

A `.cmate` file consists of **sections** separated by `---`. Sections can appear in any order, but the conventional order is:

```
[metadata]     → optional, at most one
[targets]      → optional, at most one
[contexts]     → optional, at most one
[global]       → optional, at most one
[par <target>] → one or more
```

### Section: `[metadata]`

Key-value assignments for rule file metadata.

```
[metadata]
name = 'Rule Set Name'
version = '1.0'
authors = [{"name": "Author Name", "email": "email@example.com"}]
description = 'What this rule set validates'
---
```

- Values can be strings (`'...'`), numbers, lists, or dicts
- This section is purely informational; it does not affect validation logic

### Section: `[targets]`

Declares which configuration files the rules will validate. Format: `name: 'description' @ 'format'`

```
[targets]
config: 'Main config file' @ 'json'
env_config: 'Environment config' @ 'yaml'
---
```

- Supported formats: `'json'`, `'yaml'`, `'yml'`
- The `@ 'format'` part is optional (format can be inferred from file extension at runtime)
- **`env` is a built-in target** for environment variables — do NOT declare it in `[targets]`
- Every `[par X]` section (except `[par env]`) MUST have a matching entry in `[targets]`

### Section: `[contexts]`

Declares context variables used for scenario-based rule switching.

```
[contexts]
deploy_mode: 'Deployment mode, options: pd_mix / pd_disaggregation / ep'
model_type: 'Model type, e.g. deepseek / general'
---
```

- Context values are supplied at runtime via `-C name:value`
- Referenced in rules as `${context::variable_name}`
- Every `${context::var}` used in rules MUST be declared here (if this section exists)

### Section: `[global]`

Global variable definitions and conditional logic, available to all `[par]` sections.

```
[global]
min_port = 1024
max_timeout = 30000

if ${context::env} == 'production':
    min_port = 8000
    max_timeout = 10000
fi
---
```

- Variables defined here are accessed as `${variable_name}` in `[par]` sections
- Supports `if/elif/else/fi` and `for/done` control flow
- Can reference `${context::var}` for conditional assignment

### Section: `[par <target>]`

Partition sections containing validation rules. Each partition corresponds to a target.

```
[par config]
assert ${config::server.port} > 1024, 'Port too low', error
assert ${config::host} != '', 'Host required', error

[par env]
assert ${OMP_NUM_THREADS} == '10', 'Recommended thread count', info
```

- `[par env]` is special: no `[targets]` declaration needed, reads shell environment
- The last `[par]` section does NOT require a trailing `---`
- Multiple `[par]` sections for different targets are allowed

## Data Types

| Type | Syntax | Examples |
|---|---|---|
| Integer | digits | `42`, `-5`, `0` |
| Float | digits with dot | `3.14`, `-0.5` |
| String | single quotes | `'hello'`, `'path/to/file'` |
| Boolean | lowercase keywords | `true`, `false` |
| None | keyword | `None` |
| NA | keyword | `NA` (sentinel for missing values) |
| List | brackets | `[1, 2, 3]`, `['a', 'b']` |
| Dict | braces | `{"key": "value"}` |

**Important**: In the DSL body, strings MUST use single quotes. Double quotes are only used inside JSON-style dict literals.

## Operators

### Comparison
| Operator | Meaning | Example |
|---|---|---|
| `==` | Equal | `${val} == 'expected'` |
| `!=` | Not equal | `${val} != ''` |
| `<` | Less than | `${val} < 100` |
| `>` | Greater than | `${val} > 0` |
| `<=` | Less or equal | `${val} <= 65535` |
| `>=` | Greater or equal | `${val} >= 1024` |
| `=~` | Regex match | `${val} =~ '^[a-z]+$'` |
| `in` | Membership | `${val} in ['a', 'b', 'c']` |
| `not in` | Non-membership | `${val} not in ['x', 'y']` |

### Logical
| Operator | Example |
|---|---|
| `and` | `${a} > 0 and ${b} > 0` |
| `or` | `${a} == 'x' or ${a} == 'y'` |
| `not` | `not ${flag}` |

### Arithmetic
| Operator | Meaning |
|---|---|
| `+`, `-`, `*`, `/` | Standard arithmetic |
| `//` | Floor division |
| `%` | Modulo |
| `**` | Exponentiation |

### Chained Comparisons

CMate supports Python-style chained comparisons:

```
assert 1 <= ${config::port} <= 65535, 'Port out of range', error
```

This is equivalent to `${config::port} >= 1 and ${config::port} <= 65535`.

## Statements

### assert

```
assert <expression>, '<message>'[, <severity>]
```

- `<expression>`: Any expression that evaluates to truthy/falsy
- `<message>`: Single-quoted string describing the rule
- `<severity>`: Optional, one of `error`, `warning`, `info`. Defaults to `error`

Examples:
```
assert ${config::port} > 1024, 'Port should be above 1024', error
assert ${env::HOME} != '', 'HOME must be set'
assert ${config::timeout} >= 1000, 'Recommended timeout >= 1000ms', info
assert ${value} in ['a', 'b', 'c'], 'Invalid value', warning
assert path_exists(${config::model_path}), 'Model path must exist', error
assert ${val} =~ '^[0-9]+$', 'Must be numeric string', error
```

### alert

```
alert ${namespace::path}, '<message>'[, <severity>]
```

- Marks a field for manual review without evaluating a condition
- Field MUST be a `${namespace::path}` reference (not an arbitrary expression)
- Default severity is `warning`

Example:
```
alert ${config::model_path}, 'Please verify the model path is correct', warning
```

### if / elif / else / fi

```
if <expression>:
    <statements>
elif <expression>:
    <statements>
else:
    <statements>
fi
```

- Colons after conditions are required
- `fi` closes the block (shell-style, not Python-style indentation)
- Nesting is supported

### for / done

```
for <variable> in <iterable>:
    <statements>
done
```

Tuple unpacking is supported:
```
for key, value in ${config::env_pairs}:
    assert ${value} != '', 'Value must not be empty', error
done
```

### break / continue

Standard loop control, only valid inside `for/done` blocks.

## Variable Access

### Namespaced paths
```
${config::server.port}        # config namespace, dotted path
${config::items[0].name}      # array indexing
${env::OMP_NUM_THREADS}       # environment variable
${context::deploy_mode}       # context variable
```

### Global variables
```
${min_port}                    # global variable (no namespace)
${global::cur_ip}             # explicit global namespace
```

### Resolution order in [par] sections
Inside `[par X]`, an unqualified `${variable}`:
1. If it's a loop variable → resolves to the current loop item
2. If `global::variable` exists → resolves to the global
3. Otherwise → resolves to `X::variable` (the partition's namespace)

## Built-in Functions

| Function | Description |
|---|---|
| `len(x)` | Length of string/list/dict |
| `int(x)` | Convert to integer |
| `str(x)` | Convert to string |
| `float(x)` | Convert to float |
| `bool(x)` | Convert to boolean |
| `range(start, stop)` | Range of integers |
| `sum(x)` | Sum of iterable |
| `min(x)` | Minimum value |
| `max(x)` | Maximum value |
| `path_exists(path)` | Check if filesystem path exists |
| `is_port_in_use(port)` | Check if network port is in use |
| `image_exists(name)` | Check if Docker image exists locally |

## Comments

```
# This is a comment
assert ${val} > 0, 'Must be positive'  # Inline comments NOT supported — use line above
```

Comments start with `#` and extend to end of line. They must be on their own line.

## Common Patterns

### Environment variable validation
```
[par env]
assert ${OMP_NUM_THREADS} == '10', 'Recommended OMP thread count', info
assert ${CUDA_VISIBLE_DEVICES} != '', 'GPU device must be set', error
```

Note: In `[par env]`, unqualified variables like `${OMP_NUM_THREADS}` automatically resolve to `env::OMP_NUM_THREADS`. Environment variable values are always strings.

### Conditional rules by scenario
```
[contexts]
deploy_mode: 'Deployment mode'
---

[par env]
if ${context::deploy_mode} == 'production':
    assert ${SSL_ENABLED} == 'true', 'SSL required in production', error
fi
```

### Config file validation
```
[targets]
config: 'Application config' @ 'json'
---

[par config]
assert ${config::server.port} > 1024, 'Port too low', error
assert ${config::server.host} != '0.0.0.0', 'Avoid binding all interfaces', warning
```

### Range validation
```
assert 1 <= ${config::timeout} and ${config::timeout} <= 60000, 'Timeout out of range', error
# Or using chained comparison:
assert 1 <= ${config::timeout} <= 60000, 'Timeout out of range', error
```

### List membership
```
assert ${config::log_level} in ['debug', 'info', 'warning', 'error'], 'Invalid log level', error
```
