import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cmate import cmate
from cmate.data_source import NA, DataSource
from cmate.parser import Parser
from cmate.visitor import EnvScriptGenerator


@pytest.fixture(scope="session")
def parser():
    return Parser()


# ---------------------------------------------------------------------------
# EnvScriptGenerator – unit tests
# ---------------------------------------------------------------------------


class TestEnvScriptGeneratorBasic:
    """Basic env script generation from [par env] rules."""

    def test_simple_eq_rule(self, parser):
        text = """\
[par env]
assert ${MY_VAR} == 'hello', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert 'export MY_VAR="hello"' in script
        assert gen._set_count == 1
        assert gen._unset_count == 0

    def test_multiple_eq_rules(self, parser):
        text = """\
[par env]
assert ${A} == 'a1', 'msg', info
assert ${B} == 'b2', 'msg', error
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert 'export A="a1"' in script
        assert 'export B="b2"' in script
        assert gen._set_count == 2

    def test_in_operator_uses_first_element(self, parser):
        text = """\
[par env]
assert ${MY_VAR} in ['opt1', 'opt2'], 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert 'export MY_VAR="opt1"' in script

    def test_in_operator_empty_list_skipped(self, parser):
        text = """\
[par env]
assert ${MY_VAR} in [], 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0
        assert gen._unset_count == 0

    def test_non_env_partition_ignored(self, parser):
        text = """\
[targets]
cfg: 'config' @ 'json'
---
[par cfg]
assert ${cfg::port} == '80', 'msg', error
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0
        assert gen._unset_count == 0

    def test_non_compare_rule_ignored(self, parser):
        text = """\
[par env]
assert true, 'always passes', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0

    def test_unsupported_op_ignored(self, parser):
        text = """\
[par env]
assert ${MY_VAR} > 'abc', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0

    def test_context_lhs_ignored(self, parser):
        """DictPath with namespace=='context' on LHS should be skipped."""
        text = """\
[contexts]
mode: 'deploy mode'
---
[par env]
assert ${context::mode} == 'dev', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        ds["context::mode"] = "dev"
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0


class TestEnvScriptGeneratorEdgeCases:
    """Edge-case value handling."""

    def test_na_value_unsets(self, parser):
        text = """\
[par env]
assert ${MY_VAR} == NA, 'should be unset', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert "unset MY_VAR" in script
        assert gen._unset_count == 1

    def test_none_value_unsets_with_warning(self, parser, caplog):
        text = """\
[par env]
assert ${MY_VAR} == None, 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        with caplog.at_level(logging.WARNING, logger="cmate.visitor"):
            gen.collect(node)

        assert "unset MY_VAR" in gen.render()
        assert gen._unset_count == 1

    def test_non_str_value_skipped(self, parser, caplog):
        text = """\
[par env]
assert ${MY_VAR} == 42, 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        with caplog.at_level(logging.WARNING, logger="cmate.visitor"):
            gen.collect(node)

        assert gen._set_count == 0
        assert gen._unset_count == 0

    def test_unsafe_value_skipped(self, parser, caplog):
        text = """\
[par env]
assert ${MY_VAR} == 'hello world', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        with caplog.at_level(logging.WARNING, logger="cmate.visitor"):
            gen.collect(node)

        assert gen._set_count == 0

    def test_invalid_env_name_skipped(self, parser, caplog):
        text = """\
[par env]
assert ${env::123BAD} == 'val', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        with caplog.at_level(logging.WARNING, logger="cmate.visitor"):
            gen.collect(node)

        assert gen._set_count == 0

    def test_safe_value_with_special_chars(self, parser):
        """Values with /, :, ., = should pass the safe-value regex."""
        text = """\
[par env]
assert ${MY_PATH} == '/usr/local/bin', 'msg', info
assert ${MY_CONF} == 'expandable_segments:True', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 2
        assert 'export MY_PATH="/usr/local/bin"' in gen.render()
        assert 'export MY_CONF="expandable_segments:True"' in gen.render()


class TestEnvScriptGeneratorUndo:
    """Undo (revert) script generation."""

    def test_undo_unsets_when_not_in_env(self, parser):
        with patch.dict(os.environ, {}, clear=True):
            text = """\
[par env]
assert ${BRAND_NEW} == 'val', 'msg', info
"""
            node = parser.parse(text)
            ds = DataSource()
            gen = EnvScriptGenerator(ds)
            gen.collect(node)
            script = gen.render()

        assert "unset BRAND_NEW" in script

    def test_undo_restores_original(self, parser):
        with patch.dict(os.environ, {"EXISTING": "old_val"}, clear=True):
            text = """\
[par env]
assert ${EXISTING} == 'new_val', 'msg', info
"""
            node = parser.parse(text)
            ds = DataSource()
            gen = EnvScriptGenerator(ds)
            gen.collect(node)
            script = gen.render()

        assert 'export EXISTING="new_val"' in script
        assert 'export EXISTING="old_val"' in script


class TestEnvScriptGeneratorControlFlow:
    """Conditional / loop evaluation in [par env]."""

    def test_if_true_branch(self, parser):
        text = """\
[contexts]
mode: 'mode'
---
[par env]
if ${context::mode} == 'prod':
    assert ${SSL} == 'true', 'ssl needed', error
fi
"""
        node = parser.parse(text)
        ds = DataSource()
        ds["context::mode"] = "prod"
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert 'export SSL="true"' in gen.render()

    def test_if_false_branch(self, parser):
        text = """\
[contexts]
mode: 'mode'
---
[par env]
if ${context::mode} == 'prod':
    assert ${SSL} == 'true', 'ssl needed', error
fi
"""
        node = parser.parse(text)
        ds = DataSource()
        ds["context::mode"] = "dev"
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0

    def test_if_elif_else(self, parser):
        text = """\
[contexts]
mode: 'mode'
---
[par env]
if ${context::mode} == 'a':
    assert ${VAR} == 'val_a', 'msg', info
elif ${context::mode} == 'b':
    assert ${VAR} == 'val_b', 'msg', info
else:
    assert ${VAR} == 'val_default', 'msg', info
fi
"""
        node = parser.parse(text)
        ds = DataSource()
        ds["context::mode"] = "b"
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert 'export VAR="val_b"' in gen.render()


class TestEnvScriptGeneratorRender:
    """render() and write() output correctness."""

    def test_render_empty_uses_noop(self, parser):
        text = "[metadata]\nname = 'empty'\n---\n"
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert "#!/bin/bash" in script
        assert "    :" in script

    def test_render_custom_filename(self, parser):
        text = """\
[par env]
assert ${X} == 'y', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render(filename="custom.sh")

        assert "source custom.sh" in script

    def test_write_creates_file(self, parser, tmp_path):
        text = """\
[par env]
assert ${X} == 'y', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        out = tmp_path / "set_env.sh"
        gen.write(out)

        assert out.exists()
        content = out.read_text()
        assert 'export X="y"' in content
        assert "source set_env.sh" in content

    def test_script_has_revert_section(self, parser):
        text = """\
[par env]
assert ${VAR} == 'val', 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert 'if [ "$1" = "0" ]; then' in script

    def test_render_counts(self, parser):
        text = """\
[par env]
assert ${A} == 'x', 'msg', info
assert ${B} == NA, 'msg', info
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)
        script = gen.render()

        assert "1 exported" in script
        assert "1 unset" in script


class TestEnvScriptGeneratorAlert:
    """Alert nodes should be silently skipped."""

    def test_alert_ignored(self, parser):
        text = """\
[par env]
alert ${MY_VAR}, 'check this', warning
"""
        node = parser.parse(text)
        ds = DataSource()
        gen = EnvScriptGenerator(ds)
        gen.collect(node)

        assert gen._set_count == 0
        assert gen._unset_count == 0


# ---------------------------------------------------------------------------
# Integration – run() with env_script_path
# ---------------------------------------------------------------------------


class TestRunEnvScript:
    """run() integration: env script generation."""

    def test_run_generates_env_script(self, tmp_path):
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[par env]\nassert ${MY_VAR} == 'abc', 'msg', info\n")

        env_out = tmp_path / "set_env.sh"
        cmate.run(
            str(rule_file),
            configs=["env"],
            env_script_path=env_out,
        )

        assert env_out.exists()
        assert 'export MY_VAR="abc"' in env_out.read_text()

    def test_run_no_env_partition_no_script(self, tmp_path):
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text(
            "[targets]\ncfg: 'c' @ 'json'\n---\n[par cfg]\nassert true, 'ok'\n"
        )
        cfg = tmp_path / "c.json"
        cfg.write_text('{"k": 1}')
        env_out = tmp_path / "set_env.sh"
        cmate.run(
            str(rule_file),
            configs=[f"cfg:{cfg}"],
            env_script_path=env_out,
        )

        assert not env_out.exists()

    def test_run_env_script_disabled(self, tmp_path):
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[par env]\nassert ${X} == 'y', 'msg', info\n")

        env_out = tmp_path / "set_env.sh"
        cmate.run(
            str(rule_file),
            configs=["env"],
            env_script_path=None,
        )

        assert not env_out.exists()

    def test_run_env_script_custom_path(self, tmp_path):
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[par env]\nassert ${VAR} == 'val', 'msg', info\n")

        custom = tmp_path / "custom_env.sh"
        cmate.run(
            str(rule_file),
            configs=["env"],
            env_script_path=custom,
        )

        assert custom.exists()
        content = custom.read_text()
        assert 'export VAR="val"' in content
        assert "source custom_env.sh" in content


# ---------------------------------------------------------------------------
# CLI – --env-script / --no-env-script
# ---------------------------------------------------------------------------


class TestCLIEnvScript:
    """CLI flag handling for env script."""

    def test_cli_default_generates_script(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[par env]\nassert ${V} == 'x', 'msg', info\n")

        cmate.main(["run", str(rule_file), "-c", "env"])

        assert (tmp_path / "set_env.sh").exists()

    def test_cli_no_env_script_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[par env]\nassert ${V} == 'x', 'msg', info\n")

        cmate.main(["run", str(rule_file), "-c", "env", "--no-env-script"])

        assert not (tmp_path / "set_env.sh").exists()

    def test_cli_custom_env_script_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[par env]\nassert ${V} == 'x', 'msg', info\n")
        custom = tmp_path / "my_env.sh"

        cmate.main(["run", str(rule_file), "-c", "env", "--env-script", str(custom)])

        assert custom.exists()
