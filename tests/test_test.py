import sys
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from cmate._ast import Compare, Constant, DictPath, Rule
from cmate._test import (
    RuleAssertionError,
    RuleTestResult,
    RuleTestRunner,
    _make_test_case,
    _make_test_method,
    make_test_suite,
)
from cmate.util import Severity
from cmate.visitor import _ExpressionEvaluator


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
        from cmate._ast import Compare, Constant, DictPath

        test = Compare(1, 1, DictPath(1, 1, "config::key"), "==", Constant(1, 10, "expected"))
        rule_node = Rule(1, 1, test, "Test error", Severity.ERROR)

        history = [("config::key", "value")]
        err = RuleAssertionError(rule_node, history)
        msg = err.build_err_msg()

        assert "Test error" in msg
        assert "config::key" in msg

    def test_build_err_msg_with_tuple(self):
        """Test building error message with tuple values in history"""
        from cmate._ast import Compare, Constant, DictPath

        test = Compare(1, 1, DictPath(1, 1, "config::key"), "==", Constant(1, 10, "expected"))
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
        res = RuleTestResult(stream=stream, verbosity=False, total_cnt=10, failfast=False)
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

        from cmate._ast import Compare, Constant, DictPath
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
        result = runner.run(suite)

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
