import logging
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch  # noqa: F401

import pytest

from cmate._ast import Compare, Constant, DictPath, Rule
from cmate._test import (
    _make_test_case,
    _make_test_method,
    make_test_suite,
    RuleAssertionError,
    RuleTestResult,
    RuleTestRunner,
    WarningCollector,
)
from cmate.util import Severity


class TestRuleAssertionError:
    """Tests for RuleAssertionError class"""

    def test_rule_assertion_error_creation(self):
        """Test RuleAssertionError creation"""
        rule_node = MagicMock()
        rule_node.severity = Severity.ERROR
        rule_node.msg = "Test error message"
        rule_node.test = MagicMock()

        history = [("key", "value")]
        err = RuleAssertionError(rule_node, history)

        assert err.rule_node == rule_node
        assert err.history == history

    def test_build_err_msg_simple(self):
        """Test building error message with simple history"""
        from cmate._ast import Constant

        test = Compare(
            1, 1, DictPath(1, 1, "config::key"), "==", Constant(1, 10, "expected")
        )
        rule_node = Rule(1, 1, test, "Test error", Severity.ERROR)

        history = [("config::key", "value")]
        err = RuleAssertionError(rule_node, history)
        msg = err.build_err_msg()

        assert "Test error" in msg
        assert "config::key" in msg

    def test_build_err_msg_with_tuple(self):
        """Test building error message with tuple values in history"""
        from cmate._ast import Constant

        test = Compare(
            1, 1, DictPath(1, 1, "config::key"), "==", Constant(1, 10, "expected")
        )
        rule_node = Rule(1, 1, test, "Test error", Severity.ERROR)

        history = [("config::key", ("actual", "reference"))]
        err = RuleAssertionError(rule_node, history)
        msg = err.build_err_msg()

        assert "Test error" in msg
        assert "reference" in msg
        assert "actual" in msg


class TestRuleTestResult:
    """Tests for RuleTestResult class"""

    @pytest.fixture
    def result(self):
        stream = StringIO()
        res = RuleTestResult(
            stream=stream, verbosity=False, total_cnt=10, failfast=False
        )
        return res

    def test_add_success(self, result):
        """Test addSuccess method"""
        test = MagicMock()
        test.namespace = "test_ns"
        result.addSuccess(test)
        # Status chars contain color codes, just check it's not empty
        assert len(result._status_chars) > 0

    def test_add_failure(self, result):
        """Test addFailure method"""
        test = MagicMock()
        test.namespace = "test_ns"

        from cmate._ast import Constant

        test_node = Compare(1, 1, DictPath(1, 1, "key"), "==", Constant(1, 10, "val"))
        rule_node = Rule(1, 1, test_node, "error", Severity.ERROR)
        err = RuleAssertionError(rule_node, [])

        result.addFailure(test, (Exception, err, None))
        assert len(result.failures) == 1

    def test_add_error(self, result):
        """Test addError method"""
        test = MagicMock()
        test.namespace = "test_ns"
        result.addError(test, (Exception, Exception("error"), None))
        assert len(result.errors) == 1

    def test_add_skip(self, result):
        """Test addSkip method"""
        test = MagicMock()
        test.namespace = "test_ns"
        result.addSkip(test, "reason")
        assert len(result.skipped) == 1

    def test_add_expected_failure(self, result):
        """Test addExpectedFailure method"""
        test = MagicMock()
        test.namespace = "test_ns"
        result.addExpectedFailure(test, (Exception, Exception("error"), None))
        assert len(result.expectedFailures) == 1

    def test_add_unexpected_success(self, result):
        """Test addUnexpectedSuccess method"""
        test = MagicMock()
        test.namespace = "test_ns"
        result.addUnexpectedSuccess(test)
        assert len(result.unexpectedSuccesses) == 1


class TestRuleTestRunner:
    """Tests for RuleTestRunner class"""

    def test_runner_creation(self):
        """Test RuleTestRunner creation"""
        runner = RuleTestRunner()
        assert runner.verbosity is False
        assert runner.failfast is False

    def test_runner_with_custom_params(self):
        """Test RuleTestRunner with custom parameters"""
        stream = StringIO()
        runner = RuleTestRunner(stream=stream, failfast=True, verbosity=True)
        assert runner.verbosity is True
        assert runner.failfast is True

    def test_run_empty_suite(self):
        """Test running empty test suite"""
        stream = StringIO()
        runner = RuleTestRunner(stream=stream)

        suite = unittest.TestSuite()
        runner.run(suite)  # noqa: F841

        output = stream.getvalue()
        assert "collected 0 items" in output
        assert "no tests ran" in output


class TestMakeTestSuite:
    """Tests for make_test_suite function"""

    def test_make_test_suite_empty(self):
        """Test making test suite with empty ruleset"""
        data_source = MagicMock()
        ruleset = {}
        output = {}

        suite = make_test_suite(data_source, ruleset, output)
        assert suite.countTestCases() == 0

    def test_make_test_suite_with_rules(self):
        """Test making test suite with rules"""
        data_source = MagicMock()

        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test message", Severity.ERROR)
        ruleset = {"test_ns": {rule}}
        output = {}

        suite = make_test_suite(data_source, ruleset, output)
        assert suite.countTestCases() == 1

    def test_make_test_suite_multiple_namespaces(self):
        """Test making test suite with multiple namespaces"""
        data_source = MagicMock()

        rule1 = Rule(1, 1, Constant(1, 1, True), "msg1", Severity.ERROR)
        rule2 = Rule(2, 1, Constant(2, 1, True), "msg2", Severity.WARNING)
        ruleset = {"ns1": {rule1}, "ns2": {rule2}}
        output = {}

        suite = make_test_suite(data_source, ruleset, output)
        assert suite.countTestCases() == 2


class TestMakeTestCase:
    """Tests for _make_test_case function"""

    def test_make_test_case(self):
        """Test creating test case class"""
        rule = Rule(1, 1, Constant(1, 1, True), "test", Severity.ERROR)
        cls = _make_test_case("TestClass", {rule}, "test_ns", {})

        assert cls.__name__ == "TestClass"
        assert hasattr(cls, "test_1")

    def test_make_test_case_multiple_rules(self):
        """Test creating test case with multiple rules"""
        rule1 = Rule(10, 1, Constant(10, 1, True), "test1", Severity.ERROR)
        rule2 = Rule(20, 1, Constant(20, 1, True), "test2", Severity.WARNING)
        cls = _make_test_case("TestClass", {rule1, rule2}, "test_ns", {})

        assert hasattr(cls, "test_10")
        assert hasattr(cls, "test_20")


class TestMakeTestMethod:
    """Tests for _make_test_method function"""

    def test_make_test_method_pass(self):
        """Test creating test method that passes"""
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test message", Severity.ERROR)

        test_method = _make_test_method(rule, "test_ns", {})

        # Create a mock instance
        inst = MagicMock()
        inst.evaluator.evaluate.return_value = True
        inst.evaluator.history = []

        # Should not raise
        test_method(inst)

    def test_make_test_method_fail(self):
        """Test creating test method that fails"""
        const = Constant(1, 1, False)
        rule = Rule(1, 1, const, "test message", Severity.ERROR)

        test_method = _make_test_method(rule, "test_ns", {})

        inst = MagicMock()
        inst.evaluator.evaluate.return_value = False
        inst.evaluator.history = []

        with pytest.raises(RuleAssertionError):
            test_method(inst)

    def test_make_test_method_output_populated(self):
        """Test that test method populates output dictionary"""
        const = Constant(1, 1, True)
        rule = Rule(1, 1, const, "test message", Severity.ERROR)

        test_method = _make_test_method(rule, "test_ns", {})

        inst = MagicMock()
        inst.evaluator.evaluate.return_value = True
        inst.evaluator.history = [("key", "value")]

        output = {}
        test_method = _make_test_method(rule, "test_ns", output)
        test_method(inst)

        assert "test_ns" in output
        assert len(output["test_ns"]) == 1
        assert output["test_ns"][0]["test"] is not None
        assert output["test_ns"][0]["msg"] == "test message"


class TestRuleTestRunnerExtended:
    """Extended tests for RuleTestRunner"""

    def test_runner_with_custom_rescls(self):
        """Test runner with custom result class"""

        class CustomResult(RuleTestResult):
            pass

        stream = StringIO()
        runner = RuleTestRunner(stream=stream, rescls=CustomResult)
        assert runner.rescls == CustomResult


class TestWarningCollector:
    """Tests for WarningCollector class"""

    def test_warning_collector_creation(self):
        """Test WarningCollector creation"""
        collector = WarningCollector()
        assert collector.warnings == []

    def test_warning_collector_emit(self):
        """Test WarningCollector emit method"""
        collector = WarningCollector()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test warning",
            args=(),
            exc_info=None,
        )
        collector.emit(record)
        assert len(collector.warnings) == 1
        assert "Test warning" in collector.warnings[0]

    def test_warning_collector_emit_info(self):
        """Test LogCollector now collects all log levels including INFO"""
        collector = WarningCollector()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test info",
            args=(),
            exc_info=None,
        )
        collector.emit(record)
        # Now LogCollector collects all log levels (INFO and above)
        assert len(collector.messages) == 1
        assert "Test info" in collector.messages[0]

    def test_warning_collector_get_warnings(self):
        """Test WarningCollector get_warnings method"""
        collector = WarningCollector()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test warning",
            args=(),
            exc_info=None,
        )
        collector.emit(record)
        warnings = collector.get_warnings()
        assert len(warnings) == 1

    def test_warning_collector_clear(self):
        """Test WarningCollector clear method"""
        collector = WarningCollector()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test warning",
            args=(),
            exc_info=None,
        )
        collector.emit(record)
        collector.clear()
        assert collector.warnings == []


class TestRuleTestResultExtended:
    """Extended tests for RuleTestResult"""

    def test_add_warning(self):
        """Test addWarning method"""
        stream = StringIO()
        result = RuleTestResult(stream=stream)
        result.addWarning("Test warning message")
        assert "Test warning message" in result._log_messages

    def test_print_warnings(self):
        """Test printWarnings method"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        result.addWarning("Test warning 1")
        result.addWarning("Test warning 2")
        result.printWarnings()
        output = stream.getvalue()
        # Now prints "LOG MESSAGES" instead of "WARNINGS"
        assert "LOG MESSAGES" in output
        assert "Test warning 1" in output
        assert "Test warning 2" in output

    def test_print_warnings_empty(self):
        """Test printWarnings with no warnings"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        result.printWarnings()
        output = stream.getvalue()
        assert output == ""

    def test_add_expected_failure(self):
        """Test addExpectedFailure method"""
        stream = StringIO()
        result = RuleTestResult(stream=stream)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addExpectedFailure(test, (Exception, Exception("test"), None))
        assert len(result.expectedFailures) == 1

    def test_add_expected_failure_verbose(self):
        """Test addExpectedFailure with verbosity"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream, verbosity=True, total_cnt=1)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addExpectedFailure(test, (Exception, Exception("test"), None))
        assert len(result.expectedFailures) == 1

    def test_add_unexpected_success(self):
        """Test addUnexpectedSuccess method"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addUnexpectedSuccess(test)
        assert len(result.unexpectedSuccesses) == 1

    def test_add_unexpected_success_verbose(self):
        """Test addUnexpectedSuccess with verbosity"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream, verbosity=True, total_cnt=1)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addUnexpectedSuccess(test)
        assert len(result.unexpectedSuccesses) == 1

    def test_add_error(self):
        """Test addError method"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addError(test, (Exception, Exception("test"), None))
        assert len(result.errors) == 1

    def test_add_error_verbose(self):
        """Test addError with verbosity"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream, verbosity=True, total_cnt=1)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addError(test, (Exception, Exception("test"), None))
        assert len(result.errors) == 1

    def test_add_skip(self):
        """Test addSkip method"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addSkip(test, "skipped reason")
        assert len(result.skipped) == 1

    def test_add_skip_verbose(self):
        """Test addSkip with verbosity"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream, verbosity=True, total_cnt=1)
        test = MagicMock()
        test.id.return_value = "test_id"
        test.namespace = "test_ns"

        result.addSkip(test, "skipped reason")
        assert len(result.skipped) == 1


class TestRuleTestRunnerWarnings:
    """Tests for RuleTestRunner warning collection"""

    def test_setup_warning_collection(self):
        """Test _setup_warning_collection method"""
        stream = StringIO()
        runner = RuleTestRunner(stream=stream)
        runner._setup_warning_collection()
        # Check that WarningCollector was added to logger handlers
        logger = logging.getLogger()
        has_collector = any(isinstance(h, WarningCollector) for h in logger.handlers)
        assert has_collector

    def test_transfer_warnings_to_result(self):
        """Test _transfer_warnings_to_result method"""
        stream = StringIO()
        runner = RuleTestRunner(stream=stream)
        result = RuleTestResult(stream=stream)

        # Add a warning to the collector
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test warning",
            args=(),
            exc_info=None,
        )
        runner._warning_collector.emit(record)

        runner._transfer_warnings_to_result(result)
        assert "Test warning" in result._log_messages
        assert runner._warning_collector.messages == []


class TestRuleTestResultPrintErrors:
    """Tests for RuleTestResult printErrors method"""

    def test_print_errors_with_errors(self):
        """Test printErrors with errors"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        test = MagicMock()
        test.id.return_value = "test_id"

        result.addError(test, (Exception, Exception("test error"), None))
        result.printErrors()
        output = stream.getvalue()
        assert "ERRORS" in output

    def test_print_errors_with_failures(self):
        """Test printErrors with failures"""
        from unittest.runner import _WritelnDecorator

        from cmate._ast import Compare, Constant, DictPath, Rule

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        test = MagicMock()
        test.id.return_value = "test_id"

        # Create a rule with severity for sorting
        compare = Compare(
            1, 1, DictPath(1, 1, "test::key"), "==", Constant(1, 10, "expected")
        )
        rule = Rule(1, 1, compare, "test message", Severity.ERROR)
        err = RuleAssertionError(rule, [("key", "value")])

        result.failures.append((test, err))
        result.printErrors()
        assert "FAILURES" in stream.getvalue()

    def test_print_errors_empty(self):
        """Test printErrors with no errors or failures"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream)
        result.printErrors()
        output = stream.getvalue()
        # Should just write a newline and flush
        assert output == "\n"


class TestRuleTestResultUpdateMethods:
    """Tests for RuleTestResult _update methods"""

    def test_update_verbose_long_test_id(self):
        """Test _update_verbose with long test id"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream, verbosity=True, total_cnt=1)
        test = MagicMock()
        test.id.return_value = "a" * 200  # Very long test id
        test.namespace = "test_ns"

        result._update_verbose(test, "PASSED")
        output = stream.getvalue()
        assert "..." in output or "PASSED" in output

    def test_update_with_overflow(self):
        """Test _update when status chars overflow available space"""
        from unittest.runner import _WritelnDecorator

        stream = _WritelnDecorator(StringIO())
        result = RuleTestResult(stream=stream, total_cnt=100)

        # Add many status chars to trigger overflow
        test = MagicMock()
        test.namespace = "test_ns"
        for _ in range(200):
            result._status_chars.append(".")

        result._update(test, ".")
        # Should handle overflow gracefully - output not needed for assertion
