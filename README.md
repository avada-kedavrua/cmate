# cmate

CMate — rule validator and test runner

Quick usage

# CLI (recommended for command-line use)

```bash
# show help
cmate --help

# inspect rule requirements (text)
cmate inspect presets/mindie.cmate

# inspect rule requirements (json)
cmate inspect presets/mindie.cmate --format json

# run rules (dry-run) providing required config and contexts
# Use colon-delimited `name:path` syntax (preferred). You may also append `@json` to force parse type.
cmate run presets/mindie.cmate --dry-run \
  --configs mies_config:/path/to/mies_config.json@json \
  --contexts deploy_mode:pd_mix model_type:deepseek npu_type:A2
```

- Library (importable API)

```python
import cmate

# version
print(cmate.__version__)

# inspect
info = cmate.inspect('presets/mindie.cmate')

# run (dry run) — pass parsed-friendly dicts
result = cmate.run(
    'presets/mindie.cmate',
    configs={'mies_config': '/path/to/mies_config.json'},
    contexts={'deploy_mode': 'pd_mix', 'model_type': 'deepseek', 'npu_type': 'A2'},
    dry_run=True,
)
```

Notes
- The console script `cmate` is provided by `pyproject.toml` entry `cmate = "cmate.cmate:main"`.
- Library functions return plain JSON-serializable data (dicts/lists/primitives).
- If you see a "Unsupported parse type" error, ensure your config file has a `.json`, `.yaml` or `.yml` extension or point `--configs` to a supported file format.