import ipaddress
import json
from pathlib import Path

import pytest
import yaml

from cmate.util import (
    _parse_format_from_path,
    func_timeout,
    get_cur_ip,
    load_from_file,
    ParseFormat,
    ParseFormatError,
    Severity,
)


class TestSeverity:
    """Tests for Severity enum"""

    def test_severity_values(self):
        """Test severity enum values"""
        assert Severity.INFO.value == "[RECOMMEND]"
        assert Severity.WARNING.value == "[WARNING]"
        assert Severity.ERROR.value == "[NOK]"

    def test_severity_comparison(self):
        """Test severity comparison operators"""
        assert Severity.INFO < Severity.WARNING
        assert Severity.WARNING < Severity.ERROR
        assert Severity.INFO < Severity.ERROR
        assert Severity.ERROR > Severity.WARNING
        assert Severity.WARNING > Severity.INFO

    def test_severity_comparison_with_strings(self):
        """Test severity comparison with non-Severity types raises TypeError"""
        with pytest.raises(TypeError):
            _ = Severity.INFO < "WARNING"
        with pytest.raises(TypeError):
            _ = Severity.WARNING < "ERROR"
        with pytest.raises(TypeError):
            _ = Severity.ERROR > "INFO"

    def test_severity_equality(self):
        """Test severity equality"""
        assert Severity.INFO == Severity.INFO
        assert Severity.INFO != Severity.WARNING

    def test_severity_color_code(self):
        """Test severity color codes"""
        # Just verify they return strings (colorama codes)
        assert isinstance(Severity.INFO.color_code, str)
        assert isinstance(Severity.WARNING.color_code, str)
        assert isinstance(Severity.ERROR.color_code, str)

    def test_severity_str(self):
        """Test severity string representation"""
        str_repr = str(Severity.INFO)
        assert "[RECOMMEND]" in str_repr


class TestExtToType:
    """Tests for _parse_format_from_path function"""

    def test_parse_format_from_path_json(self):
        """Test extracting json extension"""
        assert _parse_format_from_path(Path("config.json")) == ParseFormat.JSON

    def test_parse_format_from_path_yaml(self):
        """Test extracting yaml extension"""
        assert _parse_format_from_path(Path("config.yaml")) == ParseFormat.YAML

    def test_parse_format_from_path_yml(self):
        """Test extracting yml extension"""
        assert _parse_format_from_path(Path("config.yml")) == ParseFormat.YML

    def test_parse_format_from_path_no_ext(self):
        """Test file without extension"""
        assert _parse_format_from_path(Path("config")) == ParseFormat.UNKNOWN

    def test_parse_format_from_path_uppercase(self):
        """Test uppercase extension returns UNKNOWN (case-sensitive matching)"""
        assert _parse_format_from_path(Path("config.JSON")) == ParseFormat.UNKNOWN
        assert _parse_format_from_path(Path("config.YAML")) == ParseFormat.UNKNOWN

    def test_parse_format_from_path_multiple_dots(self):
        """Test file with multiple dots"""
        assert _parse_format_from_path(Path("config.test.json")) == ParseFormat.JSON


class TestLoad:
    """Tests for load function"""

    def test_load_json_file(self, tmp_path):
        """Test loading JSON file"""
        json_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        json_file.write_text(json.dumps(test_data))

        result = load_from_file(str(json_file))
        assert result == test_data

    def test_load_yaml_file(self, tmp_path):
        """Test loading YAML file"""
        yaml_file = tmp_path / "test.yaml"
        test_data = {"key": "value", "number": 42}
        yaml_file.write_text(yaml.dump(test_data))

        result = load_from_file(str(yaml_file))
        assert result == test_data

    def test_load_yml_file(self, tmp_path):
        """Test loading YML file"""
        yml_file = tmp_path / "test.yml"
        test_data = {"key": "value"}
        yml_file.write_text(yaml.dump(test_data))

        result = load_from_file(str(yml_file))
        assert result == test_data

    def test_load_with_explicit_parse_format(self, tmp_path):
        """Test loading with explicit parse format"""
        json_file = tmp_path / "config.txt"
        test_data = {"key": "value"}
        json_file.write_text(json.dumps(test_data))

        result = load_from_file(str(json_file), parse_format=ParseFormat.JSON)
        assert result == test_data

    def test_load_empty_yaml(self, tmp_path):
        """Test loading empty YAML file"""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        result = load_from_file(str(yaml_file))
        assert result is None

    def test_load_multi_document_yaml(self, tmp_path):
        """Test loading multi-document YAML file"""
        yaml_file = tmp_path / "multi.yaml"
        yaml_file.write_text("doc1: value1\n---\ndoc2: value2\n")

        result = load_from_file(str(yaml_file))
        assert isinstance(result, list)
        assert len(result) == 2

    def test_load_unsupported_type(self, tmp_path):
        """Test loading unsupported file type"""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")

        with pytest.raises(ParseFormatError, match="Unsupported parse format"):
            load_from_file(str(txt_file))

    def test_load_nonexistent_file(self):
        """Test loading non-existent file"""
        with pytest.raises(Exception):  # noqa: B017
            load_from_file("/nonexistent/path/file.json")


class TestGetCurIp:
    """Tests for get_cur_ip function"""

    def test_get_cur_ip_returns_string(self):
        """Test that get_cur_ip returns an IPv4Address or None"""
        result = get_cur_ip()
        assert result is None or isinstance(result, ipaddress.IPv4Address)

    def test_get_cur_ip_no_exception(self):
        """Test that get_cur_ip doesn't raise exception"""
        try:
            get_cur_ip()
        except Exception as e:
            pytest.fail(f"get_cur_ip raised an exception: {e}")


class TestFuncTimeout:
    """Tests for func_timeout function"""

    def test_func_timeout_success(self):
        """Test function that completes within timeout"""

        def quick_func():
            return "success"

        result = func_timeout(5, quick_func)
        assert result == "success"

    def test_func_timeout_with_args(self):
        """Test function with arguments"""

        def add(a, b):
            return a + b

        result = func_timeout(5, add, 2, 3)
        assert result == 5

    def test_func_timeout_with_kwargs(self):
        """Test function with keyword arguments"""

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = func_timeout(5, greet, "World", greeting="Hi")
        assert result == "Hi, World"

    def test_func_timeout_raises_timeout(self):
        """Test function that exceeds timeout"""

        def slow_func():
            import time

            time.sleep(10)
            return "completed"

        with pytest.raises(TimeoutError, match="timed out after"):
            func_timeout(1, slow_func)

    def test_func_timeout_exception_propagation(self):
        """Test that exceptions are properly propagated"""

        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            func_timeout(5, failing_func)

    def test_load_yaml_empty_list(self, tmp_path):
        """Test loading YAML with empty list"""
        yaml_file = tmp_path / "empty_list.yaml"
        yaml_file.write_text("[]")
        result = load_from_file(str(yaml_file))
        assert result == []

    def test_load_yaml_nested_structure(self, tmp_path):
        """Test loading YAML with nested structure"""
        yaml_file = tmp_path / "nested.yaml"
        yaml_file.write_text("level1:\n  level2:\n    key: value\n")
        result = load_from_file(str(yaml_file))
        assert result == {"level1": {"level2": {"key": "value"}}}
