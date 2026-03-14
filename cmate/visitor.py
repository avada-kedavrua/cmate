import builtins as _builtins
import inspect
import logging
import operator
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from . import _ast, custom_fn
from .data_source import DataSource, NA
from .util import func_timeout, Severity


logger = logging.getLogger(__name__)


class CMateError(Exception):
    pass


def _iter_nodes(node: _ast.Node):
    """Yield all AST nodes in *node*'s subtree (depth-first)."""
    if not isinstance(node, _ast.Node):
        return
    yield node
    if hasattr(node, "__slots__"):
        for attr in node.__slots__:
            child = getattr(node, attr, None)
            if isinstance(child, _ast.Node):
                yield from _iter_nodes(child)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, _ast.Node):
                        yield from _iter_nodes(item)


class ErrorResult:
    """Sentinel class for evaluation errors."""

    def __init__(self, lineno: int, col_offset: int, err_msg: str):
        self.lineno = lineno
        self.col_offset = col_offset
        self.err_msg = err_msg

    def __repr__(self):
        return f"<ErrorResult: {self.err_msg} at line {self.lineno}, column {self.col_offset}>"

    def __bool__(self):
        return False


class NodeVisitor:
    """
    Dispatch visit(node) to visit_<classname>(node).
    Falls back to generic_visit which recurses into child nodes.
    """

    def visit(self, node):
        if node is None:
            return None
        method = f"visit_{type(node).__name__.lower()}"
        return getattr(self, method, self.generic_visit)(node)

    def generic_visit(self, node):
        if node is None or not hasattr(node, "__slots__"):
            return None
        for attr in node.__slots__:
            val = getattr(node, attr, None)
            if isinstance(val, _ast.Node):
                self.visit(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, _ast.Node):
                        self.visit(item)


class _ExpressionEvaluator(NodeVisitor):
    """
    Evaluate an expression AST node to a Python value.

    Namespace resolution is provided by a *resolver* callable rather than
    mutating DictPath nodes, so the AST stays immutable.

        resolver(namespace: str | None, path: str) -> str
            Returns the fully-qualified 'ns::path' key to look up in data_source.
    """

    _BINARY_OPS = {
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
        "==": operator.eq,
        "!=": operator.ne,
        "=~": lambda a, b: func_timeout(3, re.search, b, a),
        "or": lambda a, b: a or b,
        "and": lambda a, b: a and b,
        "in": lambda a, b: a in b,
        "not in": lambda a, b: a not in b,
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        "//": operator.floordiv,
        "%": operator.mod,
        "**": operator.pow,
    }

    _UNARY_OPS = {
        "not": operator.not_,
    }

    _BUILTIN_FN = {
        name: getattr(_builtins, name)
        for name in (
            "int",
            "float",
            "bool",
            "str",
            "list",
            "tuple",
            "set",
            "len",
            "range",
            "sum",
            "min",
            "max",
        )
    }

    def __init__(self, data_source: DataSource, resolver=None):
        self._data_source = data_source
        # resolver(namespace, path) -> canonical 'ns::path' string
        self._resolver = resolver or self._default_resolver
        self._func_map = {**self._BUILTIN_FN, **self._load_custom_fn()}
        self.history: list = []

    @staticmethod
    def _default_resolver(namespace, path) -> str:
        ns = namespace if namespace is not None else "global"
        return f"{ns}::{path}"

    @staticmethod
    def _load_custom_fn() -> dict:
        result = {}
        for name in dir(custom_fn):
            if name.startswith("_"):
                continue
            obj = getattr(custom_fn, name)
            if inspect.isfunction(obj) and obj.__module__ == custom_fn.__name__:
                result[name] = obj
        return result

    # -- visit methods -------------------------------------------------------

    def visit_name(self, node: _ast.Name):
        raise CMateError(
            f"Direct variable reference is not allowed at line {node.lineno}, "
            f"column {node.col_offset}. "
            f"Use the interpolation syntax: ${{{node.id}}}"
        )

    def visit_constant(self, node: _ast.Constant):
        return node.value

    def visit_dictpath(self, node: _ast.DictPath):
        key = self._resolver(node.namespace, node.path)
        val = self._data_source[key]
        self.history.append((key, val))
        return val[0] if isinstance(val, tuple) else val

    def visit_list(self, node: _ast.List):
        result = []
        for elt in node.elts:
            val = self.visit(elt)
            if isinstance(val, ErrorResult):
                return val
            result.append(val)
        return result

    def visit_tuple(self, node: _ast.Tuple):
        result = []
        for elt in node.elts:
            val = self.visit(elt)
            if isinstance(val, ErrorResult):
                return val
            result.append(val)
        return tuple(result)

    def visit_dict(self, node: _ast.Dict):
        keys = []
        for k in node.keys:
            val = self.visit(k)
            if isinstance(val, ErrorResult):
                return val
            keys.append(val)
        values = []
        for v in node.values:
            val = self.visit(v)
            if isinstance(val, ErrorResult):
                return val
            values.append(val)
        return dict(zip(keys, values))

    def visit_compare(self, node: _ast.Compare):
        # For single comparison with regex match, return the match object
        if len(node.ops) == 1 and node.ops[0] == "=~":
            left = self.visit(node.left)
            if isinstance(left, ErrorResult):
                return left
            right = self.visit(node.comparators[0])
            if isinstance(right, ErrorResult):
                return right
            op = self._BINARY_OPS["=~"]
            try:
                return op(left, right)
            except TimeoutError as exc:
                return ErrorResult(node.lineno, node.col_offset, str(exc))

        left = self.visit(node.left)
        if isinstance(left, ErrorResult):
            return left
        for op_str, comparator_node in zip(node.ops, node.comparators):
            right = self.visit(comparator_node)
            if isinstance(right, ErrorResult):
                return right
            op = self._BINARY_OPS[op_str]
            try:
                if not op(left, right):
                    return False
            except Exception as exc:
                return ErrorResult(node.lineno, node.col_offset, str(exc))
            left = right
        return True

    def visit_binop(self, node: _ast.BinOp):
        left = self.visit(node.left)
        if isinstance(left, ErrorResult):
            return left
        right = self.visit(node.right)
        if isinstance(right, ErrorResult):
            return right
        op = self._BINARY_OPS[node.op]
        try:
            return op(left, right)
        except Exception as exc:
            return ErrorResult(node.lineno, node.col_offset, str(exc))

    def visit_unaryop(self, node: _ast.UnaryOp):
        op = self._UNARY_OPS.get(node.op)
        if op is None:
            raise CMateError(f"Unknown unary operator: {node.op!r}")
        operand = self.visit(node.operand)
        if isinstance(operand, ErrorResult):
            return operand
        try:
            return op(operand)
        except Exception as exc:
            return ErrorResult(node.lineno, node.col_offset, str(exc))

    def visit_call(self, node: _ast.Call):
        func = self._func_map.get(node.func.id)
        if func is None:
            raise CMateError(
                f"Undefined function {node.func.id!r} at line {node.lineno}, "
                f"column {node.col_offset}. "
                "Add it to `custom_fn.py` to use it."
            )
        args = []
        for a in node.args:
            val = self.visit(a)
            if isinstance(val, ErrorResult):
                return val
            args.append(val)
        try:
            return func(*args)
        except Exception as exc:
            return ErrorResult(node.lineno, node.col_offset, str(exc))

    # -- public entry point --------------------------------------------------

    def evaluate(self, node: _ast.Node):
        self.history = []
        return self.visit(node)


class _StatementExecutor(NodeVisitor):
    """
    Abstract base for visitors that *execute* statement nodes (For, If,
    Break, Continue).  Subclasses override visit_assign or visit_rule;
    everything else is handled here once.

    No AST mutation: DictPath namespace resolution is done via
    _make_resolver(), which returns a closure capturing current scope.
    """

    def __init__(self, data_source: DataSource):
        self._data_source = data_source
        self._in_loop = False
        self._break = False
        self._continue = False
        # Stack of (loop_var_name, loop_reference_label) for nested loops
        self._loop_stack: list[tuple[str, str]] = []

    # -- must override -------------------------------------------------------

    def _make_evaluator(self) -> _ExpressionEvaluator:
        """Return an evaluator wired to the current resolver."""
        raise NotImplementedError

    # -- loop / branch control -----------------------------------------------

    def visit_if(self, node: _ast.If):
        evaluator = self._make_evaluator()
        if evaluator.evaluate(node.test):
            self._exec_body(node.body)
        elif node.orelse:
            self._exec_body(node.orelse)

    def visit_for(self, node: _ast.For):
        evaluator = self._make_evaluator()
        iterable = evaluator.evaluate(node.it)

        # Determine if this is a tuple unpacking case
        is_tuple_unpack = isinstance(node.target, _ast.Tuple)

        if is_tuple_unpack:
            loop_vars = [n.id for n in node.target.elts]
            expected_count = len(loop_vars)
            # For dict iteration, we need to iterate over items
            if isinstance(iterable, dict):
                iterable = list(iterable.items())
        else:
            loop_var = node.target.id

        # For inline iterables store value temporarily under a generated key;
        # clean it up in a finally block so global scope is not polluted.
        if isinstance(node.it, _ast.DictPath):
            ref_label = ASTFormatter().format(node.it)
            temp_key = None
        else:
            ref_label = f"__loop_{node.lineno}_{node.col_offset}__"
            temp_key = f"global::{ref_label}"
            self._data_source[temp_key] = iterable

        saved_in_loop = self._in_loop
        self._in_loop = True

        try:
            for i, item in enumerate(iterable):
                if is_tuple_unpack:
                    # Validate unpacking
                    try:
                        iter(item)
                        item_list = list(item)
                    except TypeError:
                        item_type = type(item).__name__
                        raise CMateError(
                            f"cannot unpack non-iterable {item_type} object",
                            f"at line {node.lineno}, column {node.col_offset}",
                        )

                    actual_count = len(item_list)
                    if actual_count < expected_count:
                        raise CMateError(
                            f"not enough values to unpack "
                            f"at line {node.lineno}, column {node.col_offset}",
                            f"(expected {expected_count}, got {actual_count})",
                        )
                    if actual_count > expected_count:
                        raise CMateError(
                            f"at line {node.lineno}, column {node.col_offset}",
                            f"too many values to unpack (expected {expected_count})",
                        )

                    # Create a dict for all loop variables
                    loop_dict = dict(zip(loop_vars, item_list))
                    item_ref = f"{ref_label}[{i}]"
                    # Push all variables onto the loop stack
                    for var in loop_vars:
                        self._loop_stack.append((var, f"{item_ref}.{var}"))
                    self._data_source.flatten("global", loop_dict)

                    self._exec_body(node.body)

                    self._data_source.unflatten("global", loop_dict)
                    # Pop all variables from the loop stack
                    for _ in loop_vars:
                        self._loop_stack.pop()
                else:
                    item_ref = f"{ref_label}[{i}]"
                    self._loop_stack.append((loop_var, item_ref))
                    self._data_source.flatten("global", {loop_var: item})

                    self._exec_body(node.body)

                    self._data_source.unflatten("global", {loop_var: item})
                    self._loop_stack.pop()

                if self._break:
                    self._break = False
                    break
                if self._continue:
                    self._continue = False
        finally:
            self._in_loop = saved_in_loop
            if temp_key and temp_key in self._data_source:
                del self._data_source[temp_key]

    def visit_break(self, node: _ast.Break):
        if not self._in_loop:
            raise CMateError("'break' outside loop")
        self._break = True

    def visit_continue(self, node: _ast.Continue):
        if not self._in_loop:
            raise CMateError("'continue' not properly in loop")
        self._continue = True

    # -- helpers -------------------------------------------------------------

    def _exec_body(self, stmts: list):
        """Execute a list of statements, stopping on break/continue."""
        for stmt in stmts:
            self.visit(stmt)
            if self._break or self._continue:
                break

    def _current_loop_var(self) -> Optional[Tuple[str, str]]:
        """Return (loop_var_name, ref_label) for the innermost loop, or None."""
        return self._loop_stack[-1] if self._loop_stack else None


# ---------------------------------------------------------------------------
# Namespace resolver factory
# ---------------------------------------------------------------------------


def _make_partition_resolver(namespace: str, data_source: DataSource, loop_stack: list):
    """
    Returns a resolver function for use inside a partition.

    Resolution order for an unqualified path:
      1. If the path is the current loop variable, rewrite to the indexed ref.
      2. If 'global::path' exists in data_source (explicitly assigned in global),
         use global.
      3. Otherwise use the partition namespace (e.g., env::, mies_config::).

    This ensures variables like env::NPU_MEMORY_FRACTION display correctly
    instead of falling back to global:: when not found.
    """

    def resolver(ns: Optional[str], path: str) -> str:
        if ns is not None:
            return f"{ns}::{path}"

        # Check if this path is a loop variable (innermost wins)
        for loop_var, ref_label in reversed(loop_stack):
            if path == loop_var:
                return f"global::{ref_label}"

        # Check if explicitly defined in global (assigned in [global] section)
        global_key = f"global::{path}"
        if global_key in data_source:
            return global_key

        # Otherwise use the partition namespace
        return f"{namespace}::{path}"

    return resolver


# ---------------------------------------------------------------------------
# Concrete visitors
# ---------------------------------------------------------------------------


class AssignmentProcessor(_StatementExecutor):
    """
    Walks the [global] section and evaluates assignments into data_source.
    Skips partitions entirely.

    """

    def __init__(self, input_configs: dict, data_source: DataSource):
        super().__init__(data_source)
        self._input_configs = input_configs
        self._formatter = ASTFormatter()

    def _make_evaluator(self) -> _ExpressionEvaluator:
        return _ExpressionEvaluator(self._data_source)

    # -- section gates -------------------------------------------------------

    def visit_meta(self, node):
        pass

    def visit_target(self, node):
        pass

    def visit_context(self, node):
        pass

    def visit_partition(self, node):
        pass

    def visit_global(self, node: _ast.Global):
        self._exec_body(node.body)

    # -- assignments ---------------------------------------------------------

    def visit_assign(self, node: _ast.Assign):
        # Check whether the RHS references an unavailable namespace
        if self._rhs_references_missing_target(node.value):
            return

        target = node.target.id
        evaluator = self._make_evaluator()
        try:
            value = evaluator.evaluate(node.value)
        except Exception as exc:
            formatted = self._formatter.format(node.value)
            logger.warning(
                "Failed to assign %r to %r at line %d, column %d – skipped.",
                formatted,
                target,
                node.lineno,
                node.col_offset,
                exc_info=exc,
            )
            return

        self._data_source.flatten("global", {target: value})

        # Store (value, reference) tuple so evaluator history is informative
        ref = self._formatter.format(node.value)
        if self._loop_stack:
            _, loop_ref = self._loop_stack[-1]
            self._data_source[f"global::{target}"] = (value, loop_ref)
        elif ref != str(value):
            self._data_source[f"global::{target}"] = (value, ref)

    def _rhs_references_missing_target(self, node: _ast.Node) -> bool:
        """
        Return True (and log a warning) if any DictPath in *node* references
        a namespace that was not provided as an input config.
        """
        for n in _iter_nodes(node):
            if (
                isinstance(n, _ast.DictPath)
                and n.namespace not in {None, "global"}
                and n.namespace not in self._input_configs
            ):
                logger.warning(
                    "Assignment at line %d, column %d references namespace %r "
                    "which was not provided via -c. Skipped.",
                    n.lineno,
                    n.col_offset,
                    n.namespace,
                )
                return True
        return False

    def process(self, node):
        self.visit(node)


class RuleCollector(_StatementExecutor):
    """
    Walks partition sections and collects Rule nodes into a ruleset dict.
    Rules are filtered by minimum severity.
    Namespace resolution is done via a closure – the AST is never mutated.
    """

    def __init__(self, input_configs: dict, data_source: DataSource, severity: str):
        super().__init__(data_source)
        self._input_configs = input_configs
        self._min_severity = Severity[severity.upper()]
        self._namespace: str | None = None
        self._ruleset: dict[str, set] = defaultdict(set)

    def _make_evaluator(self) -> _ExpressionEvaluator:
        resolver = _make_partition_resolver(
            self._namespace, self._data_source, self._loop_stack
        )
        return _ExpressionEvaluator(self._data_source, resolver)

    # -- section gates -------------------------------------------------------

    def visit_meta(self, node):
        pass

    def visit_target(self, node):
        pass

    def visit_context(self, node):
        pass

    def visit_global(self, node):
        pass

    def visit_partition(self, node: _ast.Partition):
        if node.target.id not in self._input_configs:
            return
        self._namespace = node.target.id
        self._exec_body(node.body)
        self._namespace = None

    # -- rules ---------------------------------------------------------------

    def visit_rule(self, node: _ast.Rule):
        if self._min_severity > node.severity:
            return
        self._ruleset[self._namespace].add(node)

    def visit_alert(self, node: _ast.Alert):
        if self._min_severity > node.severity:
            return
        self._ruleset[self._namespace].add(node)

    def collect(self, node) -> dict:
        self.visit(node)
        return self._ruleset


class EnvScriptGenerator(_StatementExecutor):
    """
    Walk ``[par env]`` sections and produce a shell script that sets (or
    unsets) environment variables to the values expected by ``assert`` rules.

    Only ``==`` and ``in`` comparisons whose left-hand side is an
    environment-variable :class:`_ast.DictPath` are considered.  Control-flow
    nodes (``if``, ``for``) are evaluated so that context-dependent rules
    produce the correct commands.

    Typical usage::

        gen = EnvScriptGenerator(data_source)
        gen.collect(document_node)
        gen.write(Path("set_env.sh"))
    """

    _SAFE_VALUE = re.compile(r"[a-zA-Z0-9_\-:.;/,=+@%~]+")
    _VALID_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

    _SCRIPT_TEMPLATE = (
        "#!/bin/bash\n"
        "# Auto-generated by cmate\n"
        "# Usage:\n"
        "#   source {filename}    # Apply environment changes\n"
        "#   source {filename} 0  # Revert changes\n"
        "#\n"
        "# Variables: {set_count} exported, {unset_count} unset\n\n"
        'if [ "$1" = "0" ]; then\n'
        "    {undo}\n"
        "else\n"
        "    {set}\n"
        "fi\n"
    )

    def __init__(self, data_source: DataSource):
        super().__init__(data_source)
        self._environ: Dict[str, str] = os.environ.copy()
        self._set_lines: List[str] = []
        self._undo_lines: List[str] = []
        self._set_count = 0
        self._unset_count = 0

    def _make_evaluator(self) -> _ExpressionEvaluator:
        resolver = _make_partition_resolver("env", self._data_source, self._loop_stack)
        return _ExpressionEvaluator(self._data_source, resolver)

    # -- section gates -------------------------------------------------------

    def visit_meta(self, node: _ast.Meta) -> None:
        pass

    def visit_target(self, node: _ast.Target) -> None:
        pass

    def visit_context(self, node: _ast.Context) -> None:
        pass

    def visit_global(self, node: _ast.Global) -> None:
        pass

    def visit_partition(self, node: _ast.Partition) -> None:
        if node.target.id != "env":
            return
        self._exec_body(node.body)

    # -- rule processing -----------------------------------------------------

    def visit_assign(self, node: _ast.Assign) -> None:
        pass

    def visit_rule(self, node: _ast.Rule) -> None:
        test = node.test
        if not isinstance(test, _ast.Compare):
            return
        if len(test.ops) != 1:
            return
        if not isinstance(test.left, _ast.DictPath):
            return
        if test.left.namespace == "context":
            return

        env_var = test.left.path
        op = test.ops[0]
        comparator = test.comparators[0]
        evaluator = self._make_evaluator()

        if op == "==":
            expected = evaluator.evaluate(comparator)
        elif op == "in":
            val = evaluator.evaluate(comparator)
            if isinstance(val, (list, tuple)) and val:
                expected = val[0]
            else:
                return
        else:
            return

        self._add_env_command(env_var, expected, node.lineno, node.col_offset)

    def visit_alert(self, node: _ast.Alert) -> None:
        pass

    # -- command building ----------------------------------------------------

    def _add_env_command(
        self, env_var: str, expected: Any, lineno: int, col_offset: int
    ) -> None:
        if not self._VALID_ENV_NAME.fullmatch(env_var):
            logger.warning(
                "At line %d, column %d: %r is not a valid shell variable name.",
                lineno,
                col_offset,
                env_var,
            )
            return

        if expected is NA:
            self._set_lines.append(f"unset {env_var}")
            self._unset_count += 1
            return

        if expected is None:
            logger.warning(
                "At line %d, column %d: 'None' cannot unset environment "
                "variables. Use the special value 'NA' instead.",
                lineno,
                col_offset,
            )
            self._set_lines.append(f"unset {env_var}")
            self._unset_count += 1
            return

        if not isinstance(expected, str):
            logger.warning(
                "At line %d, column %d: non-str value cannot set "
                "environment variables.",
                lineno,
                col_offset,
            )
            return

        if not self._SAFE_VALUE.fullmatch(expected):
            logger.warning(
                "At line %d, column %d: unsafe value %r detected.",
                lineno,
                col_offset,
                expected,
            )
            return

        original = self._environ.get(env_var)
        self._set_lines.append(f'export {env_var}="{expected}"')
        self._set_count += 1
        if original is None:
            self._undo_lines.append(f"unset {env_var}")
        else:
            self._undo_lines.append(f'export {env_var}="{original}"')

    # -- output --------------------------------------------------------------

    def render(self, filename: str = "set_env.sh") -> str:
        """Return the shell script content as a string."""
        set_cmds = self._set_lines or [":"]
        undo_cmds = self._undo_lines or [":"]
        return self._SCRIPT_TEMPLATE.format(
            filename=filename,
            set_count=self._set_count,
            unset_count=self._unset_count,
            set="\n    ".join(set_cmds),
            undo="\n    ".join(undo_cmds),
        )

    def collect(self, node: _ast.Document) -> None:
        """Walk the AST and collect environment variable commands."""
        self.visit(node)

    def write(self, path: Path) -> None:
        """Write the generated script to *path*."""
        path.write_text(self.render(path.name), encoding="utf-8")


class InfoCollector(NodeVisitor):
    """
    Collects metadata, target declarations, context definitions,
    and partition requirements without executing any expressions.

    syntax: [target] for config files, [context] for context variables
    """

    def __init__(self):
        self._metadata_map: Dict = {}
        self._target_map: Dict = {}
        self._context_def_map: Dict = {}
        self._partition_map: Dict = {}
        self._context_map: Dict[str, set] = defaultdict(set)  # Inferred options
        self._namespace: Optional[str] = None

    def visit_meta(self, node: _ast.Meta):
        if self._metadata_map:
            raise CMateError("Multiple [metadata] sections not allowed.")
        for assign in node.body:
            self._metadata_map[assign.target.id] = self._literal_value(assign.value)

    def visit_target(self, node: _ast.Target):
        """Handle new [targets] section for config file definitions."""
        if self._target_map:
            raise CMateError("Multiple [targets] sections not allowed.")
        for desc in node.body:
            name = desc.target.id
            if name == "env":
                raise CMateError(
                    f"'env' cannot be declared in [targets] section "
                    f"(line {desc.lineno}, column {desc.col_offset}). "
                    "The 'env' partition is built-in for environment variables."
                )
            if name in self._target_map:
                logger.warning(
                    "Target %r redefined at line %d, column %d.",
                    name,
                    desc.lineno,
                    desc.col_offset,
                )
            self._target_map[name] = (desc.desc, desc.parse_format)

    def visit_context(self, node: _ast.Context):
        """Handle new [contexts] section for context variable definitions."""
        if self._context_def_map:
            raise CMateError("Multiple [contexts] sections not allowed.")
        for desc in node.body:
            name = desc.target.id
            if name in self._context_def_map:
                logger.warning(
                    "Context %r redefined at line %d, column %d.",
                    name,
                    desc.lineno,
                    desc.col_offset,
                )
            # Context definitions don't have parse_format, just description
            self._context_def_map[name] = desc.desc

    def visit_global(self, node):
        pass

    def visit_partition(self, node: _ast.Partition):
        self._namespace = node.target.id
        required_targets: Set[str] = set()
        required_contexts: Set[str] = set()

        if self._namespace in self._partition_map:
            logger.warning(
                "Multiple [par %s] sections – earlier one overwritten.", self._namespace
            )

        for stmt in node.body:
            self._collect_deps(stmt, required_targets, required_contexts)

        # Validate partition is declared in [targets] or is 'env'
        if self._namespace != "env":
            if not self._target_map:
                raise CMateError(
                    f"Partition {self._namespace!r} requires a [targets] section."
                )

            if self._namespace not in self._target_map:
                raise CMateError(
                    f"Partition {self._namespace!r} must be declared in [targets] section."
                )

        # Get description and parse format from [target]
        desc = None
        parse_format = None
        if self._target_map and self._namespace in self._target_map:
            desc, parse_format = self._target_map[self._namespace]

        self._partition_map[self._namespace] = {
            "desc": desc,
            "parse_format": parse_format,
            "required_targets": sorted(required_targets) or None,
            "required_contexts": sorted(required_contexts) or None,
        }
        self._namespace = None

    def collect(self, node: _ast.Document) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Collect metadata, target declarations, and partition requirements."""
        try:
            self.visit(node)
        except Exception as exc:
            raise CMateError(f"Configuration parsing failed: {exc}") from exc

        # Validate that all context:: references are defined in [contexts] section
        # Only validate if [contexts] section is present
        if self._context_def_map:
            for var in self._context_map.keys():
                if var not in self._context_def_map:
                    raise CMateError(
                        f"Context variable {var!r} is used in rules but not declared "
                        "in [contexts] section."
                    )

        contexts = {}
        for var, opts in self._context_map.items():
            desc = self._context_def_map.get(var) if self._context_def_map else None
            contexts[var] = {"desc": desc, "options": sorted(opts)}

        return {
            "metadata": self._metadata_map,
            "targets": self._partition_map,
            "contexts": contexts,
        }

    # -- helpers -------------------------------------------------------------

    def _collect_deps(self, node, targets: set, contexts: set):
        """Walk *node* collecting namespace references using _iter_nodes()."""
        for child in _iter_nodes(node):
            # Collect context:: and target references from DictPath nodes
            if isinstance(child, _ast.DictPath):
                ns = child.namespace
                if ns is None or ns in {"global", "env"}:
                    continue
                # Determine the valid namespaces based on which section is used
                valid_namespaces = set()
                if self._target_map:
                    valid_namespaces.update(self._target_map.keys())
                valid_namespaces.add("context")

                if ns not in valid_namespaces:
                    logger.warning(
                        "Undefined namespace %r at line %d, column %d.",
                        ns,
                        child.lineno,
                        child.col_offset,
                    )
                if ns == "context":
                    contexts.add(child.path)
                    # Ensure context is tracked in _context_map for validation
                    # (defaultdict will create empty set if not exists)
                    _ = self._context_map[child.path]
                else:
                    targets.add(ns)

            # Detect 'context::var == <literal>' or '<literal> == context::var'
            # to populate context option sets for auto-detection
            elif isinstance(child, _ast.Compare) and len(child.comparators) > 0:
                left = child.left
                first_comp = child.comparators[0]
                # Pattern: context::var == <literal>
                if (
                    isinstance(left, _ast.DictPath)
                    and left.namespace == "context"
                    and isinstance(first_comp, _ast.Constant)
                ):
                    self._context_map[left.path].add(first_comp.value)
                # Pattern: <literal> == context::var (reversed)
                elif (
                    isinstance(first_comp, _ast.DictPath)
                    and first_comp.namespace == "context"
                    and isinstance(left, _ast.Constant)
                ):
                    self._context_map[first_comp.path].add(left.value)

    @staticmethod
    def _literal_value(node):
        """Extract a plain Python value from a Constant/List/Dict AST node."""
        if node is None:
            return None
        if isinstance(node, _ast.Constant):
            return node.value
        if isinstance(node, _ast.List):
            return [InfoCollector._literal_value(e) for e in node.elts]
        if isinstance(node, _ast.Dict):
            return dict(
                zip(
                    (InfoCollector._literal_value(k) for k in node.keys),
                    (InfoCollector._literal_value(v) for v in node.values),
                )
            )
        raise CMateError(f"Unsupported literal node: {type(node).__name__}")


# ---------------------------------------------------------------------------
# AST pretty-printer
# ---------------------------------------------------------------------------


class ASTFormatter(NodeVisitor):
    """Convert an AST node back to a human-readable string."""

    def visit_name(self, node: _ast.Name):
        return node.id

    def visit_constant(self, node: _ast.Constant):
        return repr(node.value) if isinstance(node.value, str) else node.value

    def visit_dictpath(self, node: _ast.DictPath):
        return node.path if node.namespace is None else f"{node.namespace}::{node.path}"

    def visit_list(self, node: _ast.List):
        return [self.visit(e) for e in node.elts]

    def visit_tuple(self, node: _ast.Tuple):
        return tuple(self.visit(e) for e in node.elts)

    def visit_dict(self, node: _ast.Dict):
        return dict(
            zip(
                (self.visit(k) for k in node.keys),
                (self.visit(v) for v in node.values),
            )
        )

    def visit_compare(self, node: _ast.Compare):
        parts = [str(self.visit(node.left))]
        for op, comp in zip(node.ops, node.comparators):
            parts.append(op)
            parts.append(str(self.visit(comp)))
        return " ".join(parts)

    def visit_binop(self, node: _ast.BinOp):
        return f"{self.visit(node.left)} {node.op} {self.visit(node.right)}"

    def visit_unaryop(self, node: _ast.UnaryOp):
        return f"{node.op} {self.visit(node.operand)}"

    def visit_call(self, node: _ast.Call):
        args = ", ".join(str(self.visit(a)) for a in node.args)
        return f"{node.func.id}({args})"

    def visit_rule(self, node: _ast.Rule):
        return self.visit(node.test)

    def visit_alert(self, node: _ast.Alert):
        return self.visit(node.field)

    def format(self, node: _ast.Node):
        return self.visit(node)
