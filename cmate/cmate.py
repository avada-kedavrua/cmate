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
from typing import List

from msguard import Rule, validate_args
from msguard.security import open_s

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
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
LOG_FORMAT = "[%(levelname)s] [%(name)s] %(message)s"


logger = logging.getLogger(__name__)


def _parse_configs(configs: List[str]):
    res = {}
    if not configs:
        return True, res

    splitter = ":"
    parse_splitter = "@"

    for entry in configs:
        parts = entry.split(splitter, 1)

        if parts[0] == "env":
            res["env"] = (None, None)
            continue

        if len(parts) != 2:
            logger.error(
                "Invalid configuration format. Expected format: '<name>:<path>' or '<name>:<path>@<parse_type>'.\n"
                "  - <name>: A configuration identifier defined in the cmate file.\n"
                "  - <path>: File system path for the configuration file.\n"
                "  - <parse_type>: (Optional) Specifies the parsing method for the file (e.g., 'json', 'yaml')."
            )
            return False, res

        name = parts[0]
        fields = parts[1].split(parse_splitter, 1)
        path, parse_type = fields[0], None if len(fields) == 1 else fields[1]

        res[name] = (path, parse_type)

    return True, res


def _parse_contexts(configs: List[str]):
    res = {}
    if not configs:
        return True, res

    splitter = ":"
    for entry in configs:
        parts = entry.split(splitter, 1)

        if len(parts) != 2:
            logger.error(
                "Invalid format detected. Expected syntax: '<name>:<value>'.\n"
                "  - <name>: A context namespace defined in the CMATE configuration.\n"
                "  - <value>: The value to assign to the specified context namespace.\n"
                "Note: Unquoted numbers (e.g., 2) are treated as integers. "
                "To pass a string value, enclose it in quotes: '2'."
            )
            return False, res

        name, value = parts
        try:
            res[name] = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            res[name] = value

    return True, res


def _display_text(info):
    for attr in ("metadata", "targets", "contexts"):
        if attr not in info:
            logger.critical(
                "Required attribute '%s' is missing from the configuration data structure. "
                "This is likely caused by one of the following issues:\n"
                "  1. The CMATE rule file is corrupted or has an invalid format\n"
                "  2. Internal parsing logic failed to extract the required attribute\n"
                "  3. Private API methods were called directly with incomplete data\n\n"
                "This is a critical system error that requires immediate attention. "
                "Please ensure that:\n"
                "  - CMATE rule files follow the correct schema\n"
                "  - Only public APIs are used for configuration processing",
                attr,
            )
            return

    _display_text_overview(info["metadata"])
    _display_text_contexts(info["contexts"])
    _display_text_targets(info["targets"])

    # 使用说明
    print("Usage: -c <rule_name>:<file_path> -C <context>:<value>\n")


def _display_text_overview(metadata):
    _format_section("Overview")
    if metadata:
        for key, value in metadata.items():
            _format_field(key, value or "", 1)
    else:
        print("No overview available")
    print("\n")


def _display_text_contexts(contexts):
    _format_section("Context Variables")
    if contexts:
        for ctx_var, ctx_info in contexts.items():
            desc = (
                ctx_info["desc"][0]
                if isinstance(ctx_info["desc"], tuple)
                else "No description provided"
            )
            options = ctx_info["options"]
            _format_field(ctx_var, options)
            print(f"    {desc}\n")
    else:
        print("\nNo contexts available.")
    print()


def _display_text_targets(targets):
    _format_section("Config Targets")
    if targets:
        for target_name, target_info in targets.items():
            _format_section(f"{target_name}", 2)

            desc = target_info["desc"] or "No description provided"
            parse_type = target_info["parse_type"] or "Unknown"
            required_targets = target_info["required_targets"]
            required_contexts = target_info["required_contexts"]

            if target_name == "env":
                _format_field("description", "Environment variables validation", 4)
            else:
                _format_field("type", parse_type, 4)
                _format_field("description", desc, 4)

            if required_targets:
                _format_field("required_targets", ", ".join(required_targets), 4)
            if required_contexts:
                _format_field("required_contexts", ", ".join(required_contexts), 4)
            print()
    else:
        print("\nNo config targets available.")
    print()


def _format_section(title, level=0):
    indent = "  " * level
    separator = "-" * len(title)

    print(f"{indent}{title}\n{indent}{separator}")


def _format_field(label, value, indent=0):
    print(f"{'  ' * indent}{label} : {value}")


def _display_json(result):
    print(json.dumps(result, indent=4, ensure_ascii=False))


def _validate_and_load_dependencies(info, input_targets, input_contexts):
    input_targets = input_targets or {}
    input_contexts = input_contexts or {}

    all_targets = info["targets"]
    all_contexts = info["contexts"]

    data_source = DataSource()

    ret, matched_targets = _validate_and_load_targets(
        input_targets, all_targets, data_source
    )
    if not ret:
        return ret, data_source

    if not matched_targets:
        logger.error(
            "No configuration targets from the input matched. "
            "The cmate file supports the following configuration targets: \n  - %s",
            "\n  - ".join(all_targets.keys()),
        )
        return False, data_source

    missing_deps = _collect_missing_dependencies(
        matched_targets, input_targets, input_contexts, all_targets
    )
    if missing_deps:
        _log_missing_error(missing_deps, all_targets, all_contexts)
        return False, data_source

    _validate_and_load_contexts(input_contexts, all_contexts, data_source)
    return True, data_source


def _validate_and_load_targets(input_targets, all_targets, data_source):
    matched_targets = []
    for target, (input_path, input_parse_type) in input_targets.items():
        if target not in all_targets:
            logger.warning(
                "Configuration target '%s' is not defined in the cmate file and will be skipped. "
                "Currently supported targets are: %s",
                target,
                list(all_targets.keys()),
            )
            continue

        matched_targets.append(target)
        if target == "env":
            parsed_data = dict(os.environ.items())
        else:
            # User-specified parse type, rule-defined parse type, or None (for extension-based detection)
            parse_type = input_parse_type or all_targets[target].get("parse_type")

            try:
                parsed_data = load(input_path, parse_type)
            except OSError:
                logger.error(
                    "Configuration target '%s' was not found at the specified path: '%s'. "
                    "Please verify that the file exists and the path is correct.",
                    target,
                    input_path,
                )
                return False, matched_targets
            except TypeError:
                logger.error(
                    "Parse type '%s' is not supported for configuration '%s' at: '%s'. "
                    "To resolve, specify a supported parse type using: '-c %s:%s@<parse-type>'",
                    parse_type,
                    target,
                    input_path,
                    target,
                    input_path,
                )
                return False, matched_targets
            except Exception:
                logger.exception(
                    "Failed to parse configuration '%s' from: '%s'. "
                    "The %s syntax appears to be invalid.",
                    target,
                    input_path,
                    parse_type,
                )
                return False, matched_targets

        data_source.flatten(target, parsed_data)

    return True, matched_targets


def _collect_missing_dependencies(
    matched_targets, input_targets, input_contexts, all_targets
):
    missing_deps = {}
    for target in matched_targets:
        missing_map = {"targets": [], "contexts": []}

        target_info = all_targets[target]
        required_targets = target_info["required_targets"] or []
        required_contexts = target_info["required_contexts"] or []

        for required_target in required_targets:
            if required_target not in input_targets:
                missing_map["targets"].append(required_target)

        for required_context in required_contexts:
            if required_context not in input_contexts:
                missing_map["contexts"].append(required_context)

        if missing_map["targets"] or missing_map["contexts"]:
            missing_deps[target] = missing_map

    return missing_deps


def _log_missing_error(missing_deps, all_targets, all_contexts):
    error_parts = []

    for target, missing_info in missing_deps.items():
        missing_targets = missing_info["targets"]
        missing_contexts = missing_info["contexts"]

        error_parts.append(
            f"Configuration target '{target}' is missing required dependencies:"
        )

        if missing_targets:
            error_parts.append("\nMissing configuration targets:")
            for missing_target in missing_targets:
                if missing_target in all_targets:
                    target_info = all_targets[missing_target]
                    desc = target_info["desc"] or "No description available."
                    error_parts.append(f"  - {missing_target}: {desc}")

        if missing_contexts:
            error_parts.append("\nMissing context variables:")
            for missing_context in missing_contexts:
                if missing_context in all_contexts:
                    context_info = all_contexts[missing_context]
                    desc = (
                        context_info["desc"][0]
                        if isinstance(context_info["desc"], tuple)
                        else "No description provided"
                    )
                    options = context_info["options"]
                    error_parts.append(f"  - {missing_context} : {options}")
                    error_parts.append(f"      {desc}")
        error_parts.append("")

    error_parts.append(
        "\nTo resolve, please provide the missing dependencies:\n"
        "  - Use '-c <target-name>:<file-path>' to specify missing configuration targets\n"
        "  - Use '-C <context-name>:_format_field<value>' to provide required context variables"
    )

    logger.error("\n".join(error_parts))


def _validate_and_load_contexts(input_contexts, all_contexts, data_source):
    for context, value in input_contexts.items():
        if context not in all_contexts:
            logger.warning(
                "Context '%s' is not defined in the cmate file and will be skipped. "
                "Currently supported contexts are: %s",
                context,
                list(all_contexts.keys()),
            )
            continue
        data_source[f"context::{context}"] = value


def _collect_only(ruleset):
    pretty_formatter = ASTFormatter()

    msg = []
    for namespace in ruleset:
        msg.append(f"<Namespace {namespace}>")
        for rule_node in ruleset[namespace]:
            rule = pretty_formatter.format(rule_node)
            msg.append(f"  <Rule-{rule_node.lineno} {rule}>")
    logger.info("\n".join(msg))
    return 0


class NAEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, NAType):
            return {"NAType": True}  # 使用特殊标记
        return super().default(obj)


def _actual_run(ruleset, data_source, failfast, verbosity, output_path):
    test_runner = RuleTestRunner(failfast=failfast, verbosity=verbosity)

    msprechecker_output = {}

    test_suite = make_test_suite(data_source, ruleset, msprechecker_output)
    result = test_runner.run(test_suite)

    if output_path:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        msprechecker_output_name = f"msprechecker_{timestamp}_output.json"
        os.makedirs(output_path, exist_ok=True)
        saved_json = os.path.join(output_path, msprechecker_output_name)
        with open_s(saved_json, "w", encoding="utf-8") as f:
            json.dump(
                msprechecker_output, f, cls=NAEncoder, ensure_ascii=False, indent=4
            )

    return result.wasSuccessful()


def parse(rule_path):
    parser = Parser()

    with open_s(rule_path) as f:
        node = parser.parse(f.read())

    return node


def inspect(rule_path: str, output_format: str):
    output_format_map = {"text": _display_text, "json": _display_json}

    node = parse(rule_path)
    info = InfoCollector().collect(node)

    if output_format not in output_format_map:
        raise ValueError(f"Unsupported output format: {output_format}")

    return output_format_map[output_format](info)


def run(
    rule_path: str,
    configs=None,
    contexts=None,
    failfast=False,
    verbosity=False,
    collect_only=False,
    output_path="",
    severity="info",
):
    node = parse(rule_path)
    info = InfoCollector().collect(node)

    ret, data_source = _validate_and_load_dependencies(info, configs, contexts)
    if not ret:
        return 1

    AssignmentProcessor(configs, data_source).process(node)  # process global section
    rule_collector = RuleCollector(configs, data_source, severity)  # collect rule

    try:
        ruleset = rule_collector.collect(node)
    except KeyError:
        logger.exception(
            "Rule collection failed. "
            "Most likely because you are trying to use a value from a namespace "
            "that was not specified in the dependencies section, nor in the partition section."
        )
        return 1

    EnvironmentScriptGenerator(data_source).generate(node)  # try to generate env script

    if collect_only:
        return _collect_only(ruleset)

    return _actual_run(ruleset, data_source, failfast, verbosity, output_path)


def main():
    arg_parser = argparse.ArgumentParser(
        prog="cmate",
        description="CMATE - Configuration Management and Testing Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = arg_parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Execute configuration validation against specified rules",
        description="Run comprehensive validation of configurations using the specified rule set.",
    )

    run_parser.add_argument(
        "rule",
        type=validate_args(Rule.input_file_read),
        help="Path to the rule definition file (CMATE format)",
    )

    run_parser.add_argument(
        "--configs",
        "-c",
        nargs="*",
        help=(
            "Configuration files to validate, specified as '<name>:<path>' or '<name>:<path>@<parse-type>'.\n"
            "  - <name>: Configuration identifier defined in the rule file\n"
            "  - <path>: File system path to the configuration file\n"
            "  - <parse-type>: (Optional) Parsing method ('json', 'yaml', 'yml')\n"
            "Note: For 'env' type targets, the <path> component is optional and will be discarded if provided."
        ),
    )

    run_parser.add_argument(
        "--contexts",
        "-C",
        nargs="*",
        help=(
            "Context variables required for rule execution, specified as '<name>:<value>'.\n"
            "  - <name>: Context identifier defined in the rule file\n"
            "  - <value>: Value to assign to the context variable\n"
            "Note: Unquoted numbers are parsed as integers. Use quotes for string values: '2'."
        ),
    )

    run_parser.add_argument(
        "-co",
        "--collect-only",
        action="store_true",
        help="Display the list of rules that would be executed without actually running them",
    )

    run_parser.add_argument(
        "--output-path", help="Path to the save msprechecker output."
    )

    run_parser.add_argument(
        "-x",
        "--fail-fast",
        action="store_true",
        dest="failfast",
        help="Stop execution immediately upon encountering the first failure or error",
    )

    run_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        help="Enable verbose output, displaying detailed test names and individual results",
    )

    run_parser.add_argument(
        "-s",
        "--severity",
        choices=["info", "warning", "error"],
        default="info",
        help=(
            "Minimum severity level for rule execution:\n"
            "  - info: Execute all checks (default)\n"
            "  - warning: Execute only warning and error checks\n"
            "  - error: Execute only error checks"
        ),
    )

    run_parser.add_argument(
        "-l",
        "--log-level",
        choices=LOG_LEVELS,
        default="info",
        help="Set the logging level.",
    )

    # Inspect command
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Display detailed information about rule requirements",
        description="Inspect and display the configuration targets, contexts, and requirements defined in a rule file.",
    )

    inspect_parser.add_argument(
        "rule",
        type=validate_args(Rule.input_file_read),
        help="Path to the rule definition file (CMATE format)",
    )

    inspect_parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help=(
            "Output format for the inspection results:\n"
            "  - text: Human-readable text format (default)\n"
            "  - json: Structured JSON format for programmatic processing"
        ),
    )

    args = arg_parser.parse_args()

    if args.command == "inspect":
        return inspect(args.rule, args.format)

    elif args.command == "run":
        logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVELS[args.log_level])
        ret, configs = _parse_configs(args.configs)
        if not ret:
            return 1

        ret, contexts = _parse_contexts(args.contexts)
        if not ret:
            return 1

        return run(
            args.rule,
            configs,
            contexts,
            args.failfast,
            args.verbose,
            args.collect_only,
            args.output_path,
            args.severity,
        )

    return 0
