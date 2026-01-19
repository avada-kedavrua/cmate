import sys
import time
import shutil
import unittest
from typing import Set

from colorama import Fore, Style

from . import _ast
from .visitor import ASTFormatter, _ExpressionEvaluator


class RuleAssertionError(AssertionError):
    def __init__(self, rule_node, history):
        super().__init__()
        self.rule_node = rule_node
        self.history = history

        self.pretty_formatter = ASTFormatter()

    def build_err_msg(self):
        indent = len(self.rule_node.severity.value) + 2
        lines = []

        test = self.pretty_formatter.visit(self.rule_node.test)
        lines.append('>'.ljust(indent) + test)
        lines.append('')
        for k, v in self.history:
            if isinstance(v, tuple):
                line = f'{k} -> {v[1]} -> {v[0]}'
            else:
                line = f'{k} -> {v}'
            
            lines.append('E'.ljust(indent) + line)
        lines.append('')
        lines.append(f'{self.rule_node.severity} {self.rule_node.msg}')
        return '\n'.join(lines)


class RuleTestResult(unittest.TestResult):
    def __init__(self, stream=None, descriptions=None, verbosity=False, total_cnt=None, failfast=False):
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
            '.': Fore.GREEN, 'PASSED': Fore.GREEN,
            'F': Fore.RED, 'E': Fore.RED, 'FAILED': Fore.RED, 'ERROR': Fore.RED,
            's': Fore.YELLOW, 'SKIPPED': Fore.YELLOW
        }

    def startTestRun(self):
        self.stream.writeln()

    def stopTestRun(self):
        self.stream.writeln()

    def addError(self, test, err):
        if self.verbosity:
            self._update_verbose(test, 'ERROR')
        else:
            self._update(test, 'E')
        
        return super().addError(test, err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        # change to store test instance and err instance instead
        self.failures.pop()
        self.failures.append((test, err[1]))

        if self.verbosity:
            self._update_verbose(test, 'FAILED')
        else:
            self._update(test, 'F')

    def addSuccess(self, test):
        if self.verbosity:
            self._update_verbose(test, 'PASSED')
        else:
            self._update(test, '.')
        return super().addSuccess(test)

    def addSkip(self, test, reason):
        if self.verbosity:
            self._update_verbose(test, 'SKIPPED')
        else:
            self._update(test, 's')
        return super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        if self.verbosity:
            self._update_verbose(test, 'EXPECTEDFAILED')
        else:
            self._update(test, 'x')
        return super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        if self.verbosity:
            self._update_verbose(test, 'UNEXPECTEDPASSED')
        else:
            self._update(test, 'U')
        return super().addUnexpectedSuccess(test)

    def printErrors(self):
        if self.errors:
            self.stream.writeln(' ERRORS '.center(self._cols, '='))
            for test, exc in self.errors:
                self.stream.writeln(f'{Fore.RED}' + f' {test.id()} '.center(self._cols, '_') + f'{Fore.RESET}')
                self.stream.writeln()
                self.stream.write(str(exc))
        if self.failures:
            self.stream.writeln(' FAILURES '.center(self._cols, '='))
            for test, err in sorted(self.failures, key=lambda item: item[1].rule_node.severity, reverse=True):
                self.stream.writeln(f'{Fore.RED}' + f' {test.id()} '.center(self._cols, '_') + f'{Fore.RESET}')
                self.stream.writeln()
                self.stream.writeln(err.build_err_msg())
        self.stream.writeln()
        self.stream.flush()
    
    def _update(self, test, ch):
        PERCENT_PADDING = 1
        
        color_code = self._colorcode_map.get(ch, Fore.RESET)
        self._status_chars.append(f'{color_code}{ch}{Fore.RESET}')
        
        namespace = test.namespace
        
        total = self.total_cnt or 1
        percent = int(100 * (self.testsRun / total))
        percent_str = f'[{percent:3d}%]'
        percent_width = len(percent_str) + PERCENT_PADDING        
        colored_percent_str = f'{color_code}{percent_str}{Fore.RESET}'
        
        header = f'{namespace} '
        # use raw lengths for layout (colored sequences are invisible width-wise)
        visible_len = len(header) + len(self._status_chars)
        available_space = self._cols - visible_len - percent_width
        
        if available_space > 0:
            status_disp = ''.join(self._status_chars)
            pad = ' ' * available_space
            line = f"{header}{status_disp}{pad}{colored_percent_str}"
        else:
            # if line too long, truncate raw status and recompute display
            overflow = -available_space
            if overflow >= len(self._status_chars):
                trimmed_disp = ''
            else:
                trimmed_disp = self._status_chars[:-overflow]
            line = f"{header}{trimmed_disp} {colored_percent_str}"

        self.stream.write(f'\r{line}')
        self.stream.flush()
    
    def _update_verbose(self, test, status_word):
        MIN_COLUMNS = 10
        ELLIPSIS = '...'
        STATUS_PADDING = 1
        PERCENT_PADDING = 1
        
        namespace = test.namespace
        color_code = self._colorcode_map.get(status_word, Fore.RESET)

        total = self.total_cnt or 1
        percent = int(100 * (self.testsRun / total))
        percent_str = f'[{percent:3d}%]'
        percent_width = len(percent_str) + PERCENT_PADDING
        colored_percent_str = f'{color_code}{percent_str}{Fore.RESET}'
        
        available_space = max(self._cols - percent_width, MIN_COLUMNS)
        
        status_width = len(status_word) + STATUS_PADDING
        test_id_width = max(0, available_space - status_width)
        
        test_id = test.id()
        if len(test_id) > test_id_width:
            if test_id_width <= len(ELLIPSIS):
                test_id = test_id[:test_id_width]
            else:
                test_id = test_id[:test_id_width - len(ELLIPSIS)] + ELLIPSIS

        uncolored_line = f'{namespace}::{test_id} {status_word}'
        padding = max(0, available_space - len(uncolored_line))

        colored_status = f'{color_code}{status_word}{Fore.RESET}'
        colored_line = f"{namespace}::{test_id} {colored_status}"
        
        line = f"{colored_line}{' ' * padding} {colored_percent_str}"
        
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
        res = self.rescls(stream=self.stream, verbosity=self.verbosity, total_cnt=total, failfast=self.failfast)
        cols = shutil.get_terminal_size()[0]
        
        self.stream.writeln(f'{Style.BRIGHT}collected {total} items{Style.RESET_ALL}')
        if total == 0:
            self.stream.writeln()
            self.stream.writeln(f"{Fore.YELLOW}{' no tests ran in 0.00s '.center(cols, '=')}{Fore.RESET}")
            self.stream.flush()
            return res

        t0 = time.perf_counter()
        start_run = getattr(res, "startTestRun", None)
        if start_run is not None:
            start_run()
        try:
            suite(res)
        finally:
            stop_run = getattr(res, "stopTestRun", None)
            if stop_run is not None:
                stop_run()
        elapsed = time.perf_counter() - t0
        res.printErrors()
    
        counters = [
            ("errors", "errors"),
            ("failures", "failed"), 
            ("expectedFailures", "expected failures"),
            ("unexpectedSuccesses", "unexpected successes"),
            ("skipped", "skipped"),
        ]

        count_data = [
            (getattr(res, attr), label)
            for attr, label in counters
            if getattr(res, attr)
        ]

        summary_parts = [f"{len(counter)} {label}" for counter, label in count_data]
        failed_total = sum(len(counter) for counter, _ in count_data)
        num_passed = res.testsRun - failed_total

        passed_text = f"{num_passed} passed" if num_passed else "no passed"
        summary = f" {', '.join(summary_parts + [passed_text])} in {elapsed:.3f}s "

        term_color = Fore.GREEN if num_passed == res.testsRun else Fore.RED
        self.stream.writeln(f"{term_color}{summary.center(cols, '=')}{Fore.RESET}")
        self.stream.flush()

        return res


def make_test_suite(data_source, ruleset):
    test_suite = unittest.TestSuite()
    test_loader = unittest.TestLoader()

    extra_attrs = dict(_ExpressionEvaluator=_ExpressionEvaluator(data_source), data_source=data_source)
    for namespace in ruleset:
        test_case_cls_name = f'Test-{namespace}'
        rule_nodes = ruleset[namespace]
        test_case_cls = _make_test_case(test_case_cls_name, rule_nodes)

        # add extra attrs to test cls
        extra_attrs['namespace'] = namespace
        for name, value in extra_attrs.items():
            setattr(test_case_cls, name, value)

        suite = test_loader.loadTestsFromTestCase(test_case_cls)
        test_suite.addTest(suite)

    return test_suite


def _make_test_case(cls_name, rule_nodes: Set[_ast.Rule]):
    cls_dict = {
        f"test_{rule_node.lineno}": _make_test_method(rule_node)
        for rule_node in rule_nodes
    }
    test_case_cls = type(cls_name, (unittest.TestCase,), cls_dict)

    return test_case_cls


def _make_test_method(rule_node: _ast.Rule):
    def test(inst):
        if not inst._ExpressionEvaluator.evaluate(rule_node.test):
            history = inst._ExpressionEvaluator.history
            raise RuleAssertionError(rule_node, history)

    return test
