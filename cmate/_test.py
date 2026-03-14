# -------------------------------------------------------------------------
# This file is part of the MindStudio project.
# Copyright (c) 2025-2026 Huawei Technologies Co.,Ltd.
#
# MindStudio is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#
#          `http://license.coscl.org.cn/MulanPSL2`
#
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# -------------------------------------------------------------------------

import re
import shutil
import sys
import time
import unittest
from typing import Set

from colorama import Fore, Style

from . import _ast
from .util import Severity
from .visitor import _ExpressionEvaluator, _make_partition_resolver, ASTFormatter


# ANSI escape code pattern for calculating visible text length
_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _visible_len(text: str) -> int:
    """Calculate the visible length of text, excluding ANSI escape codes."""
    return len(_ANSI_ESCAPE_PATTERN.sub("", text))


def _center_with_ansi(text: str, width: int, fillchar: str = " ") -> str:
    """Center text with ANSI codes, using visible length for calculation."""
    visible = _visible_len(text)
    if visible >= width:
        return text
    padding = width - visible
    left_pad = padding // 2
    right_pad = padding - left_pad
    return fillchar * left_pad + text + fillchar * right_pad


class RuleAssertionError(AssertionError):
    """Carries the failed Rule node and the evaluator's variable history."""

    def __init__(self, rule_node: _ast.Rule, history: list):
        super().__init__()
        self.rule_node = rule_node
        self.history = history

    def build_err_msg(self) -> str:
        formatter = ASTFormatter()
        sev_color = self.rule_node.severity.color_code
        sev_name = self.rule_node.severity.name

        lines = [
            "",
            f"  {Style.DIM}Expected:{Style.RESET_ALL} "
            f"{Fore.CYAN}{formatter.visit(self.rule_node.test)}{Fore.RESET}",
            "",
        ]

        if self.history:
            lines.append(f"  {Style.DIM}Got:{Style.RESET_ALL}")
            for k, v in self.history:
                if isinstance(v, tuple):
                    lines.append(
                        f"    {k} = {Fore.YELLOW}{v[0]!r}{Fore.RESET} "
                        f"({Style.DIM}from{Style.RESET_ALL} {v[1]})"
                    )
                else:
                    lines.append(f"    {k} = {Fore.YELLOW}{v!r}{Fore.RESET}")
            lines.append("")

        lines.append(f"  {sev_color}[{sev_name}]{Fore.RESET} {self.rule_node.msg}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Custom test result / runner
# ---------------------------------------------------------------------------


class RuleTestResult(unittest.TestResult):
    _COLOR = {
        ".": Fore.GREEN,
        "PASSED": Fore.GREEN,
        "F": Fore.RED,
        "FAILED": Fore.RED,
        "E": Fore.RED,
        "ERROR": Fore.RED,
        "s": Fore.YELLOW,
        "SKIPPED": Fore.YELLOW,
    }

    def __init__(
        self,
        stream=None,
        descriptions=None,
        verbosity=False,
        total_cnt=None,
        failfast=False,
    ):
        super().__init__(stream=stream, descriptions=descriptions, verbosity=verbosity)
        if stream is None:
            stream = unittest.runner._WritelnDecorator(sys.stderr)
        self.stream = stream
        self.verbosity = verbosity
        self.total_cnt = total_cnt
        self.failfast = failfast
        self._cols = shutil.get_terminal_size()[0]
        self._status_chars = []
        self._colorcode_map = {
            ".": Fore.GREEN,
            "PASSED": Fore.GREEN,
            "F": Fore.RED,
            "E": Fore.RED,
            "FAILED": Fore.RED,
            "ERROR": Fore.RED,
            "s": Fore.YELLOW,
            "SKIPPED": Fore.YELLOW,
            "W": Fore.YELLOW,
            "WARNING": Fore.YELLOW,
        }
        self._status_chars: list[str] = []
        self._current_namespace = None

    def startTestRun(self):
        self.stream.writeln()

    def stopTestRun(self):
        self.stream.writeln()

    def addError(self, test, err):
        self._tick(test, "ERROR" if self.verbosity else "E")
        return super().addError(test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        # Replace (test, traceback_str) with (test, RuleAssertionError instance)
        self.failures[-1] = (test, err[1])
        self._tick(test, "FAILED" if self.verbosity else "F")

    def addSuccess(self, test):
        self._tick(test, "PASSED" if self.verbosity else ".")
        return super().addSuccess(test)

    def addSkip(self, test, reason):
        self._tick(test, "SKIPPED" if self.verbosity else "s")
        return super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self._tick(test, "EXPECTEDFAILED" if self.verbosity else "x")
        return super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self._tick(test, "UNEXPECTEDPASSED" if self.verbosity else "U")
        return super().addUnexpectedSuccess(test)

    def printErrors(self):
        if self.errors:
            header = f"{Fore.RED}{' ERRORS '.center(self._cols, '=')}{Fore.RESET}"
            self.stream.writeln(header)
            for test, exc in self.errors:
                # Build header with consistent coloring
                test_header = (
                    f" [{test.namespace}] test_{test._testMethodName.split('_')[-1]} "
                )
                divider = (
                    f"{Fore.RED}"
                    + _center_with_ansi(test_header, self._cols, "_")
                    + f"{Fore.RESET}"
                )
                self.stream.writeln(divider)
                self.stream.writeln()
                self.stream.write(str(exc))
            self.stream.writeln()

        if self.failures:
            header = f"{Fore.RED}{' FAILURES '.center(self._cols, '=')}{Fore.RESET}"
            self.stream.writeln(header)
            for test, err in sorted(
                self.failures, key=lambda x: x[1].rule_node.severity, reverse=True
            ):
                sev_color = err.rule_node.severity.color_code
                # Extract test number from test method name
                test_num = test._testMethodName.split("_")[-1]
                test_header = f" [{test.namespace}] test_{test_num} "
                divider = (
                    f"{sev_color}"
                    + _center_with_ansi(test_header, self._cols, "_")
                    + f"{Fore.RESET}"
                )
                self.stream.writeln(divider)
                self.stream.writeln(err.build_err_msg())

        self.stream.flush()

    def _tick(self, test, label: str):
        if self.verbosity:
            self._tick_verbose(test, label)
        else:
            self._tick_compact(test, label)

    def _tick_compact(self, test, ch: str):
        # Detect namespace change and preserve previous partition line
        if (
            self._current_namespace is not None
            and self._current_namespace != test.namespace
        ):
            self.stream.writeln()  # Preserve previous line
            self._status_chars = []  # Reset for new partition
        self._current_namespace = test.namespace

        PERCENT_PAD = 1
        color = self._COLOR.get(ch, Fore.RESET)
        self._status_chars.append(f"{color}{ch}{Fore.RESET}")

        total = self.total_cnt or 1
        pct = int(100 * self.testsRun / total)
        pct_str = f"[{pct:3d}%]"
        pct_width = len(pct_str) + PERCENT_PAD
        colored_pct = f"{color}{pct_str}{Fore.RESET}"

        header = f"{test.namespace} "
        visible = len(header) + len(self._status_chars)
        space = self._cols - visible - pct_width

        if space > 0:
            line = f"{header}{''.join(self._status_chars)}{' ' * space}{colored_pct}"
        else:
            trimmed = self._status_chars[: max(0, len(self._status_chars) + space)]
            line = f"{header}{''.join(trimmed)} {colored_pct}"

        self.stream.write(f"\r{line}")
        self.stream.flush()

    def _tick_verbose(self, test, status: str):
        ELLIPSIS, STATUS_PAD, PERCENT_PAD, MIN_COLS = "...", 1, 1, 10
        color = self._COLOR.get(status, Fore.RESET)

        total = self.total_cnt or 1
        pct = int(100 * self.testsRun / total)
        pct_str = f"[{pct:3d}%]"
        pct_width = len(pct_str) + PERCENT_PAD
        colored_pct = f"{color}{pct_str}{Fore.RESET}"

        space = max(self._cols - pct_width, MIN_COLS)
        status_w = len(status) + STATUS_PAD
        id_w = max(0, space - status_w)

        test_id = test.id()
        if len(test_id) > id_w:
            test_id = (
                test_id[: id_w - len(ELLIPSIS)] + ELLIPSIS
                if id_w > len(ELLIPSIS)
                else test_id[:id_w]
            )

        raw = f"{test.namespace}::{test_id} {status}"
        pad = max(0, space - len(raw))
        line = (
            f"{test.namespace}::{test_id} "
            f"{color}{status}{Fore.RESET}{' ' * pad} {colored_pct}"
        )
        self.stream.writeln(line)
        self.stream.flush()


class RuleTestRunner:
    rescls = RuleTestResult

    def __init__(self, stream=None, rescls=None, failfast=False, verbosity=False):
        if stream is None:
            stream = sys.stderr
        self.stream = unittest.runner._WritelnDecorator(stream)
        if rescls is not None:
            self.rescls = rescls
        self.verbosity = verbosity
        self.failfast = failfast

    def run(self, suite):
        total = suite.countTestCases()
        res = self.rescls(
            stream=self.stream,
            verbosity=self.verbosity,
            total_cnt=total,
            failfast=self.failfast,
        )
        cols = shutil.get_terminal_size()[0]
        self.stream.writeln(f"{Style.BRIGHT}collected {total} items{Style.RESET_ALL}")

        if total == 0:
            self.stream.writeln()
            self.stream.writeln(
                f"{Fore.YELLOW}"
                + " no tests ran in 0.00s ".center(cols, "=")
                + Fore.RESET
            )
            self.stream.flush()
            return res

        t0 = time.perf_counter()
        getattr(res, "startTestRun", lambda: None)()
        try:
            suite(res)
        finally:
            getattr(res, "stopTestRun", lambda: None)()
        elapsed = time.perf_counter() - t0

        res.printErrors()

        _COUNTERS = [
            ("errors", "errors"),
            ("failures", "failed"),
            ("expectedFailures", "expected failures"),
            ("unexpectedSuccesses", "unexpected successes"),
            ("skipped", "skipped"),
        ]
        counts = [
            (getattr(res, attr), label)
            for attr, label in _COUNTERS
            if getattr(res, attr)
        ]
        failed_total = sum(len(c) for c, _ in counts)
        passed = res.testsRun - failed_total
        parts = [f"{len(c)} {lbl}" for c, lbl in counts]
        parts.append(f"{passed} passed" if passed else "no passed")
        summary = f" {', '.join(parts)} in {elapsed:.3f}s "
        color = Fore.GREEN if passed == res.testsRun else Fore.RED
        self.stream.writeln(f"{color}{summary.center(cols, '=')}{Fore.RESET}")
        self.stream.flush()
        return res


# ---------------------------------------------------------------------------
# Test suite factory
# ---------------------------------------------------------------------------


def make_test_suite(data_source, ruleset: dict, output: dict):
    """
    Build a unittest.TestSuite from *ruleset*.

    Each namespace becomes a TestCase class; each Rule becomes a test method.
    *output* is populated in-place with structured results for JSON export.
    """
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    for namespace, rule_nodes in ruleset.items():
        cls = _build_test_case(namespace, rule_nodes, data_source, output)
        suite.addTest(loader.loadTestsFromTestCase(cls))

    return suite


def _build_test_case(
    namespace: str, rule_nodes: Set[_ast.Rule], data_source, output: dict
):
    """Dynamically create a TestCase class for one partition namespace."""

    resolver = _make_partition_resolver(namespace, data_source, [])
    evaluator = _ExpressionEvaluator(data_source, resolver)

    methods = {}
    for node in rule_nodes:
        if isinstance(node, _ast.Alert):
            methods[f"test_{node.lineno}"] = _build_alert_method(
                node, namespace, evaluator, output
            )
        else:
            methods[f"test_{node.lineno}"] = _build_test_method(
                node, namespace, evaluator, output
            )

    cls = type(f"Test-{namespace}", (unittest.TestCase,), methods)
    cls.namespace = namespace
    cls.data_source = data_source
    return cls


def _build_test_method(
    rule: _ast.Rule, namespace: str, evaluator: _ExpressionEvaluator, output: dict
):
    _SEV = {Severity.INFO: "info", Severity.WARNING: "warning", Severity.ERROR: "error"}
    _RES = {True: "passed", False: "failed"}
    formatter = ASTFormatter()

    def test(inst):
        test_expr = formatter.visit(rule.test)
        result = evaluator.evaluate(rule.test)
        history = evaluator.history

        output.setdefault(namespace, []).append(
            {
                "test": test_expr,
                "msg": rule.msg,
                "severity": _SEV[rule.severity],
                "status": _RES[result],
                "metadata": dict(history),
            }
        )

        if not result:
            raise RuleAssertionError(rule, history)

    return test


def _build_alert_method(
    alert: _ast.Alert, namespace: str, evaluator: _ExpressionEvaluator, output: dict
):
    """Build a test method for an Alert node.

    Alert nodes don't evaluate a condition. They mark a field for attention
    with a message. The test always passes but logs a message.
    """
    _SEV = {Severity.INFO: "info", Severity.WARNING: "warning", Severity.ERROR: "error"}
    formatter = ASTFormatter()

    def test(inst):
        # Evaluate the field to get its current value
        field_expr = formatter.visit(alert.field)
        try:
            field_value = evaluator.evaluate(alert.field)
            history = evaluator.history
        except Exception:
            field_value = "<evaluation error>"
            history = []

        output.setdefault(namespace, []).append(
            {
                "field": field_expr,
                "value": field_value,
                "msg": alert.msg,
                "severity": _SEV[alert.severity],
                "status": "alert",
                "metadata": dict(history),
            }
        )

        # Get the test result to log the alert message
        result = inst._outcome.result if hasattr(inst, "_outcome") else None
        if result and hasattr(result, "addLogMessage"):
            color = alert.severity.color_code
            result.addLogMessage(
                f"{color}[{alert.severity.name}]{Fore.RESET} "
                f"{field_expr} = {field_value!r}: {alert.msg}"
            )

    return test
