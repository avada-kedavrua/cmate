import pytest

from cmate.parser import Parser, ParserError, IteratorToTokenStream
from cmate.util import Severity
from cmate._ast import (
    BinOp, UnaryOp, Call, Name, 
    Assign, Rule, If, For, Dependency,
    Document, Meta, Global, Partition,
    Constant, Compare, List, Dict
)


@pytest.fixture(scope='session')
def parser():
    """创建解析器实例"""
    return Parser()


# 基础结构测试
def test_parse_empty_document(parser):
    """测试解析空文档"""
    result = parser.parse("")
    assert isinstance(result, Document)
    assert result.body == []

def test_parse_single_meta_section(parser):
    """测试解析单个元数据段"""
    text = "[metadata]\na = 1\n---"
    result = parser.parse(text)
    assert isinstance(result, Document)
    assert len(result.body) == 1
    assert isinstance(result.body[0], Meta)

def test_parse_multiple_sections(parser):
    """测试解析包含多个段的文档"""
    text = """
    [metadata]
    version = 1.0
    ---
    
    [global]
    base_path = "/data"
    ---
    """
    result = parser.parse(text)
    assert isinstance(result, Document)
    assert len(result.body) == 2
    assert isinstance(result.body[0], Meta)
    assert isinstance(result.body[1], Global)

# 错误处理测试
def test_parse_error_unexpected_token(parser):
    """测试遇到意外token时抛出异常"""
    with pytest.raises(ParserError) as exc_info:
        parser.parse("[meta] invalid_token")
    assert "Unexpected token" in str(exc_info.value)

def test_parse_error_unexpected_eof(parser):
    """测试意外文件结束错误"""
    with pytest.raises(ParserError) as exc_info:
        parser.parse("[metadata]")
    assert "Unexpected end of file" in str(exc_info.value)

# 表达式测试
def test_parse_binary_operations(parser):
    """测试二元运算解析"""
    text = "a = 1 + 2 * 3"
    result = parser.parse("[global]\n" + text + "\n---")
    assign = result.body[0].body[0]
    assert isinstance(assign, Assign)
    assert isinstance(assign.value, BinOp)

@pytest.mark.parametrize("op, expected_op", [
    ("and", "and"),
    ("or", "or"), 
    ("<", "<"),
    (">", ">"),
    ("==", "=="),
    ("!=", "!="),
    ("in", "in"),
    ("not in", "not in")
])
def test_parse_comparison_operations(parser, op, expected_op):
    """测试各种比较运算解析"""
    text = f"a = x {op} y"
    result = parser.parse("[global]\n" + text + "\n---")
    assign = result.body[0].body[0]
    assert isinstance(assign.value, Compare)
    assert assign.value.op == expected_op

def test_parse_unary_operations(parser):
    """测试一元运算解析"""
    text = "a = not b"
    result = parser.parse("[global]\n" + text + "\n---")
    assign = result.body[0].body[0]
    assert isinstance(assign.value, UnaryOp)
    assert assign.value.op == "not"

def test_parse_function_call(parser):
    """测试函数调用解析"""
    text = "a = func(1, 2, x + y)"
    result = parser.parse("[global]\n" + text + "\n---")
    assign = result.body[0].body[0]
    assert isinstance(assign.value, Call)
    assert assign.value.func.id == "func"

# 数据结构测试
def test_parse_list_literal(parser):
    """测试列表字面量解析"""
    text = "a = [1, 2, 'hello']"
    result = parser.parse("[global]\n" + text + "\n---")
    assign = result.body[0].body[0]
    assert isinstance(assign.value, List)
    assert len(assign.value.elts) == 3

def test_parse_dict_literal(parser):
    """测试字典字面量解析"""
    text = "a = {x: 1, y: 2, z: 3}"
    result = parser.parse("[global]\n" + text + "\n---")
    assign = result.body[0].body[0]
    assert isinstance(assign.value, Dict)
    assert len(assign.value.keys) == 3
    assert len(assign.value.values) == 3

# 控制流测试
def test_parse_if_assignment(parser):
    """测试if条件赋值解析"""
    text = """
    if condition:
        a = 1
    fi
    """
    result = parser.parse("[global]\n" + text + "\n---")
    if_stmt = result.body[0].body[0]
    assert isinstance(if_stmt, If)
    assert if_stmt.orelse is None

def test_parse_if_else_assignment(parser):
    """测试if-else条件赋值解析"""
    text = """
    if condition:
        a = 1
    else:
        a = 2
    fi
    """
    result = parser.parse("[global]\n" + text + "\n---")
    if_stmt = result.body[0].body[0]
    assert isinstance(if_stmt, If)
    assert if_stmt.orelse is not None

def test_parse_for_loop_assignment(parser):
    """测试for循环赋值解析"""
    text = """
    for item in items:
        result = item * 2
    done
    """
    result = parser.parse("[global]\n" + text + "\n---")
    for_stmt = result.body[0].body[0]
    assert isinstance(for_stmt, For)
    assert for_stmt.target.id == "item"

def test_parse_continue_break(parser):
    """测试continue和break语句解析"""
    text = """
    for x in list:
        if x > 10:
            break
        else:
            continue
        fi
    done
    """
    result = parser.parse("[global]\n" + text + "\n---")
    for_stmt = result.body[0].body[0]
    if_stmt = result.body[0].body[0].body[0]
    assert isinstance(for_stmt, For)
    assert for_stmt.target.id == "x"
    assert isinstance(if_stmt, If)
    assert if_stmt.test.comparator.value == 10

# 规则相关测试
def test_parse_rule_assertion(parser):
    """测试规则断言解析"""
    text = "assert value > 0, 'Value must be positive'"
    result = parser.parse("[par test]\n" + text + "\n---")
    rule = result.body[0].body[0]
    assert isinstance(rule, Rule)
    assert rule.msg == 'Value must be positive'

@pytest.mark.parametrize("severity_str,expected_severity", [
    ("info", Severity.INFO),
    ("warning", Severity.WARNING),
    ("error", Severity.ERROR)
])
def test_parse_rule_with_severity(parser, severity_str, expected_severity):
    """测试带严重级别的规则解析"""
    text = f"assert condition, 'message', {severity_str}"
    result = parser.parse("[par test]\n" + text + "\n---")
    rule = result.body[0].body[0]
    assert rule.severity == expected_severity

def test_parse_if_rule_statement(parser):
    """测试条件规则语句解析"""
    text = """
    if enabled:
        assert value > 0, 'Check failed'
    fi
    """
    result = parser.parse("[par test]\n" + text + "\n---")
    if_rule = result.body[0].body[0]
    assert isinstance(if_rule, If)
    assert isinstance(if_rule.body[0], Rule)

# 分区相关测试
def test_parse_partition_section(parser):
    """测试分区段解析"""
    text = """
    [par user_partition]
    assert ${user.age} > 18, 'Age requirement'
    ---
    """
    result = parser.parse(text)
    partition = result.body[0]
    assert isinstance(partition, Partition)
    assert partition.target.id == "user_partition"

# 依赖关系测试
def test_parse_dependency_section(parser):
    """测试依赖关系段解析"""
    text = """
    [dependency]
    source: 'table1'
    target: 'table2@csv'
    ---
    """
    result = parser.parse(text)
    dependency = result.body[0]
    assert isinstance(dependency, Dependency)
    assert len(dependency.body) == 2

# 边界情况测试
def test_parse_nested_structures(parser):
    """测试嵌套结构解析"""
    text = """
    [metadata]
    if outer:
        if inner:
            value = [1, {x:2}]
        fi
    fi
    ---
    """
    result = parser.parse(text)
    # 验证复杂的嵌套结构能够正确解析
    assert isinstance(result, Document)
    assert len(result.body) > 0


def test_parse_complex_expression(parser):
    """测试复杂表达式解析"""
    text = "result = (a + b) * c - d / e and not f in list"
    result = parser.parse("[global]\n" + text + "\n---")
    # 验证运算符优先级和结合性正确
    assign = result.body[0].body[0]
    assert isinstance(assign, Assign)
    assert isinstance(assign.value, Compare)
    assert isinstance(assign.value.left, BinOp)
    assert isinstance(assign.value.comparator, UnaryOp)


def test_token_stream_iteration():
    """测试token流迭代"""
    def mock_iterator():
        yield type('Token', (), {'type': 'TEST', 'value': 'test'})()
        yield type('Token', (), {'type': 'END', 'value': 'end'})()
    
    stream = IteratorToTokenStream(mock_iterator())
    token1 = stream.token()
    token2 = stream.token()
    token3 = stream.token()  # 应该返回None
    
    assert token1 is not None
    assert token2 is not None  
    assert token3 is None


def test_parse_config_given_multiple_assignments_in_global_section_when_parsed_then_returns_document_with_correct_body(parser):
    '''测试解析包含全局段和两个赋值语句的基本配置'''
    text = '''\
[global]
a = 2
b = 3
---
    '''
    document_node = parser.parse(text)
    assert isinstance(document_node, Document)
    assert len(document_node.body) == 1

    global_node = document_node.body[0]
    assert isinstance(global_node, Global)
    assert len(global_node.body) == 2

    assign_node1 = global_node.body[0]
    assign_node2 = global_node.body[1]
    assert isinstance(assign_node1, Assign)
    assert isinstance(assign_node1.target, Name)
    assert assign_node1.target.id == 'a'
    assert isinstance(assign_node1.value, Constant)
    assert assign_node1.value.value == 2

    assert isinstance(assign_node2, Assign)
    assert isinstance(assign_node2.target, Name)
    assert assign_node2.target.id == 'b'
    assert isinstance(assign_node2.value, Constant)
    assert assign_node2.value.value == 3


def test_parse_given_empty_func_args_when_input_is_valid_then_create_correct_ast_nodes(parser):
    text = '''\
[global]
a = func()
---
'''
    document_node = parser.parse(text)
    assert isinstance(document_node, Document)
    assert len(document_node.body) == 1

    global_node = document_node.body[0]
    assert isinstance(global_node, Global)
    assert len(global_node.body) == 1

    assign_node1 = global_node.body[0]
    assert isinstance(assign_node1, Assign)
    assert isinstance(assign_node1.target, Name)
    assert assign_node1.target.id == 'a'
    assert isinstance(assign_node1.value, Call)
    assert assign_node1.value.args == []
    assert assign_node1.value.keywords == []


def test_parse_given_empty_list_assignment_when_input_is_valid_then_create_correct_ast_nodes(parser):
    text = '''\
[global]
a = []
---
'''
    document_node = parser.parse(text)
    assert isinstance(document_node, Document)
    assert len(document_node.body) == 1

    global_node = document_node.body[0]
    assert isinstance(global_node, Global)
    assert len(global_node.body) == 1

    assign_node1 = global_node.body[0]
    assert isinstance(assign_node1, Assign)
    assert isinstance(assign_node1.target, Name)
    assert assign_node1.target.id == 'a'
    assert isinstance(assign_node1.value, List)
    assert assign_node1.value.elts == []


def test_parse_given_empty_dict_assignment_when_input_is_valid_then_create_correct_ast_nodes(parser):
    text = '''\
[global]
a = {}
---
'''
    document_node = parser.parse(text)
    assert isinstance(document_node, Document)
    assert len(document_node.body) == 1

    global_node = document_node.body[0]
    assert isinstance(global_node, Global)
    assert len(global_node.body) == 1

    assign_node1 = global_node.body[0]
    assert isinstance(assign_node1, Assign)
    assert isinstance(assign_node1.target, Name)
    assert assign_node1.target.id == 'a'
    assert isinstance(assign_node1.value, Dict)
    assert assign_node1.value.keys == []
    assert assign_node1.value.values == []


def test_parse_nested_if_elif_else_statements_in_global_block_then_ast_structure_correct(parser):
    text = '''\
[global]
if a < 2:
    b = 2
elif a < 3:
    b = 3
elif a < 4:
    b = 4
else:
    b = 5
    b = 6
fi
---
'''
    document_node = parser.parse(text)
    assert isinstance(document_node, Document)
    assert len(document_node.body) == 1

    global_node = document_node.body[0]
    assert isinstance(global_node, Global)
    assert len(global_node.body) == 1

    if_node = global_node.body[0]
    assert isinstance(if_node, If)
    assert isinstance(if_node.test, Compare)
    assert len(if_node.orelse) == 1
    assert isinstance(if_node.orelse[0], If)

    next_if_node = if_node.orelse[0]
    assert isinstance(next_if_node, If)
    assert isinstance(next_if_node.test, Compare)
    assert len(next_if_node.orelse) == 1
    assert isinstance(next_if_node.orelse[0], If)

    next_if_node = next_if_node.orelse[0]
    assert isinstance(next_if_node, If)
    assert isinstance(next_if_node.test, Compare)
    assert len(next_if_node.orelse) == 2
    assert isinstance(next_if_node.orelse[0], Assign)
