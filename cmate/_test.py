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
from typing import Any, List, Set, Tuple

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
    """
    A Rule whose condition evaluated to False.

    Attributes:
        severity:   Severity level from the rule.
        msg:        Message declared in the rule.
        test_expr:  The rule's condition pre-formatted as a string.
                    Computed once at build time, not re-walked per run.
        history:    Ordered snapshot of (name, value) pairs the evaluator
                    recorded while walking the expression tree.
    """

    def __init__(
        self,
        *args: object,
        severity: Severity,
        msg: str,
        test_expr: str,
        history: Tuple[Tuple[str, Any], ...],
    ) -> None:
        if not history:
            raise ValueError("History must not be empty")

        super().__init__(*args)
        self.severity = severity
        self.msg = msg
        self.test_expr = test_expr
        self.history = history

    def build_err_msg(self) -> str:
        sev_color = self.severity.color_code
        lines = [
            "",
            f"  {Style.DIM}Expected:{Style.RESET_ALL} "
            f"{Fore.CYAN}{self.test_expr}{Fore.RESET}",
            "",
        ]

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
        lines.append(f"  {sev_color}[{self.severity.name}]{Fore.RESET} {self.msg}")
        return "\n".join(lines)


class AlertError(AssertionError):
    """
    An Alert that unconditionally marks a field for attention.

    Attributes:
        severity:    Severity level (default WARNING in the parser).
        msg:         Message declared in the alert.
        field_expr:  The alert's target field pre-formatted as a string.
        field_value: The field's runtime value; None on evaluation error.
    """

    def __init__(
        self,
        *args: object,
        severity: Severity,
        msg: str,
        field_expr: str,
        history: Tuple[Tuple[str, Any], ...],
    ) -> None:
        if not history:
            raise ValueError("History must not be empty")

        super().__init__(*args)
        self.severity = severity
        self.msg = msg
        self.field_expr = field_expr
        self.history = history

    def build_err_msg(self) -> str:
        sev_color = self.severity.color_code
        lines = [
            "",
            f"  {Style.DIM}Alert:{Style.RESET_ALL} "
            f"{Fore.CYAN}{self.field_expr}{Fore.RESET}",
            "",
        ]

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
        lines.append(f"  {sev_color}[{self.severity.name}]{Fore.RESET} {self.msg}")
        return "\n".join(lines)


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
        "A": Fore.YELLOW,
        "ALERT": Fore.YELLOW,
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
        self._status_chars: List[str] = []
        self._current_namespace = None

        # Alert notices are tracked separately from failures.
        # They are informational and do not affect the pass/fail count.
        self.alerts: List[Tuple[unittest.TestCase, AlertError]] = []

    def startTestRun(self):
        self.stream.writeln()

    def stopTestRun(self):
        self.stream.writeln()

    def addError(self, test, err):
        self._tick(test, "ERROR" if self.verbosity else "E")
        return super().addError(test, err)

    def addFailure(self, test, err):
        exc = err[1]

        if isinstance(exc, AlertError):
            # Alerts are not failures: track separately, do not call super().
            self.alerts.append((test, exc))
            self._tick(test, "ALERT" if self.verbosity else "A")
            return

        super().addFailure(test, err)
        # Replace raw (type, value, tb) with the ValidationError so
        # printErrors can call issue.build_err_msg() without a traceback dump.
        self.failures[-1] = (test, exc)
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
            for test, exc in sorted(
                self.failures, key=lambda x: x[1].severity, reverse=True
            ):
                sev_color = exc.severity.color_code
                test_num = test._testMethodName.split("_")[-1]
                test_header = f" [{test.namespace}] test_{test_num} "
                divider = (
                    f"{sev_color}"
                    + _center_with_ansi(test_header, self._cols, "_")
                    + f"{Fore.RESET}"
                )
                self.stream.writeln(divider)
                self.stream.writeln(exc.build_err_msg())

        if self.alerts:
            header = f"{Fore.YELLOW}{' ALERTS '.center(self._cols, '=')}{Fore.RESET}"
            self.stream.writeln(header)
            for test, exc in self.alerts:
                sev_color = exc.severity.color_code
                test_num = test._testMethodName.split("_")[-1]
                test_header = f" [{test.namespace}] test_{test_num} "
                divider = (
                    f"{sev_color}"
                    + _center_with_ansi(test_header, self._cols, "_")
                    + f"{Fore.RESET}"
                )
                self.stream.writeln(divider)
                self.stream.writeln(exc.build_err_msg())

        self.stream.flush()

    def _tick(self, test, label: str):
        if self.verbosity:
            self._tick_verbose(test, label)
        else:
            self._tick_compact(test, label)

    def _tick_compact(self, test, ch: str):
        if (
            self._current_namespace is not None
            and self._current_namespace != test.namespace
        ):
            self.stream.writeln()
            self._status_chars = []
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

    def __init__(
        self, stream=None, rescls=None, failfast=False, verbosity=False, deselected=0
    ):
        if stream is None:
            stream = sys.stderr
        self.stream = unittest.runner._WritelnDecorator(stream)
        if rescls is not None:
            self.rescls = rescls
        self.verbosity = verbosity
        self.failfast = failfast
        self.deselected = deselected

    def run(self, suite):
        total = suite.countTestCases()
        res = self.rescls(
            stream=self.stream,
            verbosity=self.verbosity,
            total_cnt=total,
            failfast=self.failfast,
        )
        cols = shutil.get_terminal_size()[0]

        # Print collection summary with deselected count if applicable
        if self.deselected > 0:
            self.stream.writeln(
                f"{Style.BRIGHT}collected {total + self.deselected} items / "
                f"{self.deselected} deselected / {total} selected{Style.RESET_ALL}"
            )
        else:
            self.stream.writeln(
                f"{Style.BRIGHT}collected {total} items{Style.RESET_ALL}"
            )

        if total == 0:
            self.stream.writeln()
            if self.deselected > 0:
                self.stream.writeln(
                    f"{Fore.YELLOW}"
                    + f" {self.deselected} deselected in 0.00s ".center(cols, "=")
                    + Fore.RESET
                )
            else:
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

        alert_count = len(res.alerts)
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
        passed = res.testsRun - failed_total - alert_count
        parts = [f"{len(c)} {lbl}" for c, lbl in counts]
        if alert_count:
            parts.append(f"{alert_count} alerts")
        parts.append(f"{passed} passed" if passed else "no passed")
        # Add deselected count if applicable
        if self.deselected > 0:
            parts.append(f"{self.deselected} deselected")
        summary = f" {', '.join(parts)} in {elapsed:.3f}s "
        color = Fore.GREEN if passed == res.testsRun - alert_count else Fore.RED
        self.stream.writeln(f"{color}{summary.center(cols, '=')}{Fore.RESET}")
        self.stream.flush()
        return res


# ---------------------------------------------------------------------------
# Test suite factory
# ---------------------------------------------------------------------------


def make_test_suite(data_source, ruleset: dict, output: dict):
    """
    Build a unittest.TestSuite from *ruleset*.

    Each namespace becomes a TestCase class; each Rule/Alert becomes a test
    method.  *output* is populated in-place with structured results for JSON
    export.
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
    formatter = ASTFormatter()

    methods = {}
    for node in rule_nodes:
        if isinstance(node, _ast.Alert):
            methods[f"test_{node.lineno}"] = _build_alert_method(
                node, namespace, evaluator, formatter, output
            )
        else:
            methods[f"test_{node.lineno}"] = _build_rule_method(
                node, namespace, evaluator, formatter, output
            )

    cls = type(f"Test-{namespace}", (unittest.TestCase,), methods)
    cls.namespace = namespace
    cls.data_source = data_source
    return cls


def _build_rule_method(
    rule: _ast.Rule,
    namespace: str,
    evaluator: _ExpressionEvaluator,
    formatter: ASTFormatter,
    output: dict,
):
    # Pre-format the expression once at build time, not on every test run.
    test_expr = formatter.visit(rule.test)

    def test(inst):
        result = evaluator.evaluate(rule.test)
        history = tuple(evaluator.history)

        output.setdefault(namespace, []).append(
            {
                "test": test_expr,
                "msg": rule.msg,
                "severity": rule.severity.name.lower(),
                "status": "passed" if result else "failed",
                "metadata": dict(history),
            }
        )

        if not result:
            raise RuleAssertionError(
                severity=rule.severity,
                msg=rule.msg,
                test_expr=test_expr,
                history=history,
            )

    return test


def _build_alert_method(
    alert: _ast.Alert,
    namespace: str,
    evaluator: _ExpressionEvaluator,
    formatter: ASTFormatter,
    output: dict,
):
    # Pre-format the field expression once at build time.
    field_expr = formatter.visit(alert.field)

    def test(inst):
        field_value = evaluator.evaluate(alert.field)
        history = tuple(evaluator.history)

        output.setdefault(namespace, []).append(
            {
                "field": field_expr,
                "value": field_value,
                "msg": alert.msg,
                "severity": alert.severity.name.lower(),
                "status": "alert",
                "metadata": dict(history),
            }
        )

        raise AlertError(
            severity=alert.severity,
            msg=alert.msg,
            field_expr=field_expr,
            history=history,
        )

    return test
