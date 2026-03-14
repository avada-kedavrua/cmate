import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cmate import cmate
from cmate._ast import Constant, DictPath, Rule
from cmate.data_source import DataSource, NA
from cmate.util import ParseFormat, Severity


class TestParseConfigs:
    """Tests for _parse_configs function"""

    def test_parse_configs_empty(self):
        """Test parsing empty configs"""
        result = cmate._parse_configs([])
        assert result == {}

    def test_parse_configs_simple(self):
        """Test parsing simple config"""
        result = cmate._parse_configs(["config:/path/to/config"])
        assert "config" in result
        path, pf = result["config"]
        assert path == Path("/path/to/config")
        assert pf == ParseFormat.UNKNOWN

    def test_parse_configs_with_parse_format(self):
        """Test parsing config with parse format"""
        result = cmate._parse_configs(["config:/path/to/config@.json"])
        path, pf = result["config"]
        assert path == Path("/path/to/config")
        assert pf == ParseFormat.JSON

    def test_parse_configs_env(self):
        """Test parsing env config"""
        result = cmate._parse_configs(["env"])
        assert "env" in result
        assert result["env"] == (None, ParseFormat.UNKNOWN)

    def test_parse_configs_multiple(self):
        """Test parsing multiple configs"""
        configs = ["cfg1:/path1", "cfg2:/path2@.yaml"]
        result = cmate._parse_configs(configs)
        assert result["cfg1"] == (Path("/path1"), ParseFormat.UNKNOWN)
        assert result["cfg2"] == (Path("/path2"), ParseFormat.YAML)

    def test_parse_configs_invalid_format(self):
        """Test parsing invalid config format"""
        with pytest.raises(ValueError):
            cmate._parse_configs(["invalid_config"])


class TestParseLines:
    """Tests for _parse_lines function"""

    def test_parse_lines_none(self):
        """Test parsing None returns None"""
        result = cmate._parse_lines(None)
        assert result is None

    def test_parse_lines_empty_string(self):
        """Test parsing empty string returns None"""
        result = cmate._parse_lines("")
        assert result is None

    def test_parse_lines_single(self):
        """Test parsing single line number"""
        result = cmate._parse_lines("10")
        assert result == {10}

    def test_parse_lines_multiple(self):
        """Test parsing multiple line numbers"""
        result = cmate._parse_lines("10,20,30")
        assert result == {10, 20, 30}

    def test_parse_lines_with_spaces(self):
        """Test parsing line numbers with spaces"""
        result = cmate._parse_lines("10 , 20 , 30")
        assert result == {10, 20, 30}

    def test_parse_lines_invalid_skipped(self, caplog):
        """Test parsing invalid line numbers are skipped with warning"""
        import logging

        cmate.logger.setLevel(logging.WARNING)
        result = cmate._parse_lines("10,abc,30")
        assert result == {10, 30}

    def test_parse_lines_all_invalid_returns_none(self, caplog):
        """Test parsing all invalid line numbers returns None"""
        import logging

        cmate.logger.setLevel(logging.WARNING)
        result = cmate._parse_lines("abc,def")
        assert result is None

    def test_parse_lines_duplicates(self):
        """Test parsing duplicate line numbers"""
        result = cmate._parse_lines("10,10,20")
        assert result == {10, 20}


class TestParseContexts:
    """Tests for _parse_contexts function"""

    def test_parse_contexts_empty(self):
        """Test parsing empty contexts"""
        result = cmate._parse_contexts([])
        assert result == {}

    def test_parse_contexts_string(self):
        """Test parsing string context"""
        result = cmate._parse_contexts(["name:value"])
        assert result == {"name": "value"}

    def test_parse_contexts_integer(self):
        """Test parsing integer context"""
        result = cmate._parse_contexts(["count:42"])
        assert result == {"count": 42}

    def test_parse_contexts_negative_number(self):
        """Test parsing negative integer context"""
        result = cmate._parse_contexts(["count:-42"])
        assert result == {"count": -42}

    def test_parse_contexts_string_in_quotes(self):
        """Test parsing quoted string context"""
        result = cmate._parse_contexts(["name:'42'"])
        assert result == {"name": "42"}

    def test_parse_contexts_multiple(self):
        """Test parsing multiple contexts"""
        contexts = ["a:1", "b:'two'", "c:True"]
        result = cmate._parse_contexts(contexts)
        assert result["a"] == 1
        assert result["b"] == "two"
        assert result["c"] is True

    def test_parse_contexts_invalid_format(self):
        """Test parsing invalid context format"""
        with pytest.raises(ValueError):
            cmate._parse_contexts(["invalid"])


class TestDisplayFunctions:
    """Tests for display functions"""

    def test_format_section(self, capsys):
        """Test _print_section function"""
        cmate._print_section("Test Section")
        captured = capsys.readouterr()
        assert "Test Section" in captured.out
        assert "------------" in captured.out

    def test_format_section_with_level(self, capsys):
        """Test _print_section with indentation level"""
        cmate._print_section("Test", level=2)
        captured = capsys.readouterr()
        assert "    Test" in captured.out

    def test_format_field(self, capsys):
        """Test _print_field function"""
        cmate._print_field("key", "value", indent=0)
        captured = capsys.readouterr()
        assert "key : value" in captured.out

    def test_format_field_with_indent(self, capsys):
        """Test _print_field with indentation"""
        cmate._print_field("key", "value", indent=2)
        captured = capsys.readouterr()
        assert "    key : value" in captured.out

    def test_display_json(self, capsys):
        """Test _display_json function"""
        data = {"key": "value", "number": 42}
        cmate._display_json(data)
        captured = capsys.readouterr()
        assert "key" in captured.out
        assert "value" in captured.out


class TestValidateAndLoadTargets:
    """Tests for _load_targets function"""

    def test_validate_and_load_targets_empty(self):
        """Test with empty input targets"""
        ds = DataSource()
        matched = cmate._load_targets({}, {}, ds)
        assert matched == []

    def test_validate_and_load_targets_not_in_all(self, caplog):
        """Test with target not in all_targets"""
        import logging

        cmate.logger.setLevel(logging.WARNING)
        ds = DataSource()
        input_targets = {"missing": (Path("/path"), ParseFormat.UNKNOWN)}
        all_targets = {}
        matched = cmate._load_targets(input_targets, all_targets, ds)
        assert matched == []

    def test_validate_and_load_targets_env(self):
        """Test loading env target"""
        ds = DataSource()
        input_targets = {"env": (None, ParseFormat.UNKNOWN)}
        all_targets = {"env": {}}
        matched = cmate._load_targets(input_targets, all_targets, ds)
        assert "env" in matched


class TestCollectMissingDependencies:
    """Tests for _collect_missing function"""

    def test_no_missing_deps(self):
        """Test with no missing dependencies"""
        matched = ["target1"]
        input_targets = {"target1": (Path("/path"), ParseFormat.UNKNOWN)}
        input_contexts = {}
        all_targets = {"target1": {"required_targets": [], "required_contexts": []}}

        result = cmate._collect_missing(
            matched, input_targets, input_contexts, all_targets
        )
        assert result == {}

    def test_missing_target(self):
        """Test with missing target dependency"""
        matched = ["target1"]
        input_targets = {"target1": (Path("/path"), ParseFormat.UNKNOWN)}
        input_contexts = {}
        all_targets = {
            "target1": {"required_targets": ["target2"], "required_contexts": []}
        }

        result = cmate._collect_missing(
            matched, input_targets, input_contexts, all_targets
        )
        assert "target1" in result
        assert result["target1"]["targets"] == ["target2"]

    def test_missing_context(self):
        """Test with missing context dependency"""
        matched = ["target1"]
        input_targets = {"target1": (Path("/path"), ParseFormat.UNKNOWN)}
        input_contexts = {}
        all_targets = {
            "target1": {"required_targets": [], "required_contexts": ["ctx1"]}
        }

        result = cmate._collect_missing(
            matched, input_targets, input_contexts, all_targets
        )
        assert "target1" in result
        assert result["target1"]["contexts"] == ["ctx1"]


class TestValidateAndLoadContexts:
    """Tests for _load_contexts function"""

    def test_validate_and_load_contexts(self):
        """Test loading contexts"""
        ds = DataSource()
        input_contexts = {"ctx1": "value1", "ctx2": 42}
        all_contexts = {"ctx1": {}, "ctx2": {}}

        cmate._load_contexts(input_contexts, all_contexts, ds)

        assert ds["context::ctx1"] == "value1"
        assert ds["context::ctx2"] == 42

    def test_validate_and_load_contexts_not_in_all(self, caplog):
        """Test loading context not in all_contexts"""
        import logging

        cmate.logger.setLevel(logging.WARNING)
        ds = DataSource()
        input_contexts = {"unknown": "value"}
        all_contexts = {}

        cmate._load_contexts(input_contexts, all_contexts, ds)
        # Should log warning but not raise


class TestFilterRulesByLines:
    """Tests for _filter_rules_by_lines function"""

    def test_filter_empty_ruleset(self):
        """Test filtering empty ruleset"""
        filtered, deselected = cmate._filter_rules_by_lines({}, {10, 20})
        assert filtered == {}
        assert deselected == 0

    def test_filter_single_rule_match(self):
        """Test filtering with single matching rule"""
        const = Constant(10, 1, True)
        rule = Rule(10, 1, const, "test", Severity.ERROR)
        ruleset = {"ns": {rule}}

        filtered, deselected = cmate._filter_rules_by_lines(ruleset, {10})
        assert len(filtered["ns"]) == 1
        assert deselected == 0

    def test_filter_single_rule_no_match(self):
        """Test filtering with no matching rules"""
        const = Constant(10, 1, True)
        rule = Rule(10, 1, const, "test", Severity.ERROR)
        ruleset = {"ns": {rule}}

        filtered, deselected = cmate._filter_rules_by_lines(ruleset, {999})
        assert filtered == {}
        assert deselected == 1

    def test_filter_multiple_rules_partial_match(self):
        """Test filtering with partial match"""
        rule1 = Rule(10, 1, Constant(10, 1, True), "test1", Severity.ERROR)
        rule2 = Rule(20, 1, Constant(20, 1, True), "test2", Severity.ERROR)
        rule3 = Rule(30, 1, Constant(30, 1, True), "test3", Severity.ERROR)
        ruleset = {"ns": {rule1, rule2, rule3}}

        filtered, deselected = cmate._filter_rules_by_lines(ruleset, {10, 30})
        assert len(filtered["ns"]) == 2
        assert deselected == 1

    def test_filter_multiple_namespaces(self):
        """Test filtering with multiple namespaces"""
        rule1 = Rule(10, 1, Constant(10, 1, True), "test1", Severity.ERROR)
        rule2 = Rule(20, 1, Constant(20, 1, True), "test2", Severity.ERROR)
        ruleset = {"ns1": {rule1}, "ns2": {rule2}}

        filtered, deselected = cmate._filter_rules_by_lines(ruleset, {10})
        assert "ns1" in filtered
        assert "ns2" not in filtered
        assert deselected == 1

    def test_filter_removes_empty_namespaces(self):
        """Test filtering removes namespaces with no selected rules"""
        rule1 = Rule(10, 1, Constant(10, 1, True), "test1", Severity.ERROR)
        rule2 = Rule(20, 1, Constant(20, 1, True), "test2", Severity.ERROR)
        ruleset = {"ns1": {rule1}, "ns2": {rule2}}

        filtered, deselected = cmate._filter_rules_by_lines(ruleset, {999})
        assert filtered == {}
        assert deselected == 2


class TestCollectOnly:
    """Tests for _show_collected function"""

    def test_collect_only_empty(self, caplog):
        """Test with empty ruleset"""
        import logging

        cmate.logger.setLevel(logging.INFO)
        result = cmate._show_collected({})
        assert result == 0

    def test_collect_only_with_rules(self, caplog):
        """Test with rules"""
        import logging

        cmate.logger.setLevel(logging.INFO)
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test", Severity.ERROR)
        ruleset = {"ns": {rule}}

        result = cmate._show_collected(ruleset)
        assert result == 0

    def test_collect_only_with_deselected(self, capsys):
        """Test collect only with deselected count"""
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test", Severity.ERROR)
        ruleset = {"ns": {rule}}

        result = cmate._show_collected(ruleset, total=10, deselected=9)
        assert result == 0
        captured = capsys.readouterr()
        assert "10 items" in captured.out
        assert "9 deselected" in captured.out
        assert "1 selected" in captured.out

    def test_collect_only_all_deselected(self, capsys):
        """Test collect only when all items are deselected"""
        result = cmate._show_collected({}, total=10, deselected=10)
        assert result == 0
        captured = capsys.readouterr()
        assert "10 items" in captured.out
        assert "10 deselected" in captured.out
        assert "0 selected" in captured.out


class TestNAEncoder:
    """Tests for _NAEncoder class"""

    def test_encode_na(self):
        """Test encoding NA value"""
        encoder = cmate._NAEncoder()
        result = encoder.default(NA)
        assert result == {"NAType": True}

    def test_encode_regular(self):
        """Test encoding regular value"""
        encoder = cmate._NAEncoder()
        result = encoder.encode("string")
        assert result == '"string"'

    def test_json_dump_with_na(self):
        """Test JSON dump with NA value"""
        data = {"key": NA, "other": "value"}
        result = json.dumps(data, cls=cmate._NAEncoder)
        assert "NAType" in result


class TestParse:
    """Tests for parse function"""

    def test_parse(self, tmp_path):
        """Test parse function"""
        from cmate._ast import Document

        rule_file = tmp_path / "test.cmate"
        rule_file.write_text("[metadata]\nname = 'test'\n---\n")

        result = cmate.parse(str(rule_file))
        assert isinstance(result, Document)


class TestFileExtensionValidation:
    """Tests for .cmate file extension validation"""

    def test_parse_invalid_extension_raises_error(self, tmp_path):
        """Test that non-.cmate files raise RuleSyntaxError"""
        rule_file = tmp_path / "test.json"
        rule_file.write_text("[metadata]\nname = 'test'\n---\n")

        with pytest.raises(cmate.RuleSyntaxError, match="must have .cmate extension"):
            cmate.parse(str(rule_file))

    def test_parse_valid_cmate_extension(self, tmp_path):
        """Test that .cmate files are accepted"""
        from cmate._ast import Document

        rule_file = tmp_path / "test.cmate"
        rule_file.write_text("[metadata]\nname = 'test'\n---\n")

        result = cmate.parse(str(rule_file))
        assert isinstance(result, Document)

    def test_parse_txt_extension_raises_error(self, tmp_path):
        """Test that .txt files raise RuleSyntaxError"""
        rule_file = tmp_path / "rules.txt"
        rule_file.write_text("[metadata]\nname = 'test'\n---\n")

        with pytest.raises(cmate.RuleSyntaxError, match="must have .cmate extension"):
            cmate.parse(str(rule_file))

    def test_parse_no_extension_raises_error(self, tmp_path):
        """Test that files without extension raise RuleSyntaxError"""
        rule_file = tmp_path / "rulefile"
        rule_file.write_text("[metadata]\nname = 'test'\n---\n")

        with pytest.raises(cmate.RuleSyntaxError, match="must have .cmate extension"):
            cmate.parse(str(rule_file))

    def test_inspect_invalid_extension_raises_error(self, tmp_path):
        """Test that inspect rejects non-.cmate files"""
        rule_file = tmp_path / "test.yaml"
        rule_file.write_text("[metadata]\nname = 'test'\n---\n")

        with pytest.raises(cmate.RuleSyntaxError, match="must have .cmate extension"):
            cmate.inspect(str(rule_file), "text")

    def test_run_invalid_extension_raises_error(self, tmp_path):
        """Test that run rejects non-.cmate files"""
        rule_file = tmp_path / "test.json"
        rule_file.write_text("[par test]\nassert true, 'test'\n")

        with pytest.raises(cmate.RuleSyntaxError, match="must have .cmate extension"):
            cmate.run(str(rule_file))


class TestInspect:
    """Tests for inspect function"""

    def test_inspect_text(self, capsys, tmp_path):
        """Test inspect with text format"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[metadata]\nname = 'test'\n---")

        cmate.inspect(str(rule_file), "text")
        captured = capsys.readouterr()  # noqa: F841
        # Should output something

    def test_inspect_json(self, capsys, tmp_path):
        """Test inspect with json format"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[metadata]\nname = 'test'\n---")

        cmate.inspect(str(rule_file), "json")
        captured = capsys.readouterr()
        assert "metadata" in captured.out

    def test_inspect_invalid_format(self, tmp_path):
        """Test inspect with invalid format"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text("[metadata]\nname = 'test'\n---")

        with pytest.raises(ValueError, match="Unsupported output format"):
            cmate.inspect(str(rule_file), "invalid")


class TestRun:
    """Tests for run function"""

    def test_run(self, tmp_path):
        """Test run function"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test'\n"
        )
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        result = cmate.run(str(rule_file), configs=[f"test:{config_file}"])
        assert isinstance(result, int)

    def test_run_validation_fails(self, tmp_path):
        """Test run when validation fails"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test'\n"
        )
        with pytest.raises(cmate.ValidationError):
            cmate.run(str(rule_file), configs=[])

    def test_run_collect_only(self, tmp_path, capsys):
        """Test run with collect_only flag"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test'\n"
        )
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        result = cmate.run(
            str(rule_file),
            configs=[f"test:{config_file}"],
            collect_only=True,
        )
        assert result == 0

    def test_run_with_lines_filter(self, tmp_path):
        """Test run with -k lines filter"""
        rule_file = tmp_path / "rule.cmate"
        # Line numbers: line 1 is header, line 2 is separator, line 3 is [par test], line 4 is assert
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test'\n"
        )
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        result = cmate.run(
            str(rule_file),
            configs=[f"test:{config_file}"],
            lines="5",  # Line 5 is the assert line
        )
        assert isinstance(result, int)

    def test_run_with_lines_filter_nonexistent(self, tmp_path, capsys):
        """Test run with -k filter for non-existent line"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test'\n"
        )
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        result = cmate.run(
            str(rule_file),
            configs=[f"test:{config_file}"],
            lines="999",  # Non-existent line
        )
        # Should return 0 when all rules are deselected
        assert result == 0

    def test_run_collect_only_with_lines_filter(self, tmp_path, capsys):
        """Test run with collect_only and lines filter"""
        rule_file = tmp_path / "rule.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test1'\nassert false, 'test2'\n"
        )
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        result = cmate.run(
            str(rule_file),
            configs=[f"test:{config_file}"],
            collect_only=True,
            lines="5",  # Only select first assert
        )
        assert result == 0
        captured = capsys.readouterr()
        assert "deselected" in captured.out


class TestMain:
    """Tests for main function"""

    def test_main_help(self):
        """Test main with help flag"""
        with patch.object(sys, "argv", ["cmate", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                cmate.main()
            assert exc_info.value.code == 0


class TestDisplayText:
    """Tests for display text functions"""

    def test_display_text_overview(self, capsys):
        """Test _display_text with overview data"""
        info = {
            "metadata": {"name": "test", "version": "1.0"},
            "targets": {},
            "contexts": {},
        }
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "Overview" in captured.out
        assert "name" in captured.out

    def test_display_text_overview_empty(self, capsys):
        """Test _display_text with empty overview"""
        info = {"metadata": {}, "targets": {}, "contexts": {}}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "No overview available" in captured.out

    def test_display_text_contexts(self, capsys):
        """Test _display_text with contexts"""
        contexts = {
            "mode": {"desc": ("Deployment mode", None), "options": ["dev", "prod"]}
        }
        info = {"metadata": {}, "targets": {}, "contexts": contexts}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "Context Variables" in captured.out
        assert "mode" in captured.out

    def test_display_text_contexts_empty(self, capsys):
        """Test _display_text with empty contexts"""
        info = {"metadata": {}, "targets": {}, "contexts": {}}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "No contexts available" in captured.out

    def test_display_text_contexts_tuple_desc(self, capsys):
        """Test _display_text with tuple description"""
        contexts = {"mode": {"desc": ("Description text",), "options": ["a", "b"]}}
        info = {"metadata": {}, "targets": {}, "contexts": contexts}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "Description text" in captured.out

    def test_display_text_targets(self, capsys):
        """Test _display_text with targets"""
        targets = {
            "config": {
                "desc": "Configuration file",
                "parse_format": "json",
                "required_targets": ["base"],
                "required_contexts": ["env"],
            }
        }
        info = {"metadata": {}, "targets": targets, "contexts": {}}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "Config Targets" in captured.out
        assert "config" in captured.out

    def test_display_text_targets_env(self, capsys):
        """Test _display_text with env target"""
        targets = {
            "env": {
                "desc": None,
                "parse_format": None,
                "required_targets": None,
                "required_contexts": None,
            }
        }
        info = {"metadata": {}, "targets": targets, "contexts": {}}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "Environment variable validation" in captured.out

    def test_display_text_targets_empty(self, capsys):
        """Test _display_text with empty targets"""
        info = {"metadata": {}, "targets": {}, "contexts": {}}
        cmate._display_text(info)
        captured = capsys.readouterr()
        assert "No config targets available" in captured.out

    def test_display_text_missing_attr(self):
        """Test _display_text with missing attributes"""
        info = {"metadata": {}}  # Missing targets and contexts
        with pytest.raises(KeyError):
            cmate._display_text(info)


class TestValidateAndLoadDependencies:
    """Tests for _load_dependencies"""

    def test_validate_no_matched_targets(self):
        """Test when no targets match"""
        info = {
            "targets": {"target1": {}},
            "contexts": {},
            "metadata": {},
        }
        with pytest.raises(cmate.ValidationError):
            cmate._load_dependencies(info, {}, {})

    def test_validate_with_missing_deps(self, tmp_path):
        """Test with missing dependencies"""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        info = {
            "targets": {
                "target1": {
                    "required_targets": ["missing"],
                    "required_contexts": [],
                    "parse_format": None,
                }
            },
            "contexts": {},
            "metadata": {},
        }
        with pytest.raises(cmate.ValidationError):
            cmate._load_dependencies(
                info, {"target1": (config_file, ParseFormat.JSON)}, {}
            )


class TestLogMissingError:
    """Tests for _format_missing"""

    def test_log_missing_error(self):
        """Test _format_missing function"""
        missing_deps = {"target1": {"targets": ["dep1"], "contexts": ["ctx1"]}}
        all_targets = {"dep1": {"desc": "Dependency 1"}}
        all_contexts = {"ctx1": {"desc": ("Context 1", None), "options": ["a"]}}

        result = cmate._format_missing(missing_deps, all_targets, all_contexts)
        assert isinstance(result, str)
        assert "dep1" in result


class TestValidateAndLoadTargetsExtended:
    """Extended tests for _load_targets"""

    def test_load_target_file_not_found(self):
        """Test loading target with file not found"""
        ds = DataSource()
        input_targets = {
            "config": (Path("/nonexistent/path.json"), ParseFormat.UNKNOWN)
        }
        all_targets = {"config": {"parse_format": None}}

        with pytest.raises(cmate.ConfigError):
            cmate._load_targets(input_targets, all_targets, ds)

    def test_load_target_unsupported_type(self, tmp_path):
        """Test loading target with unsupported parse type"""
        txt_file = tmp_path / "config.txt"
        txt_file.write_text("content")

        ds = DataSource()
        input_targets = {"config": (txt_file, ParseFormat.UNKNOWN)}
        all_targets = {"config": {"parse_format": None}}

        with pytest.raises(cmate.ConfigError):
            cmate._load_targets(input_targets, all_targets, ds)

    def test_load_target_parse_error(self, tmp_path):
        """Test loading target with parse error"""
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json")

        ds = DataSource()
        input_targets = {"config": (bad_json, ParseFormat.UNKNOWN)}
        all_targets = {"config": {"parse_format": None}}

        with pytest.raises(Exception):  # noqa: B017
            cmate._load_targets(input_targets, all_targets, ds)


class TestRunExtended:
    """Extended tests for run function"""

    def test_run_with_undefined_namespace(self, tmp_path):
        """Test run with reference to undefined namespace raises ValidationError"""
        rule_file = tmp_path / "test.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n"
            "[par test]\nassert ${undefined::key} == 1, 'test'\n"
        )

        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        with pytest.raises(cmate.ValidationError):
            cmate.run(str(rule_file), configs=[f"test:{config_file}"])

    def test_run_with_output_path(self, tmp_path):
        """Test run with output path"""
        rule_file = tmp_path / "test.cmate"
        rule_file.write_text(
            "[targets]\ntest: 'Test config'\n---\n[par test]\nassert true, 'test'\n"
        )

        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = cmate.run(
            str(rule_file),
            configs=[f"test:{config_file}"],
            output_path=output_dir,
        )
        # Should complete without error
        assert isinstance(result, int)


class TestActualRun:
    """Tests for _execute function"""

    def test_actual_run_success(self):
        """Test _execute with successful tests"""
        ds = DataSource()
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test message", Severity.ERROR)
        ruleset = {"test": {rule}}

        result = cmate._execute(
            ruleset, ds, failfast=False, verbosity=False, output_path=None
        )
        assert result == 0

    def test_actual_run_failure(self):
        """Test _execute with failing tests"""
        from cmate._ast import Compare

        ds = DataSource()
        # Use a comparison that will evaluate to False
        compare = Compare(
            1, 1, DictPath(1, 1, "test::key"), ["=="], [Constant(1, 10, "expected")]
        )
        rule = Rule(1, 1, compare, "test message", Severity.ERROR)
        ruleset = {"test": {rule}}

        result = cmate._execute(
            ruleset, ds, failfast=False, verbosity=False, output_path=None
        )
        assert result == 1


class TestRunExtendedMore:
    """More extended tests for run function"""

    @patch("cmate.cmate.parse")
    @patch("cmate.cmate.InfoCollector")
    @patch("cmate.cmate._load_dependencies")
    @patch("cmate.cmate.AssignmentProcessor")
    @patch("cmate.cmate.RuleCollector")
    def test_run_keyerror_in_collect(
        self,
        mock_rule_collector,
        mock_assignment_processor,
        mock_validate,
        mock_info_collector,
        mock_parse,
    ):
        """Test run when KeyError is raised during rule collection"""
        mock_info_collector.return_value.collect.return_value = {
            "targets": {},
            "contexts": {},
        }
        mock_validate.return_value = DataSource()

        mock_collector = mock_rule_collector.return_value
        mock_collector.collect.side_effect = KeyError("test_key")

        with pytest.raises(cmate.RuleCollectionError):
            cmate.run("/path/to/rule.cmate")


class TestValidateAndLoadTargetsMore:
    """Extended tests for _load_targets"""

    @patch("cmate.cmate.load_from_file")
    def test_validate_and_load_targets_oserror(self, mock_load):
        """Test _load_targets with OSError"""
        mock_load.side_effect = OSError("File not found")

        input_targets = {"config": (Path("/path/to/config.json"), ParseFormat.UNKNOWN)}
        all_targets = {"config": {"parse_format": None}}
        ds = DataSource()

        with pytest.raises(cmate.ConfigError):
            cmate._load_targets(input_targets, all_targets, ds)

    @patch("cmate.cmate.load_from_file")
    def test_validate_and_load_targets_typeerror(self, mock_load):
        """Test _load_targets with TypeError"""
        mock_load.side_effect = TypeError("Invalid type")

        input_targets = {"config": (Path("/path/to/config.json"), ParseFormat.UNKNOWN)}
        all_targets = {"config": {"parse_format": None}}
        ds = DataSource()

        with pytest.raises(TypeError):
            cmate._load_targets(input_targets, all_targets, ds)

    @patch("cmate.cmate.load_from_file")
    def test_validate_and_load_targets_generic_exception(self, mock_load):
        """Test _load_targets with generic Exception"""
        mock_load.side_effect = Exception("Generic error")

        input_targets = {"config": (Path("/path/to/config.json"), ParseFormat.UNKNOWN)}
        all_targets = {"config": {"parse_format": None}}
        ds = DataSource()

        with pytest.raises(Exception):  # noqa: B017
            cmate._load_targets(input_targets, all_targets, ds)
