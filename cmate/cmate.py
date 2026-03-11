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

import os
import ast
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from . import _ast
from ._test import make_test_suite, RuleTestRunner
from .data_source import DataSource, NAType
from .parser import Parser
from .util import load
from .visitor import (
    AssignmentProcessor,
    ASTFormatter,
    EnvironmentScriptGenerator,
    InfoCollector,
    RuleCollector,
)

LOG_LEVELS = {
    "debug":    logging.DEBUG,
    "info":     logging.INFO,
    "warning":  logging.WARNING,
    "error":    logging.ERROR,
    "critical": logging.CRITICAL,
}
LOG_FORMAT = "[%(levelname)s] [%(name)s] %(message)s"


logger = logging.getLogger(__name__)


def _parse_configs(configs: Optional[List[str]]) -> Dict[str, Tuple[str, str]]:
    """
    Parse '-c' arguments of the form '<name>:<path>[@<parse_type>]' or 'env'.

    Args:
        configs (Optional[List[str]]): List of configs of the form '<name>:<path>[@<parse_type>]' or 'env'.

    Returns:
        Dict[str, Tuple[str, str]]: The parsed configs.
        
    Raises:
        ValueError: If a config is not of the form '<name>:<path>[@<parse_type>]' or 'env'.    
    """
    result = {}

    if not configs:
        return result

    for entry in configs:
        if entry == "env":
            result["env"] = (None, None)
            continue

        parts = entry.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"`configs` parameter expected to be a list of '<name>:<path>[@<parse_type>]' or 'env', got: {configs!r}")

        name = parts[0]
        fields = parts[1].split("@", 1)
        path = fields[0]
        parse_type = fields[1] if len(fields) == 2 else None
        result[name] = (path, parse_type)

    return result


def _parse_contexts(contexts: Optional[List[str]]) -> Dict[str, str]:
    """
    Parse '-C' arguments of the form '<name>:<value>'.
    
    Args:
        contexts (Optional[List[str]]): List of contexts of the form '<name>:<value>'.

    Returns:
        Dict[str, str]: The parsed contexts.
        
    Raises:
        ValueError: If a context is not of the form '<name>:<value>'.
    """
    result = {}
    if not contexts:
        return result

    for entry in contexts:
        parts = entry.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"`contexts` parameter expected to be a list of '<name>:<value>', got: {contexts!r}")

        name, raw = parts
        try:
            result[name] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            result[name] = raw

    return result


# ---------------------------------------------------------------------------
# Dependency validation and data loading
# ---------------------------------------------------------------------------

def _validate_and_load_dependencies(
    info: Dict[str, Any], input_targets: Dict[str, Tuple[str, str]], input_contexts: Dict[str, str]
) -> Tuple[bool, DataSource]:
    """
    Validate that the user supplied at least one recognised target, check that
    all required dependencies are present, then load files into a DataSource.
    """
    input_targets  = input_targets  or {}
    input_contexts = input_contexts or {}

    all_targets  = info["targets"]
    all_contexts = info["contexts"]
    data_source  = DataSource()

    ok, matched = _load_targets(input_targets, all_targets, data_source)
    if not ok:
        return False, data_source

    if not matched:
        logger.error(
            "No recognised targets supplied. The rule file supports: %s",
            list(all_targets.keys()),
        )
        return False, data_source

    missing = _collect_missing(matched, input_targets, input_contexts, all_targets)
    if missing:
        _log_missing(missing, all_targets, all_contexts)
        return False, data_source

    _load_contexts(input_contexts, all_contexts, data_source)
    return True, data_source


def _load_targets(input_targets: dict, all_targets: dict,
                  data_source: DataSource) -> Tuple[bool, list]:
    """Load targets from the user-supplied config files."""
    matched = []
    for target, (path, parse_type) in input_targets.items():
        if target not in all_targets:
            logger.warning(
                "Target %r not defined in the rule file – skipped. "
                "Known targets: %s", target, list(all_targets.keys())
            )
            continue

        matched.append(target)

        if target == "env":
            data_source.flatten("env", dict(os.environ))
            continue

        effective_parse_type = parse_type or all_targets[target].get("parse_type")
        try:
            data = load(path, effective_parse_type)
        except OSError:
            logger.error(
                "Target %r not found at %r. Check the path.", target, path
            )
            return False, matched
        except TypeError:
            logger.error(
                "Unsupported parse type %r for target %r at %r. "
                "Specify one with '-c %s:%s@<type>'.",
                effective_parse_type, target, path, target, path,
            )
            return False, matched
        except Exception:
            logger.exception(
                "Failed to parse target %r from %r.", target, path
            )
            return False, matched

        data_source.flatten(target, data)

    return True, matched


def _collect_missing(matched: List[str], input_targets: Dict[str, Tuple[str, str]], input_contexts: Dict[str, str],
                     all_targets: Dict[str, Dict[str, List[str]]]) -> Dict[str, Dict[str, List[str]]]:
    """Collect missing dependencies for the given targets and input configs."""
    missing = {}
    for target in matched:
        info = all_targets[target]
        req_targets  = info.get("required_targets")  or []
        req_contexts = info.get("required_contexts") or []

        absent_targets  = [t for t in req_targets  if t not in input_targets]
        absent_contexts = [c for c in req_contexts if c not in input_contexts]

        if absent_targets or absent_contexts:
            missing[target] = {
                "targets":  absent_targets,
                "contexts": absent_contexts,
            }
    return missing


def _log_missing(missing: Dict[str, Dict[str, List[str]]], all_targets: Dict[str, Dict[str, List[str]]], all_contexts: Dict[str, Dict[str, List[str]]]) -> None:
    """Log missing dependencies for the given targets and input configs."""
    parts = []
    for target, m in missing.items():
        parts.append(f"Target {target!r} is missing required dependencies:")
        for t in m["targets"]:
            info = all_targets.get(t, {})
            desc = info.get("desc") or "No description available."
            parts.append(f"  - {t}: {desc}")
        for c in m["contexts"]:
            info = all_contexts.get(c, {})
            ctx_desc = info.get("desc")
            desc = ctx_desc[0] if isinstance(ctx_desc, tuple) else "No description."
            opts = info.get("options", [])
            parts.append(f"  - {c}: {opts}")
            parts.append(f"      {desc}")
        parts.append("")

    parts.append(
        "Resolve with:\n"
        "  -c <target>:<path>   to supply a missing config target\n"
        "  -C <context>:<value> to supply a missing context variable"
    )
    logger.error("\n".join(parts))


def _load_contexts(input_contexts: Dict[str, str], all_contexts: Dict[str, Dict[str, List[str]]],
                   data_source: DataSource) -> None:
    """Load contexts from the user-supplied config files."""
    for ctx, value in input_contexts.items():
        if ctx not in all_contexts:
            logger.warning(
                "Context %r not defined in rule file – skipped. Known: %s",
                ctx, list(all_contexts.keys())
            )
            continue
        data_source[f"context::{ctx}"] = value


def _display_text(info: Dict[str, Any]) -> None:
    """Display rule file info in human-readable format."""
    for attr in ("metadata", "targets", "contexts"):
        if attr not in info:
            logger.critical("Required key %r missing from info dict.", attr)
            return
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
            desc = ctx["desc"][0] if isinstance(ctx["desc"], tuple) else "No description."
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
            parse_type = tinfo["parse_type"] or "Unknown"
            req_targets  = tinfo["required_targets"]
            req_contexts = tinfo["required_contexts"]

            if name == "env":
                _print_field("description", "Environment variable validation", indent=4)
            else:
                _print_field("type",        parse_type, indent=4)
                _print_field("description", desc,       indent=4)

            if req_targets:
                _print_field("required_targets",  ", ".join(req_targets),  indent=4)
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


def _print_section(title: str, level: int = 0):
    """Print a section header."""
    indent = "  " * level
    print(f"{indent}{title}\n{indent}{'-' * len(title)}")


def _print_field(label, value, indent: int = 0):
    """Print a field in the format: <label> : <value>."""
    print(f"{'  ' * indent}{label} : {value}")


class _NAEncoder(json.JSONEncoder):
    """JSON encoder that converts NAType instances to a dictionary."""
    def default(self, obj):
        if isinstance(obj, NAType):
            return {"NAType": True}
        return super().default(obj)


def parse(rule_path: Path) -> _ast.Document:
    """Parse a cmate rule file and return the Document AST node."""
    if not isinstance(rule_path, Path):
        rule_path = Path(rule_path)
    
    rule_path = rule_path.resolve()
    
    if not rule_path.is_file():
        raise OSError(f"Rule file is not a file: {rule_path}")

    return Parser().parse(rule_path.read_text(encoding="utf-8"))


def inspect(rule_path: Path, output_format: str = "text") -> None:
    """Print human-readable or JSON information about a rule file."""
    formatters = {"text": _display_text, "json": _display_json}
    if output_format not in formatters:
        raise ValueError(f"Unsupported output format: {output_format!r}")

    node = parse(rule_path)
    info = InfoCollector().collect(node)
    return formatters[output_format](info)


def run(
    rule_path: str,
    configs: Optional[List[str]] = None,
    contexts: Optional[List[str]] = None,
    failfast: bool = False,
    verbosity: bool = False,
    collect_only: bool = False,
    output_path: str = "",
    severity: str = "info",
) -> int:
    """Validate configurations against rules defined in a cmate rule file.
    
    Args:
        rule_path (str): Path to the cmate rule file. The rule file should be in the cmate rule language and follow the cmate syntax.
        configs (List[str]): List of config files to validate. Each config file should be in the format '<name>:<path>[@<type>]' or 'env'.
        contexts (List[str]): List of context variables to use. Each context variable should be in the format '<name>:<value>'.
        failfast (bool): Whether to stop validation on the first failure. If set to True, the validation will terminate immediately upon encountering the first failure.
        verbosity (bool): Whether to print verbose output. If set to True, the output will include more detailed information about the validation process.
        collect_only (bool): Whether to collect rules without executing them. If set to True, the tool will only collect the rules and display them in a human-readable format.
        output_path (str): Directory path for the JSON result file. If not specified, the result will be printed to stdout.
        severity (str): Minimum severity level of rules to execute. Valid values are "info", "warning", and "error". If not specified, all rules will be executed.
    
    Returns:
        int: 0 on success, 1 on failure.
    """
    configs = _parse_configs(configs)
    contexts = _parse_contexts(contexts)

    node = parse(rule_path)
    info = InfoCollector().collect(node)

    ok, data_source = _validate_and_load_dependencies(info, configs, contexts)
    if not ok:
        return 1

    AssignmentProcessor(configs or {}, data_source).process(node)

    try:
        ruleset = RuleCollector(configs or {}, data_source, severity).collect(node)
    except KeyError:
        logger.exception(
            "Rule collection failed – likely a namespace referenced without "
            "being listed in dependencies or the partition section."
        )
        return 1

    # Generate env script only when an env partition exists
    EnvironmentScriptGenerator(data_source).generate(node)

    if collect_only:
        return _show_collected(ruleset)

    return _execute(ruleset, data_source, failfast, verbosity, output_path)


def _show_collected(ruleset: Dict[str, List[_ast.Rule]]) -> int:
    """Display the collected rules in a human-readable format."""
    formatter = ASTFormatter()
    lines = []
    for ns, rules in ruleset.items():
        lines.append(f"<Namespace {ns}>")
        for rule in rules:
            lines.append(f"  <Rule-{rule.lineno} {formatter.format(rule)}>")
    logger.info("\n".join(lines))
    return 0


def _execute(ruleset: Dict[str, List[_ast.Rule]], data_source: DataSource,
             failfast: bool, verbosity: bool, output_path: str) -> int:
    """Execute the collected rules and return the result."""
    runner = RuleTestRunner(failfast=failfast, verbosity=verbosity)
    result_log: dict = {}
    suite = make_test_suite(data_source, ruleset, result_log)
    result = runner.run(suite)

    if output_path:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        os.makedirs(output_path, exist_ok=True)
        out_file = os.path.join(output_path, f"msprechecker_{ts}_output.json")
        with open_s(out_file, "w", encoding="utf-8") as f:
            json.dump(result_log, f, cls=_NAEncoder, ensure_ascii=False, indent=4)

    return 0 if result.wasSuccessful() else 1


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the cmate command-line tool."""
    parser = argparse.ArgumentParser(
        prog="cmate",
        description="CMATE – Configuration Management and Testing Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument("-l", "--log-level", choices=LOG_LEVELS, default="info",
                    help="Logging verbosity")
    global_parser.add_argument("rule", type=Path, help="Path to the cmate rule file")

    subparser = parser.add_subparsers(dest="command", required=False)

    # -- run -----------------------------------------------------------------
    run_parser = subparser.add_parser("run", parents=[global_parser], help="Validate configurations against rules")
    run_parser.add_argument("--configs", "-c", nargs="*",
                    help="Config files: '<name>:<path>[@<type>]' or 'env'")
    run_parser.add_argument("--contexts", "-C", nargs="*",
                    help="Context variables: '<name>:<value>'")
    run_parser.add_argument("-co", "--collect-only", action="store_true",
                    help="List rules without executing them")
    run_parser.add_argument("--output-path", type=Path,
                    help="Directory for the JSON result file")
    run_parser.add_argument("-x", "--fail-fast", action="store_true", dest="failfast",
                    help="Stop on first failure")
    run_parser.add_argument("-v", "--verbose", action="store_true", dest="verbose",
                    help="Verbose test output")
    run_parser.add_argument("-s", "--severity",
                    choices=["info", "warning", "error"], default="info",
                    help="Minimum severity to execute (default: info)")

    # -- inspect -------------------------------------------------------------
    inspect_parser = subparser.add_parser("inspect", parents=[global_parser], help="Show rule file requirements")
    inspect_parser.add_argument("--format", "-f", choices=["text", "json"], default="text",
                    help="Output format (default: text)")

    args = parser.parse_args(args)
    if not args.command:
        parser.print_help()
        return 1

    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVELS[args.log_level])
    if args.command == "inspect":
        try:
            inspect(args.rule, args.format)
        except (OSError, ValueError):
            logger.exception("Error inspecting rule file")
            return 1
        return 0

    return run(
        args.rule,
        args.configs,
        args.contexts,
        args.failfast,
        args.verbose,
        args.collect_only,
        args.output_path,
        args.severity,
    )