import re

import pytest
from cmate.data_source import DataSource

from cmate.parser import Parser
from cmate.visitor import (
    _ExpressionEvaluator,
    AssignmentProcessor,
    ASTFormatter,
    CMateError,
    InfoCollector,
    RuleCollector,
)


@pytest.fixture(scope="session")
def parser():
    return Parser()


@pytest.fixture()
def info_collector():
    return InfoCollector()


def test_collect_given_metadata_name_assignment_when_input_is_valid_then_extract_correct_metadata_info(
    parser, info_collector
):
    text = """\
[metadata]
name = 'test_name'
---
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {"contexts": {}, "metadata": {"name": "test_name"}, "targets": {}}


def test_parse_multiple_metadata_blocks_raises_error(parser, info_collector):
    """Test that multiple metadata blocks now raise error"""
    text = """\
[metadata]
name = 'test_1'
---

[metadata]
name = 'test_2'
---
"""
    node = parser.parse(text)
    with pytest.raises(
        CMateError, match="Multiple \\[metadata\\] sections not allowed"
    ):
        info_collector.collect(node)


def test_collect_when_given_par_env_with_assert_in_desc_then_par_env_parsed_as_target(
    parser, info_collector
):
    text = """\
[par env]
assert 1, ''
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        "metadata": {},
        "targets": {
            "env": {
                "desc": None,
                "parse_format": None,
                "required_targets": None,
                "required_contexts": None,
            }
        },
        "contexts": {},
    }


def test_collect_when_multiple_par_blocks_present_then_all_blocks_parsed_as_targets(
    parser, info_collector
):
    text = """\
[par env]
assert 1, ''

[par sys]
assert 1, ''
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        "metadata": {},
        "targets": {
            "env": {
                "desc": None,
                "parse_format": None,
                "required_targets": None,
                "required_contexts": None,
            },
            "sys": {
                "desc": None,
                "parse_format": None,
                "required_targets": None,
                "required_contexts": None,
            },
        },
        "contexts": {},
    }


def test_collect_when_target_requires_context_then_context_and_target_relation_captured(
    parser, info_collector
):
    text = """\
[par env]
assert ${context::a} == 2, ''

"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        "metadata": {},
        "targets": {
            "env": {
                "desc": None,
                "parse_format": None,
                "required_targets": None,
                "required_contexts": ["a"],
            }
        },
        "contexts": {"a": {"desc": None, "options": [2]}},
    }


def test_collect_when_same_target_with_different_context_options_then_options_merged_in_context(
    parser, info_collector
):
    text = """\
[par env]
assert ${context::a} == 2, ''
---
[par env]
assert ${context::a} == 3, ''
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        "metadata": {},
        "targets": {
            "env": {
                "desc": None,
                "parse_format": None,
                "required_targets": None,
                "required_contexts": ["a"],
            }
        },
        "contexts": {"a": {"desc": None, "options": [2, 3]}},
    }


def test_collect_when_target_defined_in_dependency_block_then_parse_format_and_desc_parsed_correctly(
    parser, info_collector
):
    text = """\
[dependency]
sys : 'System' @ 'json'
---

[par sys]
assert ${env::ABC} == ${context::test}, 'test'
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        "metadata": {},
        "targets": {
            "sys": {
                "desc": "System",
                "parse_format": "json",
                "required_targets": ["env"],
                "required_contexts": ["test"],
            }
        },
        "contexts": {},
    }


def test_collect_complex_scenario_with_metadata_dependency_and_conditional_logic_then_info_collected_correctly(
    parser, info_collector
):
    text = """\
[metadata]
name = 'MindIE 配置项检查'
authors = [{"name": "a", "email": "b"}, {"name": "c"}]
---

[dependency]
mies_config: 'MindIE Service 主配置文件' @ 'json'
deploy_mode: '部署模式标识，用于确定检查规则集'
---

[global]
if ${context::deploy_mode} == 'pd_mix':
    dp = ${mies_config::BackendConfig.ModelDeployConfig.ModelConfig[0].dp} or 1

    if ${context::model_type} == 'deepseek':
        moe_ep = ${mies_config::BackendConfig.ModelDeployConfig.ModelConfig[0].moe_ep} or 1
    fi
fi
---

[par mies_config]
if ${context::deploy_mode} == 'pd_mix':
    assert ${pp} == 1, 'pp 取值只能等于 1', error
fi
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info == {
        "metadata": {
            "name": "MindIE 配置项检查",
            "authors": [{"name": "a", "email": "b"}, {"name": "c"}],
        },
        "targets": {
            "mies_config": {
                "desc": "MindIE Service 主配置文件",
                "parse_format": "json",
                "required_targets": None,
                "required_contexts": ["deploy_mode"],
            }
        },
        "contexts": {
            "deploy_mode": {
                "desc": ("部署模式标识，用于确定检查规则集", None),
                "options": ["pd_mix"],
            }
        },
    }


@pytest.fixture()
def data_source(mocker):
    return mocker.MagicMock()


@pytest.fixture()
def evaluator(data_source):
    return _ExpressionEvaluator(data_source)


def test_eval_complex_arithmetic_expression_in_global_block_then_result_matches_standard(
    parser, evaluator
):
    text = """\
[global]
a = (1 + 2 * 3 // 4 - 5) % 2
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    standard = (1 + 2 * 3 // 4 - 5) % 2

    assert standard == evaluator.evaluate(assign_node.value)


def test_eval_list_concatenation_with_dicts_in_global_block_then_result_matches_standard(
    parser, evaluator
):
    text = """\
[global]
a = [{'a': 2}] + [{'b': 3}]
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    standard = [{"a": 2}] + [{"b": 3}]

    assert standard == evaluator.evaluate(assign_node.value)


def test_eval_complex_comparison_expression_with_many_parentheses_in_global_block_then_result_matches_standard(
    parser, evaluator
):
    text = """\
[global]
a = (((((1 == 2) != 3) <= 4) >= 5) < 6) > 7
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    standard = (((((1 == 2) != 3) <= 4) >= 5) < 6) > 7  # noqa: SIM300

    assert standard == evaluator.evaluate(assign_node.value)


def test_eval_assign_value_given_match_operator_when_string_matches_regex_then_return_match_object(
    parser, evaluator
):
    text = """\
[global]
a = 'test_string' =~ 'str'
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    standard = re.search("str", "test_string")
    assert standard.pos == evaluator.evaluate(assign_node.value).pos
    assert standard.endpos == evaluator.evaluate(assign_node.value).endpos


def test_eval_regex_with_repetition_operator_when_string_length_exceeds_limit_then_timeout_occurs(
    parser, evaluator
):
    text = """\
[global]
a = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!' =~ '^(a+)+$'
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    with pytest.raises(TimeoutError, match="timed out after"):
        evaluator.evaluate(assign_node.value)


def test_eval_contains_check_with_data_source_access_in_global_block_then_result_matches_standard(
    parser, evaluator, data_source
):
    text = """\
[global]
a = ${a.b.c} in set([1, 2, 3])
---
"""
    data_source.__getitem__.return_value = 2
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    standard = 2 in {1, 2, 3}
    assert standard == evaluator.evaluate(assign_node.value)
    assert evaluator.history == [("global::a.b.c", 2)]


def test_eval_raises_cmate_error_when_function_undefined_in_global_scope(
    parser, evaluator
):
    text = """\
[global]
a = unknownfunc(1, 2, 3)
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    with pytest.raises(CMateError, match="Undefined function"):
        evaluator.evaluate(assign_node.value)


def test_eval_reference_to_another_global_variable_then_data_source_access_called(
    parser, evaluator
):
    """访问不带 namespace 的，默认 global"""
    text = """\
[global]
b = ${a}
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    evaluator.evaluate(assign_node.value)
    evaluator.data_source.__getitem__.assert_called_once_with("global::a")


@pytest.fixture(scope="session")
def pretty_formatter():
    return ASTFormatter()


def test_format_assert_statement_with_string_comparison_then_output_matches_expected_format(
    parser, pretty_formatter
):
    text = """\
[par env]
assert ${test::ABC} == 'ABC', 'test'
---
"""
    document_node = parser.parse(text)
    partition_node = document_node.body[0]
    rule_node = partition_node.body[0]
    assert pretty_formatter.format(rule_node) == "test::ABC == 'ABC'"


def test_format_assert_statement_with_nested_data_structure_then_output_matches_expected_format(
    parser, pretty_formatter
):
    text = """\
[par env]
assert ${test::ABC} == [{int(2): str(3)}] and not false, 'test'
---
"""
    document_node = parser.parse(text)
    partition_node = document_node.body[0]
    rule_node = partition_node.body[0]
    assert (
        pretty_formatter.format(rule_node)
        == "test::ABC == [{'int(2)': 'str(3)'}] and not False"
    )


@pytest.fixture
def input_configs(mocker):
    return mocker.MagicMock()


def test_process_variable_assignment_in_global_block_then_data_source_updated_with_correct_value(
    parser, input_configs, data_source
):
    text = """\
[global]
a = 2
---
"""
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)

    data_source.flatten.assert_called_once()
    data_source.flatten.assert_called_with("global", {"a": 2})


def test_process_conditional_assignment_in_global_block_when_flag_false_then_else_branch_executed(
    parser, input_configs, data_source
):
    text = """\
[global]
flag = true
if ${flag}:
    a = 2
elif ${flag}:
    b = 2
else:
    c = 2
fi
---
"""
    document_node = parser.parse(text)
    data_source.__getitem__.return_value = False
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)
    data_source.__getitem__.assert_called_with("global::flag")
    data_source.flatten.assert_called_with("global", {"c": 2})


def test_process_for_loop_with_conditional_assignment_then_variables_set_correctly(
    parser, input_configs
):
    text = """\
[global]
test_arr = [1, 2, 3]
for item in ${test_arr}:
    if ${item} < 2:
        b = ${item}
    else:
        c = ${item}
    fi
done
---
"""
    data_source = DataSource()
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)
    assert data_source["global::b"] == (1, "global::test_arr[0]")
    assert data_source["global::c"] == (3, "global::test_arr[2]")
    assert "global::__root__" not in data_source
    assert "global::item" not in data_source


def test_process_loop_with_dictionary_iteration_then_values_correctly_extracted_and_processed(
    parser, input_configs, data_source
):
    text = """\
[global]
for item in [{'name': 'a', 'value': 'b'}, {'name': 'c', 'value': 'd'}]:
    if ${item.name} == 'a':
        first_value = ${item.value}
    elif ${item.name} == 'c':
        second_value = ${item.value}
    fi
done
---
"""
    data_source = DataSource()
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)
    assert data_source["global::first_value"] == (
        "b",
        "[{\"'name'\": \"'a'\", \"'value'\": \"'b'\"}, {\"'name'\": \"'c'\", \"'value'\": \"'d'\"}][0]",
    )
    assert data_source["global::second_value"] == (
        "d",
        "[{\"'name'\": \"'a'\", \"'value'\": \"'b'\"}, {\"'name'\": \"'c'\", \"'value'\": \"'d'\"}][1]",
    )
    assert "global::__root__" not in data_source
    assert "global::item" not in data_source


def test_process_for_loop_with_continue_and_break_then_only_correct_variables_set(
    parser, input_configs, data_source
):
    text = """\
[global]
for item in set([1, 3, 5]):
    if ${item} < 4:
        continue
    fi

    a = ${item}
    break
    b = ${item}
done
---
"""
    data_source = DataSource()
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)
    assert "global::__root__" not in data_source
    assert "global::item" not in data_source
    assert data_source["global::a"] == (5, "set([1, 3, 5])[2]")


def test_process_reference_to_data_source_value_when_key_not_present_then_no_variable_assignment(
    parser, input_configs, data_source
):
    text = """\
[global]
a = ${env::ABC}
b = ${ABC}
c = ${abc}
---
"""
    results = {"abc": 2}

    def set_item(self, key, value):
        results[key] = value

    def get_item(self, key):
        return results[key]

    def del_item(self, key):
        del results[key]

    document_node = parser.parse(text)
    data_source.__setitem__ = set_item
    data_source.__getitem__ = get_item
    data_source.__delitem__ = del_item
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)
    assert results == {"abc": 2}


def test_process_break_outside_loop_then_cmate_error_raised(
    parser, input_configs, data_source
):
    text = """\
[global]
a = ${env::ABC}
break
---
"""
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    with pytest.raises(CMateError, match="'break' outside loop"):
        processor.process(document_node)


def test_process_continue_outside_loop_then_cmate_error_raised(
    parser, input_configs, data_source
):
    text = """\
[global]
a = ${env::ABC}
continue
---
"""
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    with pytest.raises(CMateError, match="'continue' not properly in loop"):
        processor.process(document_node)


def test_process_variable_assignment_in_global_block_then_flatten_called_with_correct_syntax(
    parser, input_configs, data_source
):
    text = """\
[global]
a = 2
b = a
---
"""
    document_node = parser.parse(text)
    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)
    data_source.flatten.assert_called_once_with("global", {"a": 2})


def test_visit_assert_statement_when_input_configs_not_contains_target_then_ruleset_empty(
    parser, input_configs, data_source
):
    text = """\
[par env]
assert ${test::ABC} == [{int(2): str(3)}] and not false, 'test'
---
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = False
    rule_collector = RuleCollector(input_configs, data_source, "info")
    ruleset = rule_collector.collect(document_node)
    assert not ruleset


def test_visit_assert_statement_when_input_configs_contains_target_then_ruleset_has_one_rule(
    parser, input_configs, data_source
):
    text = """\
[par env]
assert ${test::ABC} == [{int(2): str(3)}] and not false, 'test'
---
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    rule_collector = RuleCollector(input_configs, data_source, "info")
    ruleset = rule_collector.collect(document_node)
    assert len(ruleset) == 1


def test_visit_assert_statement_when_severity_mismatch_with_visitor_config_then_ruleset_empty(
    parser, input_configs, data_source
):
    text = """\
[par env]
assert ${test::ABC} == [{int(2): str(3)}] and not false, 'test', info
---
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    rule_collector = RuleCollector(input_configs, data_source, "error")
    ruleset = rule_collector.collect(document_node)
    assert not ruleset


def test_collect_conditional_assert_when_condition_true_then_correct_rule_added_to_ruleset(
    parser, input_configs, data_source
):
    text = """\
[par env]
if True:
    assert True, 'true'
else:
    assert False, 'false'
fi
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    rule_collector = RuleCollector(input_configs, data_source, "error")
    ruleset = rule_collector.collect(document_node)
    assert len(ruleset) == 1
    assert list(list(ruleset.values())[0])[0].msg == "true"


def test_collect_assert_inside_for_loop_when_condition_true_then_multiple_rules_generated(
    parser, input_configs
):
    text = """\
[par env]
for item in [1, 2, 3]:
    assert ${item} > 0, 'test'
done
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    data_source = DataSource()
    rule_collector = RuleCollector(input_configs, data_source, "error")
    ruleset = rule_collector.collect(document_node)
    assert len(ruleset) == 1
    assert len(ruleset["env"]) == 3
    assert "loopvar" in list(ruleset["env"])[0].test.left.path
    assert "loopvar" in list(ruleset["env"])[0].test.left.path
    assert "loopvar" in list(ruleset["env"])[0].test.left.path


def test_collect_assert_inside_for_loop_with_referenced_array_then_path_reflects_source_data(
    parser, input_configs
):
    text = """\
[global]
test_arr = [1, 2, 3]
---

[par env]
for item in ${test_arr}:
    assert ${item} > 0, 'test'
done
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    data_source = DataSource()

    # Process global section first to populate data_source
    from cmate.visitor import AssignmentProcessor

    processor = AssignmentProcessor(input_configs, data_source)
    processor.process(document_node)

    rule_collector = RuleCollector(input_configs, data_source, "error")
    ruleset = rule_collector.collect(document_node)
    assert len(ruleset) == 1
    assert len(ruleset["env"]) == 3
    assert "test_arr[" in list(ruleset["env"])[0].test.left.path


def test_collect_assert_with_break_outside_loop_then_cmate_error_raised(
    parser, input_configs
):
    text = """\
[par env]
assert ${item} > 0, 'test'
break
---
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    data_source = DataSource()
    rule_collector = RuleCollector(input_configs, data_source, "error")

    with pytest.raises(CMateError, match="'break' outside loop"):
        rule_collector.collect(document_node)


def test_collect_assert_with_continue_outside_loop_then_cmate_error_raised(
    parser, input_configs
):
    text = """\
[par env]
assert false, 'test'
continue
---
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    data_source = DataSource()
    rule_collector = RuleCollector(input_configs, data_source, "error")

    with pytest.raises(CMateError, match="'continue' not properly in loop"):
        rule_collector.collect(document_node)


def test_collect_assert_in_loop_with_continue_and_break_then_only_relevant_assert_captured(
    parser, input_configs, data_source
):
    text = """\
[par env]
for item in set([1, 3, 5]):
    if ${item} < 4:
        continue
    fi

    assert false, 'test'
    break
    assert true, 'test'
done
---
"""
    document_node = parser.parse(text)

    input_configs.__contains__.return_value = True
    data_source = DataSource()
    rule_collector = RuleCollector(input_configs, data_source, "error")
    ruleset = rule_collector.collect(document_node)

    assert len(ruleset) == 1
    assert len(ruleset["env"]) == 1
    assert list(ruleset["env"])[0].test.value is False


def test_info_collector_visit_global(parser, info_collector):
    """Test InfoCollector visit_global method"""
    text = """\
[global]
a = 1
---
"""
    node = parser.parse(text)
    # Should not raise
    info_collector.visit_global(node.body[0])


def test_info_collector_visit_meta_multiple_raises_error(parser, info_collector):
    """Test InfoCollector with multiple metadata blocks raises error"""
    text = """\
[metadata]
name = 'first'
---
[metadata]
name = 'second'
---
"""
    node = parser.parse(text)
    with pytest.raises(
        CMateError, match="Multiple \\[metadata\\] sections not allowed"
    ):
        info_collector.collect(node)


def test_expression_evaluator_visit_name_raises(parser):
    """Test that visiting Name raises CMateError"""
    from cmate.visitor import _ExpressionEvaluator, CMateError

    text = """\
[global]
a = undefined_var
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    evaluator = _ExpressionEvaluator(data_source)

    assign_node = document_node.body[0].body[0]
    with pytest.raises(CMateError, match="Direct variable reference is not allowed"):
        evaluator.evaluate(assign_node.value)


def test_expression_evaluator_undefined_function(parser):
    """Test evaluating undefined function"""
    from cmate.visitor import _ExpressionEvaluator, CMateError

    text = """\
[global]
a = undefined_func(1)
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    evaluator = _ExpressionEvaluator(data_source)

    assign_node = document_node.body[0].body[0]
    with pytest.raises(CMateError, match="Undefined function"):
        evaluator.evaluate(assign_node.value)


def test_node_visitor_generic_visit_none():
    """Test NodeVisitor generic_visit with None"""
    from cmate.visitor import NodeVisitor

    visitor = NodeVisitor()
    # Should not raise
    result = visitor.generic_visit(None)
    assert result is None


def test_node_visitor_generic_visit_no_slots():
    """Test NodeVisitor generic_visit with object without __slots__"""
    from cmate.visitor import NodeVisitor

    class NoSlots:
        pass

    visitor = NodeVisitor()
    # Should not raise
    result = visitor.generic_visit(NoSlots())
    assert result is None


def test_ast_formatter_visit_rule(parser):
    """Test ASTFormatter visit_rule"""
    from cmate.visitor import ASTFormatter

    text = """\
[par env]
assert ${test::key} == 'value', 'message'
---
"""
    document_node = parser.parse(text)
    formatter = ASTFormatter()
    rule = document_node.body[0].body[0]
    result = formatter.visit_rule(rule)
    assert "test::key" in result


def test_assignment_processor_visit_meta_dependency(parser):
    """Test AssignmentProcessor visit_meta and visit_dependency"""
    from cmate.visitor import AssignmentProcessor

    text = """\
[metadata]
name = 'test'
---
[dependency]
config: 'desc'
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    input_configs = {}
    processor = AssignmentProcessor(input_configs, data_source)

    # Should not raise
    processor.visit_meta(document_node.body[0])
    processor.visit_dependency(document_node.body[1])


def test_info_collector_visit_compare_with_context(parser, info_collector):
    """Test InfoCollector visit_compare with context comparison"""
    text = """\
[par env]
assert ${context::mode} == 'production', ''
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert "mode" in info["contexts"]
    assert "production" in info["contexts"]["mode"]["options"]


def test_info_collector_multiple_dependency_raises_error(
    parser, info_collector, caplog
):
    """Test InfoCollector raises error for multiple dependency sections"""
    text = """\
[dependency]
config: 'first'
---
[dependency]
config: 'second'
---
"""
    node = parser.parse(text)
    with pytest.raises(
        CMateError, match="Multiple \\[dependency\\] sections not allowed"
    ):
        info_collector.collect(node)


def test_expression_evaluator_visit_list(parser):
    """Test _ExpressionEvaluator visit_list"""
    from cmate.visitor import _ExpressionEvaluator

    text = """\
[global]
a = [1, 2, 3]
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    evaluator = _ExpressionEvaluator(data_source)

    assign_node = document_node.body[0].body[0]
    result = evaluator.evaluate(assign_node.value)
    assert result == [1, 2, 3]


def test_expression_evaluator_visit_dict(parser):
    """Test _ExpressionEvaluator visit_dict"""
    from cmate.visitor import _ExpressionEvaluator

    text = """\
[global]
a = {'key': 'value'}
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    evaluator = _ExpressionEvaluator(data_source)

    assign_node = document_node.body[0].body[0]
    result = evaluator.evaluate(assign_node.value)
    assert result == {"key": "value"}


def test_expression_evaluator_visit_binop(parser):
    """Test _ExpressionEvaluator visit_binop"""
    from cmate.visitor import _ExpressionEvaluator

    text = """\
[global]
a = 1 + 2
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    evaluator = _ExpressionEvaluator(data_source)

    assign_node = document_node.body[0].body[0]
    result = evaluator.evaluate(assign_node.value)
    assert result == 3


def test_expression_evaluator_visit_unaryop(parser):
    """Test _ExpressionEvaluator visit_unaryop"""
    from cmate.visitor import _ExpressionEvaluator

    text = """\
[global]
a = -5
---
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    evaluator = _ExpressionEvaluator(data_source)

    assign_node = document_node.body[0].body[0]
    result = evaluator.evaluate(assign_node.value)
    assert result == -5


def test_ast_formatter_visit_list_dict(parser):
    """Test ASTFormatter visit_list and visit_dict"""
    from cmate.visitor import ASTFormatter

    text = """\
[par env]
assert [1, 2] == [{'a': 1}], 'test'
---
"""
    document_node = parser.parse(text)
    formatter = ASTFormatter()
    rule = document_node.body[0].body[0]
    result = formatter.visit_rule(rule)
    assert "[1, 2]" in result


def test_rule_collector_visit_meta_dependency(parser, input_configs):
    """Test RuleCollector visit_meta and visit_dependency"""
    from cmate.visitor import RuleCollector

    text = """\
[metadata]
name = 'test'
---
[dependency]
config: 'desc'
---
[par env]
assert true, 'test'
"""
    document_node = parser.parse(text)
    data_source = DataSource()

    input_configs.__contains__.return_value = True
    collector = RuleCollector(input_configs, data_source, "error")
    collector.collect(document_node)
    # Should not raise


def test_assignment_processor_visit_partition(parser):
    """Test AssignmentProcessor visit_partition"""
    from cmate.visitor import AssignmentProcessor

    text = """\
[par env]
assert true, 'test'
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    input_configs = {}
    processor = AssignmentProcessor(input_configs, data_source)

    # Should not raise
    processor.visit_partition(document_node.body[0])


def test_evaluator_visit_unaryop(parser, evaluator):
    """Test _ExpressionEvaluator visit_unaryop"""
    text = """\
[global]
a = -123
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    result = evaluator.evaluate(assign_node.value)
    assert result == -123


def test_evaluator_visit_binop(parser, evaluator):
    """Test _ExpressionEvaluator visit_binop"""
    text = """\
[global]
a = 1 + 2
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    result = evaluator.evaluate(assign_node.value)
    assert result == 3


def test_evaluator_visit_call_undefined_function(parser, evaluator):
    """Test _ExpressionEvaluator visit_call with undefined function"""
    from cmate.visitor import CMateError

    text = """\
[global]
a = undefined_func(1)
---
"""
    document_node = parser.parse(text)
    global_node = document_node.body[0]
    assign_node = global_node.body[0]
    with pytest.raises(CMateError, match="undefined_func"):
        evaluator.evaluate(assign_node.value)


def test_rule_collector_visit_assert_with_info_severity(parser):
    """Test RuleCollector visit_assert with info severity filter"""
    from cmate.visitor import RuleCollector

    text = """\
[par env]
assert true, 'test'
"""
    document_node = parser.parse(text)
    data_source = DataSource()
    input_configs = {}
    # Use "error" severity to filter out info rules
    collector = RuleCollector(input_configs, data_source, "error")

    # Should skip info rules due to severity filter
    result = collector.collect(document_node)
    assert len(result) == 0 or all(len(rules) == 0 for rules in result.values())


# ---------------------------------------------------------------------------
# Tests for Partition-Dependency Validation (partition must be in dependency)
# ---------------------------------------------------------------------------


def test_collect_partition_without_dependency_raises_error(parser, info_collector):
    """Test that partition not in dependency section raises error"""
    text = """\
[par config]
assert true, 'test'
"""
    node = parser.parse(text)
    with pytest.raises(
        CMateError, match="must be declared in \\[dependency\\] section"
    ):
        info_collector.collect(node)


def test_collect_partition_with_dependency_succeeds(parser, info_collector):
    """Test that partition with matching dependency works"""
    text = """\
[dependency]
config: 'Configuration file'
---

[par config]
assert true, 'test'
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert "config" in info["targets"]
    assert info["targets"]["config"]["desc"] == "Configuration file"


def test_collect_env_partition_without_dependency_allowed(parser, info_collector):
    """Test that 'env' partition is exempted from dependency requirement"""
    text = """\
[par env]
assert true, 'test'
"""
    node = parser.parse(text)
    # Should not raise - env partition is special
    info = info_collector.collect(node)
    assert "env" in info["targets"]


def test_collect_multiple_partitions_all_need_dependency(parser, info_collector):
    """Test that all partition targets must be in dependency"""
    text = """\
[dependency]
config1: 'First config'
---

[par config1]
assert true, 'test1'

[par config2]
assert true, 'test2'
"""
    node = parser.parse(text)
    with pytest.raises(CMateError, match="config2.*must be declared"):
        info_collector.collect(node)


# ---------------------------------------------------------------------------
# Tests for Single Section Rule (only one metadata and one dependency)
# ---------------------------------------------------------------------------


def test_collect_multiple_metadata_raises_error(parser, info_collector):
    """Test that multiple metadata sections raise error"""
    text = """\
[metadata]
name = 'first'
---

[metadata]
name = 'second'
---
"""
    node = parser.parse(text)
    with pytest.raises(
        CMateError, match="Multiple \\[metadata\\] sections not allowed"
    ):
        info_collector.collect(node)


def test_collect_multiple_dependency_raises_error(parser, info_collector):
    """Test that multiple dependency sections raise error"""
    text = """\
[dependency]
config: 'first'
---

[dependency]
config: 'second'
---
"""
    node = parser.parse(text)
    with pytest.raises(
        CMateError, match="Multiple \\[dependency\\] sections not allowed"
    ):
        info_collector.collect(node)


def test_collect_single_metadata_succeeds(parser, info_collector):
    """Test that single metadata section works"""
    text = """\
[metadata]
name = 'test'
version = '1.0'
---
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert info["metadata"]["name"] == "test"
    assert info["metadata"]["version"] == "1.0"


def test_collect_single_dependency_succeeds(parser, info_collector):
    """Test that single dependency section works"""
    text = """\
[dependency]
config: 'Configuration file' @ 'json'
---

[par config]
assert true, 'test'
"""
    node = parser.parse(text)
    info = info_collector.collect(node)
    assert "config" in info["targets"]
