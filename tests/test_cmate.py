import json
import os
import sys
from io import StringIO
from unittest.mock import MagicMock, mock_open, patch

import pytest

from cmate import cmate
from cmate._ast import Constant, DictPath, Rule
from cmate.data_source import NA, DataSource
from cmate.util import Severity


class TestParseConfigs:
    """Tests for _parse_configs function"""

    def test_parse_configs_empty(self):
        """Test parsing empty configs"""
        ret, result = cmate._parse_configs([])
        assert ret is True
        assert result == {}

    def test_parse_configs_simple(self):
        """Test parsing simple config"""
        ret, result = cmate._parse_configs(["config:/path/to/config"])
        assert ret is True
        assert result == {"config": ("/path/to/config", None)}

    def test_parse_configs_with_parse_type(self):
        """Test parsing config with parse type"""
        ret, result = cmate._parse_configs(["config:/path/to/config@json"])
        assert ret is True
        assert result == {"config": ("/path/to/config", "json")}

    def test_parse_configs_env(self):
        """Test parsing env config"""
        ret, result = cmate._parse_configs(["env"])
        assert ret is True
        assert result == {"env": (None, None)}

    def test_parse_configs_multiple(self):
        """Test parsing multiple configs"""
        configs = ["cfg1:/path1", "cfg2:/path2@yaml"]
        ret, result = cmate._parse_configs(configs)
        assert ret is True
        assert result["cfg1"] == ("/path1", None)
        assert result["cfg2"] == ("/path2", "yaml")

    def test_parse_configs_invalid_format(self, caplog):
        """Test parsing invalid config format"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        ret, result = cmate._parse_configs(["invalid_config"])
        assert ret is False


class TestParseContexts:
    """Tests for _parse_contexts function"""

    def test_parse_contexts_empty(self):
        """Test parsing empty contexts"""
        ret, result = cmate._parse_contexts([])
        assert ret is True
        assert result == {}

    def test_parse_contexts_string(self):
        """Test parsing string context"""
        ret, result = cmate._parse_contexts(["name:value"])
        assert ret is True
        assert result == {"name": "value"}

    def test_parse_contexts_integer(self):
        """Test parsing integer context"""
        ret, result = cmate._parse_contexts(["count:42"])
        assert ret is True
        assert result == {"count": 42}

    def test_parse_contexts_negative_number(self):
        """Test parsing negative integer context"""
        ret, result = cmate._parse_contexts(["count:-42"])
        assert ret is True
        assert result == {"count": -42}

    def test_parse_contexts_string_in_quotes(self):
        """Test parsing quoted string context"""
        ret, result = cmate._parse_contexts(["name:'42'"])
        assert ret is True
        assert result == {"name": "42"}

    def test_parse_contexts_multiple(self):
        """Test parsing multiple contexts"""
        contexts = ["a:1", "b:'two'", "c:True"]
        ret, result = cmate._parse_contexts(contexts)
        assert ret is True
        assert result["a"] == 1
        assert result["b"] == "two"
        assert result["c"] is True

    def test_parse_contexts_invalid_format(self, caplog):
        """Test parsing invalid context format"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        ret, result = cmate._parse_contexts(["invalid"])
        assert ret is False


class TestDisplayFunctions:
    """Tests for display functions"""

    def test_format_section(self, capsys):
        """Test _format_section function"""
        cmate._format_section("Test Section")
        captured = capsys.readouterr()
        assert "Test Section" in captured.out
        assert "------------" in captured.out

    def test_format_section_with_level(self, capsys):
        """Test _format_section with indentation level"""
        cmate._format_section("Test", level=2)
        captured = capsys.readouterr()
        assert "    Test" in captured.out

    def test_format_field(self, capsys):
        """Test _format_field function"""
        cmate._format_field("key", "value", indent=0)
        captured = capsys.readouterr()
        assert "key : value" in captured.out

    def test_format_field_with_indent(self, capsys):
        """Test _format_field with indentation"""
        cmate._format_field("key", "value", indent=2)
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
    """Tests for _validate_and_load_targets function"""

    def test_validate_and_load_targets_empty(self):
        """Test with empty input targets"""
        ds = DataSource()
        ret, matched = cmate._validate_and_load_targets({}, {}, ds)
        assert ret is True
        assert matched == []

    def test_validate_and_load_targets_not_in_all(self, caplog):
        """Test with target not in all_targets"""
        import logging

        cmate.logger.setLevel(logging.WARNING)
        ds = DataSource()
        input_targets = {"missing": ("/path", None)}
        all_targets = {}
        ret, matched = cmate._validate_and_load_targets(input_targets, all_targets, ds)
        assert ret is True
        assert matched == []

    def test_validate_and_load_targets_env(self):
        """Test loading env target"""
        ds = DataSource()
        input_targets = {"env": (None, None)}
        all_targets = {"env": {}}
        ret, matched = cmate._validate_and_load_targets(input_targets, all_targets, ds)
        assert ret is True
        assert "env" in matched


class TestCollectMissingDependencies:
    """Tests for _collect_missing_dependencies function"""

    def test_no_missing_deps(self):
        """Test with no missing dependencies"""
        matched = ["target1"]
        input_targets = {"target1": ("/path", None)}
        input_contexts = {}
        all_targets = {"target1": {"required_targets": [], "required_contexts": []}}

        result = cmate._collect_missing_dependencies(
            matched, input_targets, input_contexts, all_targets
        )
        assert result == {}

    def test_missing_target(self):
        """Test with missing target dependency"""
        matched = ["target1"]
        input_targets = {"target1": ("/path", None)}
        input_contexts = {}
        all_targets = {
            "target1": {"required_targets": ["target2"], "required_contexts": []}
        }

        result = cmate._collect_missing_dependencies(
            matched, input_targets, input_contexts, all_targets
        )
        assert "target1" in result
        assert result["target1"]["targets"] == ["target2"]

    def test_missing_context(self):
        """Test with missing context dependency"""
        matched = ["target1"]
        input_targets = {"target1": ("/path", None)}
        input_contexts = {}
        all_targets = {
            "target1": {"required_targets": [], "required_contexts": ["ctx1"]}
        }

        result = cmate._collect_missing_dependencies(
            matched, input_targets, input_contexts, all_targets
        )
        assert "target1" in result
        assert result["target1"]["contexts"] == ["ctx1"]


class TestValidateAndLoadContexts:
    """Tests for _validate_and_load_contexts function"""

    def test_validate_and_load_contexts(self):
        """Test loading contexts"""
        ds = DataSource()
        input_contexts = {"ctx1": "value1", "ctx2": 42}
        all_contexts = {"ctx1": {}, "ctx2": {}}

        cmate._validate_and_load_contexts(input_contexts, all_contexts, ds)

        assert ds["context::ctx1"] == "value1"
        assert ds["context::ctx2"] == 42

    def test_validate_and_load_contexts_not_in_all(self, caplog):
        """Test loading context not in all_contexts"""
        import logging

        cmate.logger.setLevel(logging.WARNING)
        ds = DataSource()
        input_contexts = {"unknown": "value"}
        all_contexts = {}

        cmate._validate_and_load_contexts(input_contexts, all_contexts, ds)
        # Should log warning but not raise


class TestCollectOnly:
    """Tests for _collect_only function"""

    def test_collect_only_empty(self, caplog):
        """Test with empty ruleset"""
        import logging

        cmate.logger.setLevel(logging.INFO)
        result = cmate._collect_only({})
        assert result == 0

    def test_collect_only_with_rules(self, caplog):
        """Test with rules"""
        import logging

        cmate.logger.setLevel(logging.INFO)
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test", Severity.ERROR)
        ruleset = {"ns": {rule}}

        result = cmate._collect_only(ruleset)
        assert result == 0


class TestNAEncoder:
    """Tests for NAEncoder class"""

    def test_encode_na(self):
        """Test encoding NA value"""
        encoder = cmate.NAEncoder()
        result = encoder.default(NA)
        assert result == {"NAType": True}

    def test_encode_regular(self):
        """Test encoding regular value"""
        encoder = cmate.NAEncoder()
        result = encoder.encode("string")
        assert result == '"string"'

    def test_json_dump_with_na(self):
        """Test JSON dump with NA value"""
        data = {"key": NA, "other": "value"}
        result = json.dumps(data, cls=cmate.NAEncoder)
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


class TestInspect:
    """Tests for inspect function"""

    @patch("cmate.cmate.open_s", mock_open(read_data="[metadata]\nname = 'test'\n---"))
    def test_inspect_text(self, capsys):
        """Test inspect with text format"""
        cmate.inspect("/path/to/rule.cmate", "text")
        captured = capsys.readouterr()
        # Should output something

    @patch("cmate.cmate.open_s", mock_open(read_data="[metadata]\nname = 'test'\n---"))
    def test_inspect_json(self, capsys):
        """Test inspect with json format"""
        cmate.inspect("/path/to/rule.cmate", "json")
        captured = capsys.readouterr()
        assert "metadata" in captured.out

    @patch("cmate.cmate.open_s", mock_open(read_data="[metadata]\nname = 'test'\n---"))
    def test_inspect_invalid_format(self):
        """Test inspect with invalid format"""
        with pytest.raises(ValueError, match="Unsupported output format"):
            cmate.inspect("/path/to/rule.cmate", "invalid")


class TestRun:
    """Tests for run function"""

    @patch("cmate.cmate.open_s", mock_open(read_data="[par test]\nassert true, 'test'\n"))
    @patch("cmate.cmate._validate_and_load_dependencies")
    def test_run(self, mock_validate):
        """Test run function"""
        mock_validate.return_value = (True, DataSource())
        result = cmate.run("/path/to/rule.cmate", configs={"test": ("/path", "json")})
        # Function should complete without error
        assert isinstance(result, int)

    @patch("cmate.cmate.open_s", mock_open(read_data="[par test]\nassert true, 'test'\n"))
    def test_run_validation_fails(self):
        """Test run when validation fails"""
        result = cmate.run("/path/to/rule.cmate", configs={})
        assert result == 1

    @patch("cmate.cmate.open_s", mock_open(read_data="[par test]\nassert true, 'test'\n"))
    @patch("cmate.cmate._validate_and_load_dependencies")
    def test_run_collect_only(self, mock_validate, capsys):
        """Test run with collect_only flag"""
        mock_validate.return_value = (True, DataSource())
        result = cmate.run("/path/to/rule.cmate", configs={"test": ("/path", "json")}, collect_only=True)
        assert result == 0


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
        """Test _display_text_overview with data"""
        metadata = {"name": "test", "version": "1.0"}
        cmate._display_text_overview(metadata)
        captured = capsys.readouterr()
        assert "Overview" in captured.out
        assert "name" in captured.out

    def test_display_text_overview_empty(self, capsys):
        """Test _display_text_overview with empty data"""
        cmate._display_text_overview({})
        captured = capsys.readouterr()
        assert "No overview available" in captured.out

    def test_display_text_contexts(self, capsys):
        """Test _display_text_contexts"""
        contexts = {
            "mode": {"desc": ("Deployment mode", None), "options": ["dev", "prod"]}
        }
        cmate._display_text_contexts(contexts)
        captured = capsys.readouterr()
        assert "Context Variables" in captured.out
        assert "mode" in captured.out

    def test_display_text_contexts_empty(self, capsys):
        """Test _display_text_contexts with empty data"""
        cmate._display_text_contexts({})
        captured = capsys.readouterr()
        assert "No contexts available" in captured.out

    def test_display_text_contexts_tuple_desc(self, capsys):
        """Test _display_text_contexts with tuple description"""
        contexts = {
            "mode": {"desc": ("Description text",), "options": ["a", "b"]}
        }
        cmate._display_text_contexts(contexts)
        captured = capsys.readouterr()
        assert "Description text" in captured.out

    def test_display_text_targets(self, capsys):
        """Test _display_text_targets"""
        targets = {
            "config": {
                "desc": "Configuration file",
                "parse_type": "json",
                "required_targets": ["base"],
                "required_contexts": ["env"],
            }
        }
        cmate._display_text_targets(targets)
        captured = capsys.readouterr()
        assert "Config Targets" in captured.out
        assert "config" in captured.out

    def test_display_text_targets_env(self, capsys):
        """Test _display_text_targets with env target"""
        targets = {
            "env": {
                "desc": None,
                "parse_type": None,
                "required_targets": None,
                "required_contexts": None,
            }
        }
        cmate._display_text_targets(targets)
        captured = capsys.readouterr()
        assert "Environment variables validation" in captured.out

    def test_display_text_targets_empty(self, capsys):
        """Test _display_text_targets with empty data"""
        cmate._display_text_targets({})
        captured = capsys.readouterr()
        assert "No config targets available" in captured.out

    def test_display_text_missing_attr(self, caplog):
        """Test _display_text with missing attributes"""
        import logging

        cmate.logger.setLevel(logging.CRITICAL)
        info = {"metadata": {}}  # Missing targets and contexts
        cmate._display_text(info)
        # Should log critical error


class TestValidateAndLoadDependencies:
    """Tests for _validate_and_load_dependencies"""

    def test_validate_no_matched_targets(self, caplog):
        """Test when no targets match"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        info = {
            "targets": {"target1": {}},
            "contexts": {},
            "metadata": {},
        }
        ret, ds = cmate._validate_and_load_dependencies(info, {}, {})
        assert ret is False

    def test_validate_with_missing_deps(self, caplog):
        """Test with missing dependencies"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        info = {
            "targets": {
                "target1": {"required_targets": ["missing"], "required_contexts": []}
            },
            "contexts": {},
            "metadata": {},
        }
        ret, ds = cmate._validate_and_load_dependencies(info, {"target1": ("/path", None)}, {})
        assert ret is False


class TestLogMissingError:
    """Tests for _log_missing_error"""

    def test_log_missing_error(self, caplog):
        """Test _log_missing_error function"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        missing_deps = {
            "target1": {"targets": ["dep1"], "contexts": ["ctx1"]}
        }
        all_targets = {"dep1": {"desc": "Dependency 1"}}
        all_contexts = {"ctx1": {"desc": ("Context 1", None), "options": ["a"]}}

        cmate._log_missing_error(missing_deps, all_targets, all_contexts)
        # Should log error message


class TestValidateAndLoadTargetsExtended:
    """Extended tests for _validate_and_load_targets"""

    def test_load_target_file_not_found(self, caplog):
        """Test loading target with file not found"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        ds = DataSource()
        input_targets = {"config": ("/nonexistent/path.json", None)}
        all_targets = {"config": {"parse_type": "json"}}

        ret, matched = cmate._validate_and_load_targets(input_targets, all_targets, ds)
        assert ret is False

    def test_load_target_unsupported_type(self, caplog):
        """Test loading target with unsupported parse type"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        ds = DataSource()
        input_targets = {"config": ("/path", "unsupported")}
        all_targets = {"config": {"parse_type": None}}

        ret, matched = cmate._validate_and_load_targets(input_targets, all_targets, ds)
        assert ret is False

    def test_load_target_parse_error(self, caplog, tmp_path):
        """Test loading target with parse error"""
        import logging

        cmate.logger.setLevel(logging.ERROR)
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json")

        ds = DataSource()
        input_targets = {"config": (str(bad_json), None)}
        all_targets = {"config": {"parse_type": "json"}}

        ret, matched = cmate._validate_and_load_targets(input_targets, all_targets, ds)
        assert ret is False


class TestRunExtended:
    """Extended tests for run function"""

    def test_run_with_keyerror(self, tmp_path):
        """Test run when KeyError is raised during rule collection"""
        # Create a rule file that will cause KeyError
        rule_file = tmp_path / "test.cmate"
        rule_file.write_text("[par test]\nassert ${undefined::key} == 1, 'test'\n")

        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        result = cmate.run(str(rule_file), configs={"test": (str(config_file), "json")})
        assert result == 1

    def test_run_with_output_path(self, tmp_path):
        """Test run with output path"""
        rule_file = tmp_path / "test.cmate"
        rule_file.write_text("[par test]\nassert true, 'test'\n")

        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": 1}')

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = cmate.run(
            str(rule_file),
            configs={"test": (str(config_file), "json")},
            output_path=str(output_dir)
        )
        # Should complete without error
        assert isinstance(result, int)


class TestActualRun:
    """Tests for _actual_run function"""

    def test_actual_run_success(self):
        """Test _actual_run with successful tests"""
        ds = DataSource()
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test message", Severity.ERROR)
        ruleset = {"test": {rule}}
        output = {}

        result = cmate._actual_run(ruleset, ds, failfast=False, verbosity=False, output_path=None)
        assert result is True

    def test_actual_run_failure(self):
        """Test _actual_run with failing tests"""
        from cmate._ast import Compare, DictPath
        ds = DataSource()
        # Use a comparison that will evaluate to False
        compare = Compare(1, 1, DictPath(1, 1, "test::key"), "==", Constant(1, 10, "expected"))
        rule = Rule(1, 1, compare, "test message", Severity.ERROR)
        ruleset = {"test": {rule}}
        output = {}

        result = cmate._actual_run(ruleset, ds, failfast=False, verbosity=False, output_path=None)
        assert result is False
