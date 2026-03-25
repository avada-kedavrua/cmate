# Example: JSON Config Requirements (CSV → .cmate)

## Source File: `server_requirements.csv`

```csv
config_key,expected,operator,severity,message,condition
server.port,1024,>=,error,Port must be above 1024,
server.port,65536,<,error,Port must be below 65536,
server.host,,!=,error,Hostname must not be empty,
server.timeout,1000,>=,warning,Timeout should be at least 1000ms,
server.max_connections,10000,<=,warning,Max connections too high,
server.ssl,true,==,error,SSL must be enabled in production,env == production
server.host,0.0.0.0,!=,warning,Avoid binding all interfaces in production,env == production
logging.level,"debug,info,warning,error",in,error,Invalid log level,
```

## Column Detection

The skill detects:
- `config_key` → **variable/path** (contains dots → config file path)
- `expected` → **expected value**
- `operator` → **operator**
- `severity` → **severity**
- `message` → **message**
- `condition` → **condition**
- No namespace column → auto-detect: dotted paths → need a config namespace

Since no namespace is specified and paths use dots, the skill asks:
> "These look like JSON config paths. What should I name the config target? (e.g., `config`, `server_config`)"

User responds: `cfg`

## Generated File: `server_requirements.cmate`

```
[metadata]
name = 'Server Configuration Requirements'
version = '1.0'
description = 'Auto-generated from server_requirements.csv'
---

[targets]
cfg: 'Server configuration file' @ 'json'
---

[contexts]
env: 'Deployment environment'
---

[par cfg]
# Port validation
assert ${cfg::server.port} >= 1024, 'Port must be above 1024', error
assert ${cfg::server.port} < 65536, 'Port must be below 65536', error

# General validation
assert ${cfg::server.host} != '', 'Hostname must not be empty', error
assert ${cfg::server.timeout} >= 1000, 'Timeout should be at least 1000ms', warning
assert ${cfg::server.max_connections} <= 10000, 'Max connections too high', warning

# Logging
assert ${cfg::logging.level} in ['debug', 'info', 'warning', 'error'], 'Invalid log level', error

# Production environment
if ${context::env} == 'production':
    assert ${cfg::server.ssl} == true, 'SSL must be enabled in production', error
    assert ${cfg::server.host} != '0.0.0.0', 'Avoid binding all interfaces in production', warning
fi
```

## Run Command

```bash
cmate run server_requirements.cmate -c cfg:server.json -C env:production
```

## Key Conversion Decisions

1. **Operator column used directly**: `>=`, `<`, `!=`, `<=`, `==`, `in` mapped to CMate operators
2. **Comma-separated values**: `"debug,info,warning,error"` with operator `in` → `in ['debug', 'info', 'warning', 'error']`
3. **Boolean value**: `true` kept as boolean (not quoted), because this is a JSON config value (not env var)
4. **Empty expected value with `!=`**: `server.host` with empty expected and `!=` → `!= ''` (not-empty check)
5. **Condition parsing**: `env == production` → context variable `env`, value `production`
6. **Namespace**: User specified `cfg`, so all paths are `${cfg::path}`
