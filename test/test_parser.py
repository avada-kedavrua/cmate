import pytest

from cmate.parser import Parser, ParserError, IteratorToTokenStream
from cmate.util import Severity
from cmate._ast import (
    BinOp, UnaryOp, Call, Name, Desc, 
    Assign, Rule, If, For, Dependency,
    Document, Meta, Global, Partition, DictPath,
    Constant, Compare, List, Dict,
    Continue, Break
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
