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

import argparse
import ast
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import _ast
from ._test import make_test_suite, RuleTestRunner
from .data_source import DataSource, NAType
from .parser import Parser
from .util import load_from_file, ParseFormat, ParseFormatError
from .visitor import (
    AssignmentProcessor,
    ASTFormatter,
    EnvScriptGenerator,
    InfoCollector,
    RuleCollector,
)


LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
LOG_FORMAT = "[%(levelname)s] [%(name)s] %(message)s"

logger = logging.getLogger(__name__)

_DEFAULT_ENV_SCRIPT = Path("set_env.sh")


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class CmateError(Exception):
    """Base class for all cmate errors."""


class ConfigError(CmateError):
    """Raised when a config file cannot be parsed or loaded."""


class ValidationError(CmateError):
    """Raised when dependency validation fails (missing targets / contexts)."""


class RuleCollectionError(CmateError):
    """Raised when rule collection fails due to unresolved namespace references."""


class RuleSyntaxError(CmateError):
    """Raised when rule file syntax validation fails (e.g., wrong extension)."""


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


def _parse_configs(
    configs: Optional[List[str]],
) -> Dict[str, Tuple[Optional[Path], ParseFormat]]:
    """
    Parse '-c' arguments of the form '<name>:<path>[@<parse_format>]' or 'env'.

    Raises:
        ValueError: If an entry is not of the expected form.
        ParseFormatError: If an unsupported parse format is specified.
    """
    result = {}
    if not configs:
        return result

    for entry in configs:
        if entry == "env":
            result["env"] = (None, ParseFormat.UNKNOWN)
            continue

        parts = entry.split(":", 1)
        if len(parts) != 2:
            raise ValueError(
                f"`configs` expected '<name>:<path>[@<parse_format>]' or 'env', got: {entry!r}"
            )

        name = parts[0]
        fields = parts[1].split("@", 1)
        path = Path(fields[0])
        parse_format = ParseFormat.UNKNOWN

        if len(fields) == 2:
            try:
                parse_format = ParseFormat(fields[1])
            except ValueError as e:
                raise ParseFormatError(
                    f"Unsupported parse format: {fields[1]!r}. "
                    f"Supported: {list(ParseFormat.__members__)}"
                ) from e

        result[name] = (path, parse_format)

    return result


def _parse_contexts(contexts: Optional[List[str]]) -> Dict[str, Any]:
    """
    Parse '-C' arguments of the form '<name>:<value>'.

    Raises:
        ValueError: If an entry is not of the expected form.
    """
    result = {}
    if not contexts:
        return result

    for entry in contexts:
        parts = entry.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"`contexts` expected '<name>:<value>', got: {entry!r}")

        name, raw = parts
        if name in result:
            logger.warning("Duplicate context name: %r – overwritten.", name)

        try:
            result[name] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            result[name] = raw

    return result


def _parse_lines(lines: Optional[str]) -> Optional[set]:
    """
    Parse '-k' argument of comma-separated line numbers.

    Args:
        lines: Comma-separated line numbers string (e.g., '10,20,30').

    Returns:
        Set of line numbers to filter, or None if no filter specified.
    """
    if not lines:
        return None

    result = set()
    for part in lines.split(","):
        part = part.strip()
        if part:
            try:
                result.add(int(part))
            except ValueError:
                logger.warning("Invalid line number %r – skipped.", part)
    return result if result else None


# ---------------------------------------------------------------------------
# Dependency validation and data loading
# ---------------------------------------------------------------------------


def _load_dependencies(
    info: Dict[str, Any],
    input_targets: Dict[str, Tuple[Path, ParseFormat]],
    input_contexts: Dict[str, str],
) -> DataSource:
    """
    Validate supplied targets/contexts and load them into a DataSource.

    Raises:
        ValidationError: If no recognised targets are supplied, or required
                         dependencies are missing.
        ConfigError: If a config file cannot be read or parsed (propagated
                     from _load_targets).
    """
    all_targets = info["targets"]
    all_contexts = info["contexts"]
    data_source = DataSource()

    matched = _load_targets(input_targets, all_targets, data_source)

    if not matched:
        raise ValidationError(
            f"No recognised targets supplied. "
            f"The rule file supports: {list(all_targets.keys())}"
        )

    missing = _collect_missing(matched, input_targets, input_contexts, all_targets)
    if missing:
        raise ValidationError(_format_missing(missing, all_targets, all_contexts))

    _load_contexts(input_contexts, all_contexts, data_source)
    return data_source


def _load_targets(
    input_targets: Dict[str, Tuple[Path, ParseFormat]],
    all_targets: Dict[str, Dict[str, Any]],
    data_source: DataSource,
) -> List[str]:
    """
    Load each recognised target into data_source and return the matched names.

    Raises:
        ConfigError: If a target file cannot be read or parsed.
    """
    matched = []
    for target, (path, parse_format) in input_targets.items():
        if target not in all_targets:
            logger.warning(
                "Target %r not defined in the rule file – skipped. Known targets: %s",
                target,
                list(all_targets.keys()),
            )
            continue

        matched.append(target)

        if target == "env":
            data_source.flatten("env", dict(os.environ))
            continue

        effective_format = parse_format or all_targets[target].get("parse_format")
        try:
            data = load_from_file(path, effective_format)
        except (OSError, ParseFormatError) as e:
            raise ConfigError(
                f"Failed to load target {target!r} from {path}: {e}"
            ) from e

        data_source.flatten(target, data)

    return matched


def _collect_missing(
    matched: List[str],
    input_targets: Dict[str, Any],
    input_contexts: Dict[str, str],
    all_targets: Dict[str, Dict[str, List[str]]],
) -> Dict[str, Dict[str, List[str]]]:
    """Return a dict of targets that have unsatisfied dependencies."""
    missing = {}
    for target in matched:
        info = all_targets[target]
        required_targets = info.get("required_targets") or []
        required_contexts = info.get("required_contexts") or []

        absent_targets = [
            target for target in required_targets if target not in input_targets
        ]
        absent_contexts = [
            context for context in required_contexts if context not in input_contexts
        ]

        if absent_targets or absent_contexts:
            missing[target] = {
                "targets": absent_targets,
                "contexts": absent_contexts,
            }
    return missing


def _format_missing(
    missing: Dict[str, Dict[str, List[str]]],
    all_targets: Dict[str, Dict[str, Any]],
    all_contexts: Dict[str, Dict[str, Any]],
) -> str:
    """Format missing-dependency info as a human-readable string."""
    parts = []
    for target, m in missing.items():
        parts.append(f"Target {target!r} is missing required dependencies:")

        for t in m["targets"]:
            desc = all_targets.get(t, {}).get("desc") or "No description available."
            parts.append(f"  - {t}: {desc}")
        for c in m["contexts"]:
            ctx = all_contexts.get(c, {})
            raw = ctx.get("desc")
            # Handle both new format (string) and legacy format (tuple)
            if isinstance(raw, tuple):
                desc = raw[0]
            else:
                desc = raw or "No description."
            opts = ctx.get("options", []) or "No options available."
            parts.append(f"  - {c}: {opts}")
            parts.append(f"      {desc}")
        parts.append("")

    parts.append(
        "Resolve with:\n"
        "  -c <target>:<path>   to supply a missing config target\n"
        "  -C <context>:<value> to supply a missing context variable"
    )
    return "\n".join(parts)


def _load_contexts(
    input_contexts: Dict[str, str],
    all_contexts: Dict[str, Dict[str, Any]],
    data_source: DataSource,
) -> None:
    """Write recognised context values into data_source; warn and skip others."""
    for ctx, value in input_contexts.items():
        if ctx not in all_contexts:
            logger.warning(
                "Context %r not defined in rule file – skipped. Known: %s",
                ctx,
                list(all_contexts.keys()),
            )
            continue
        data_source[f"context::{ctx}"] = value


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _display_text(info: Dict[str, Any]) -> None:
    """Display rule file info in human-readable format."""
    for attr in ("metadata", "targets", "contexts"):
        if attr not in info:
            raise KeyError(f"Required key {attr!r} missing from info dict.")

    _print_section("Overview")
    if info["metadata"]:
        for k, v in info["metadata"].items():
            _print_field(k, v or "", indent=1)
    else:
        print("No overview available")
    print("\n")

    _print_section("Context Variables")
    if info["contexts"]:
        for var, ctx in info["contexts"].items():
            desc = ctx["desc"]
            # Handle both new format (string) and legacy format (tuple)
            if isinstance(desc, tuple):
                desc = desc[0]
            if not desc:
                desc = "No description."
            _print_field(var, ctx["options"])
            print(f"    {desc}\n")
    else:
        print("\nNo contexts available.")
    print()

    _print_section("Config Targets")
    if info["targets"]:
        for name, tinfo in info["targets"].items():
            _print_section(name, level=2)
            desc = tinfo["desc"] or "No description."
            parse_format = tinfo["parse_format"] or "Unknown"
            req_targets = tinfo["required_targets"]
            req_contexts = tinfo["required_contexts"]

            if name == "env":
                _print_field("description", "Environment variable validation", indent=4)
            else:
                _print_field("type", parse_format, indent=4)
                _print_field("description", desc, indent=4)

            if req_targets:
                _print_field("required_targets", ", ".join(req_targets), indent=4)
            if req_contexts:
                _print_field("required_contexts", ", ".join(req_contexts), indent=4)
            print()
    else:
        print("\nNo config targets available.")
    print()

    print("Usage: -c <rule_name>:<file_path>  -C <context>:<value>\n")


def _display_json(info: Dict[str, Any]) -> None:
    """Display rule file info in JSON format."""
    print(json.dumps(info, indent=4, ensure_ascii=False))


def _print_section(title: str, level: int = 0) -> None:
    indent = "  " * level
    print(f"{indent}{title}\n{indent}{'-' * len(title)}")


def _print_field(label: str, value: Any, indent: int = 0) -> None:
    print(f"{'  ' * indent}{label} : {value}")


class _NAEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, NAType):
            return {"NAType": True}
        return super().default(obj)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(rule_path: Path) -> _ast.Document:
    """Parse a cmate rule file and return the Document AST node."""
    if not isinstance(rule_path, Path):
        rule_path = Path(rule_path)

    rule_path = rule_path.resolve()

    if not rule_path.exists():
        raise FileNotFoundError(f"Rule file not found: {rule_path}")
    if not rule_path.is_file():
        raise IsADirectoryError(f"Rule path is not a file: {rule_path}")
    if rule_path.suffix != ".cmate":
        raise RuleSyntaxError(
            f"Rule file must have .cmate extension, got: {rule_path.suffix!r}"
        )

    return Parser().parse(rule_path.read_text(encoding="utf-8"))


def inspect(rule_path: Path, output_format: str = "text") -> None:
    """Print human-readable or JSON information about a rule file."""
    formatters = {"text": _display_text, "json": _display_json}
    if output_format not in formatters:
        raise ValueError(f"Unsupported output format: {output_format!r}")

    node = parse(rule_path)
    info = InfoCollector().collect(node)
    formatters[output_format](info)


def run(
    rule_path: str,
    configs: Optional[List[str]] = None,
    contexts: Optional[List[str]] = None,
    failfast: bool = False,
    verbosity: bool = False,
    collect_only: bool = False,
    output_path: Optional[Path] = None,
    severity: str = "info",
    lines: Optional[str] = None,
) -> int:
    """Validate configurations against rules defined in a cmate rule file.

    Returns:
        0 on success, 1 on failure.

    Raises:
        ValueError, ParseFormatError: For malformed CLI arguments.
        FileNotFoundError, IsADirectoryError: If the rule file is missing.
        ValidationError: If required targets / contexts are absent.
        ConfigError: If a config file cannot be loaded.
        RuleCollectionError: If rule collection fails due to missing namespace.
    """
    parsed_configs = _parse_configs(configs)
    parsed_contexts = _parse_contexts(contexts)
    line_filter = _parse_lines(lines)

    node = parse(rule_path)
    info = InfoCollector().collect(node)

    data_source = _load_dependencies(info, parsed_configs, parsed_contexts)
    AssignmentProcessor(parsed_configs, data_source).process(node)

    if "env" in info["targets"]:
        env_script_path = Path("./set_env.sh").resolve()
        gen = EnvScriptGenerator(data_source)
        try:
            gen.collect(node)
            gen.write(env_script_path)
        except Exception:
            logger.warning("Failed to generate env script", exc_info=True)

    try:
        ruleset = RuleCollector(parsed_configs, data_source, severity).collect(node)
    except KeyError as e:
        raise RuleCollectionError(
            f"Rule collection failed – namespace {e} is referenced but not listed "
            "in dependencies or the partition section."
        ) from e

    # Apply line filter if specified
    total_rules = sum(len(rules) for rules in ruleset.values())
    if line_filter is not None:
        filtered_ruleset, deselected = _filter_rules_by_lines(ruleset, line_filter)
    else:
        filtered_ruleset = ruleset
        deselected = 0

    if collect_only:
        return _show_collected(filtered_ruleset, total_rules, deselected)

    return _execute(
        filtered_ruleset, data_source, failfast, verbosity, output_path, deselected
    )


def _filter_rules_by_lines(
    ruleset: Dict[str, set], line_filter: set
) -> Tuple[Dict[str, set], int]:
    """Filter rules by line numbers.

    Args:
        ruleset: Dictionary mapping namespace to set of rule nodes.
        line_filter: Set of line numbers to include.

    Returns:
        Tuple of (filtered ruleset, deselected count).
    """
    filtered = {}
    deselected = 0

    for ns, rules in ruleset.items():
        selected = set()
        for rule in rules:
            if rule.lineno in line_filter:
                selected.add(rule)
            else:
                deselected += 1
        if selected:
            filtered[ns] = selected

    return filtered, deselected


def _show_collected(
    ruleset: Dict[str, List[_ast.Rule]], total: int = 0, deselected: int = 0
) -> int:
    formatter = ASTFormatter()
    selected = sum(len(rules) for rules in ruleset.values())

    # Print pytest-style collection summary
    if deselected > 0:
        print(
            f"collected {total} items / {deselected} deselected / {selected} selected"
        )
        if selected == 0:
            print(f"\n{'=' * 60} {deselected} deselected {'=' * 60}")
            return 0
    else:
        print(f"collected {total} items")

    lines = []
    for ns, rules in ruleset.items():
        lines.append(f"<Target {ns}>")
        for rule in rules:
            lines.append(f"  <test_{rule.lineno} {formatter.format(rule)}>")
    print("\n".join(lines))
    return 0


def _execute(
    ruleset: Dict[str, List[_ast.Rule]],
    data_source: DataSource,
    failfast: bool,
    verbosity: bool,
    output_path: Optional[Path],
    deselected: int = 0,
) -> int:
    runner = RuleTestRunner(
        failfast=failfast, verbosity=verbosity, deselected=deselected
    )
    result_log: dict = {}
    suite = make_test_suite(data_source, ruleset, result_log)
    result = runner.run(suite)

    if output_path:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        output_path.mkdir(mode=0o750, parents=True, exist_ok=True)

        out_file = output_path / f"cmate_{ts}_output.json"
        out_file.write_text(
            json.dumps(result_log, cls=_NAEncoder, ensure_ascii=False, indent=4)
        )

    return 0 if result.wasSuccessful() else 1


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def setup_cmate_parser(
    subparser: argparse._SubParsersAction,
    parents: List[argparse.ArgumentParser] = [],
) -> None:
    """Register cmate subcommands into an existing subparser container.

    Intended for callers that want to embed cmate inside their own argument
    parser.  The caller creates the top-level parser and calls
    ``add_subparsers``; the resulting action object is passed here together
    with an optional list of parent parsers that contribute shared / global
    options (e.g. ``--log-level`` or a positional ``rule`` argument already
    defined by the host application).

    The function always prepends its own internal *cmate global* parent parser
    (which adds ``-l/--log-level`` and the ``rule`` positional) to whatever
    ``parents`` the caller supplies, so duplicate definitions should be
    avoided.

    Args:
        subparser: The ``_SubParsersAction`` returned by
            ``ArgumentParser.add_subparsers()``.  The ``run`` and ``inspect``
            subcommands are registered into this container.
        parents: Additional parent parsers whose arguments are inherited by
            every cmate subcommand.  Defaults to an empty list.
    """
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "-l",
        "--log-level",
        choices=LOG_LEVELS,
        default="error",
        help="Logging verbosity",
    )
    global_parser.add_argument("rule", type=Path, help="Path to the cmate rule file")

    all_parents = [global_parser] + list(parents)

    # -- run -----------------------------------------------------------------
    run_parser = subparser.add_parser(
        "run", parents=all_parents, help="Validate configurations against rules"
    )
    run_parser.add_argument(
        "--configs",
        "-c",
        nargs="*",
        help="Config files: '<name>:<path>[@<type>]' or 'env'",
    )
    run_parser.add_argument(
        "--contexts", "-C", nargs="*", help="Context variables: '<name>:<value>'"
    )
    run_parser.add_argument(
        "-co",
        "--collect-only",
        action="store_true",
        help="List rules without executing them",
    )
    run_parser.add_argument(
        "--output-path", type=Path, help="Directory for the JSON result file"
    )
    run_parser.add_argument(
        "-x",
        "--fail-fast",
        action="store_true",
        dest="failfast",
        help="Stop on first failure",
    )
    run_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        help="Verbose test output",
    )
    run_parser.add_argument(
        "-s",
        "--severity",
        choices=["info", "warning", "error"],
        default="info",
        help="Minimum severity to execute (default: info)",
    )
    run_parser.add_argument(
        "-k",
        "--lines",
        type=str,
        help="Comma-separated line numbers to run (e.g., '10,20,30')",
    )

    # -- inspect -------------------------------------------------------------
    inspect_parser = subparser.add_parser(
        "inspect", parents=all_parents, help="Show rule file requirements"
    )
    inspect_parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the cmate command-line tool."""
    parser = argparse.ArgumentParser(
        prog="cmate",
        description="CMATE – Configuration Management and Testing Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=False)
    setup_cmate_parser(subparsers)

    parsed = parser.parse_args(args)
    if not parsed.command:
        parser.print_help()
        return 1

    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVELS[parsed.log_level])

    # All CmateError subclasses represent expected, user-facing failures.
    # Everything else is an unexpected bug and gets a full traceback.
    if parsed.command == "inspect":
        try:
            inspect(parsed.rule, parsed.format)
        except (OSError, ValueError, CmateError):
            logger.exception("%s")
            return 1
        except Exception:
            logger.exception("Unexpected error during inspect")
            return 1
        return 0

    # run
    try:
        return run(
            parsed.rule,
            parsed.configs,
            parsed.contexts,
            parsed.failfast,
            parsed.verbose,
            parsed.collect_only,
            parsed.output_path,
            parsed.severity,
            parsed.lines
        )
    except (OSError, ValueError, ParseFormatError, CmateError):
        logger.exception("Error during run")
        return 1
    except Exception:
        logger.exception("Unexpected error during run")
        return 1
