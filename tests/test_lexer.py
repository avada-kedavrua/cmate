import pytest

from cmate.lexer import Lexer, LexerError
from cmate.data_source import NA


@pytest.fixture(scope='function')
def lexer():
    lexer = Lexer()
    yield lexer
    lexer.cleanup()


# 基础功能测试
def test_tokenize_given_empty_string_when_tokenize_then_no_tokens(lexer):
    """测试空字符串输入"""
    tokens = list(lexer.tokenize(""))
    assert len(tokens) == 0


def test_tokenize_given_whitespace_only_when_tokenize_then_no_tokens(lexer):
    """测试只有空白字符"""
    tokens = list(lexer.tokenize(" \t\n \t"))
    assert len(tokens) == 0


# 数字测试
def test_tokenize_given_integer_number_when_tokenize_then_num_token(lexer):
    """测试整数解析"""
    tokens = list(lexer.tokenize("123"))
    assert len(tokens) == 1
    assert tokens[0].type == 'NUM'
    assert tokens[0].value == 123


def test_tokenize_given_float_number_when_tokenize_then_num_token(lexer):
    """测试浮点数解析"""
    tokens = list(lexer.tokenize("123.45"))
    assert len(tokens) == 1
    assert tokens[0].type == 'NUM'
    assert tokens[0].value == 123.45


def test_tokenize_given_negative_number_when_tokenize_then_num_token(lexer):
    """测试负数解析"""
    tokens = list(lexer.tokenize("-123"))
    assert len(tokens) == 1
    assert tokens[0].type == 'NUM'
    assert tokens[0].value == -123


# 单例值测试
@pytest.mark.parametrize("input_val, expected_val", [
    ("true", True),
    ("false", False),
    ("None", None),
    ("NA", NA)
])
def test_tokenize_given_singleton_values_when_tokenize_then_correct_singleton(lexer, input_val, expected_val):
    """测试单例值解析"""
    tokens = list(lexer.tokenize(input_val))
    assert len(tokens) == 1
    assert tokens[0].type == 'SINGLETON'
    assert tokens[0].value == expected_val


# 比较运算符测试
def test_tokenize_given_comparison_operators_when_tokenize_then_comparison_tokens(lexer):
    """测试比较运算符"""
    input_str = "== != >= > <= <"
    tokens = list(lexer.tokenize(input_str))
    expected_types = ['EQ', 'NE', 'GE', 'GT', 'LE', 'LT']
    assert len(tokens) == len(expected_types)
    for token, expected_type in zip(tokens, expected_types):
        assert token.type == expected_type


# 算术运算符测试
def test_tokenize_given_arithmetic_operators_when_tokenize_then_arithmetic_tokens(lexer):
    """测试算术运算符"""
    input_str = "+ - * / // % **"
    tokens = list(lexer.tokenize(input_str))
    expected_types = ['ADD', 'SUB', 'MUL', 'TRUEDIV', 'FLOORDIV', 'MOD', 'POW']
    assert len(tokens) == len(expected_types)
    for token, expected_type in zip(tokens, expected_types):
        assert token.type == expected_type


# 保留关键字测试
@pytest.mark.parametrize("keyword,token_type", [
    ("metadata", "METADATA"),
    ("if", "IF"),
    ("and", "AND"),
    ("for", "FOR"),
    ("dependency", "DEPENDENCY"),
    ("par", "PAR"),
    ("global", "GLOBAL"),
    ("elif", "ELIF"),
    ("else", "ELSE"),
    ("fi", "FI"),
    ("error", "ERROR"),
    ("warning", "WARNING"),
    ("info", "INFO"),
    ("done", "DONE"),
    ("or", "OR"),
    ("not", "NOT"),
    ("in", "IN")
])
def test_tokenize_given_reserved_keywords_when_tokenize_then_reserved_tokens(lexer, keyword, token_type):
    """测试保留关键字识别"""
    tokens = list(lexer.tokenize(keyword))
    assert len(tokens) == 1
    assert tokens[0].type == token_type


# 标识符测试
def test_tokenize_given_regular_identifier_when_tokenize_then_id_token(lexer):
    """测试常规标识符"""
    tokens = list(lexer.tokenize("variable_name"))
    assert len(tokens) == 1
    assert tokens[0].type == 'ID'
    assert tokens[0].value == 'variable_name'


def test_tokenize_given_identifier_with_dash_when_tokenize_then_id_token(lexer):
    """测试带连字符标识符"""
    tokens = list(lexer.tokenize("var-name"))
    assert len(tokens) == 1
    assert tokens[0].type == 'ID'
    assert tokens[0].value == 'var-name'


# 注释测试
def test_tokenize_given_single_line_comment_when_tokenize_then_no_token(lexer):
    """测试单行注释"""
    tokens = list(lexer.tokenize("# This is a comment"))
    assert len(tokens) == 0


def test_tokenize_given_comment_with_newline_when_tokenize_then_correct_handling(lexer):
    """测试带换行的注释"""
    tokens = list(lexer.tokenize("# comment\nnext_line"))
    assert len(tokens) == 1
    assert tokens[0].type == 'ID'


# 字符串测试
def test_tokenize_given_single_quoted_string_when_tokenize_then_str_token(lexer):
    """测试单引号字符串"""
    tokens = list(lexer.tokenize("'hello'"))
    assert len(tokens) == 1
    assert tokens[0].type == 'STR'
    assert tokens[0].value == 'hello'


def test_tokenize_given_double_quoted_string_when_tokenize_then_str_token(lexer):
    """测试双引号字符串"""
    tokens = list(lexer.tokenize('"world"'))
    assert len(tokens) == 1
    assert tokens[0].type == 'STR'
    assert tokens[0].value == 'world'


def test_tokenize_given_escaped_string_when_tokenize_then_correct_value(lexer):
    """测试转义字符串"""
    tokens = list(lexer.tokenize(r"'line1\nline2'"))
    assert len(tokens) == 1
    assert tokens[0].type == 'STR'
    assert tokens[0].value == 'line1\nline2'


def test_tokenize_given_string_with_escaped_backslash_when_tokenize_then_correct_value(lexer):
    """测试转义反斜杠"""
    tokens = list(lexer.tokenize(r"'path\\to\\file'"))
    assert len(tokens) == 1
    assert tokens[0].type == 'STR'
    assert tokens[0].value == 'path\\to\\file'


# JSON路径测试
def test_tokenize_given_DICTPATH_when_tokenize_then_DICTPATH_token(lexer):
    """测试JSON路径解析"""
    tokens = list(lexer.tokenize("${path.to.item}"))
    assert len(tokens) == 1
    assert tokens[0].type == 'DICTPATH'
    assert tokens[0].value == 'path.to.item'


def test_tokenize_given_nested_DICTPATH_when_tokenize_then_correct_value(lexer):
    """测试嵌套JSON路径"""
    tokens = list(lexer.tokenize("${path.{nested}.item}"))
    assert len(tokens) == 1
    assert tokens[0].type == 'DICTPATH'
    assert tokens[0].value == 'path.{nested}.item'


def test_tokenize_given_complex_DICTPATH_when_tokenize_then_correct_value(lexer):
    """测试复杂JSON路径"""
    tokens = list(lexer.tokenize("${path.to.{nested:{deep:value}}.item}"))
    assert len(tokens) == 1
    assert tokens[0].type == 'DICTPATH'
    assert tokens[0].value == 'path.to.{nested:{deep:value}}.item'


# 复杂组合测试
def test_tokenize_given_multiple_tokens_when_tokenize_then_all_tokens(lexer):
    """测试多token组合解析"""
    input_str = "if x == 5"
    tokens = list(lexer.tokenize(input_str))
    expected_types = ['IF', 'ID', 'EQ', 'NUM']
    expected_values = ['if', 'x', '==', 5]
    
    assert len(tokens) == len(expected_types)
    for token, exp_type, exp_val in zip(tokens, expected_types, expected_values):
        assert token.type == exp_type
        assert token.value == exp_val


def test_tokenize_given_newlines_when_tokenize_then_correct_line_numbers(lexer):
    """测试换行符处理"""
    tokens = list(lexer.tokenize("a\nb"))
    assert len(tokens) == 2
    assert tokens[0].lineno == 1
    assert tokens[1].lineno == 2


def test_tokenize_given_multiple_newlines_when_tokenize_then_correct_column_calculation(lexer):
    """测试多换行符的列计算"""
    tokens = list(lexer.tokenize("abc\ndef\nghi"))
    assert len(tokens) == 3
    # 每行的列号都应该是 1（行首）
    for token in tokens:
        assert token.col_offset == 1


# 错误处理测试
def test_tokenize_given_illegal_character_when_tokenize_then_skip_and_continue(lexer):
    """测试非法字符处理"""
    with pytest.raises(LexerError, match="Error on line 1, col 1: Unexpected character: \\^"):
        list(lexer.tokenize("a^b"))


def test_tokenize_given_unclosed_single_quote_when_tokenize_then_raise_error(lexer):
    """测试未闭合单引号错误"""
    with pytest.raises(LexerError, match="Unexpected EOF in string literal"):
        list(lexer.tokenize("'unclosed"))


def test_tokenize_given_unclosed_double_quote_when_tokenize_then_raise_error(lexer):
    """测试未闭合双引号错误"""
    with pytest.raises(LexerError, match="Unexpected EOF in string literal"):
        list(lexer.tokenize('"unclosed'))


def test_tokenize_given_unclosed_DICTPATH_when_tokenize_then_raise_error(lexer):
    """测试未闭合JSON路径错误"""
    with pytest.raises(LexerError, match="Unexpected EOF in string literal"):
        list(lexer.tokenize("${unclosed"))


def test_tokenize_given_mismatched_braces_in_DICTPATH_when_tokenize_then_raise_error(lexer):
    """测试JSON路径中大括号不匹配错误"""
    with pytest.raises(LexerError):
        list(lexer.tokenize("${path.{unclosed"))


# 清理方法测试
def test_cleanup_given_no_buffer_when_cleanup_then_no_error(lexer):
    """测试无缓冲区时的清理"""
    # 不创建任何字符串，直接调用cleanup
    lexer.cleanup()  # 应该不抛出异常


def test_cleanup_given_buffer_exists_when_cleanup_then_buffer_closed(lexer):
    """测试缓冲区清理"""
    # 先创建一个字符串来触发缓冲区创建
    list(lexer.tokenize("'test'"))
    
    # 测试cleanup不会抛出异常
    lexer.cleanup()


# 文字字符测试
def test_tokenize_given_literals_when_tokenize_then_correct_tokens(lexer):
    """测试文字字符识别"""
    input_str = "[]=():,{}"
    tokens = list(lexer.tokenize(input_str))
    # 应该正确识别所有文字字符
    assert len(tokens) == len(input_str)


# 边界情况测试
def test_tokenize_given_string_with_escaped_quote_when_tokenize_then_correct_parsing(lexer):
    """测试转义引号处理"""
    tokens = list(lexer.tokenize(r'"quote: \"test\""'))
    assert len(tokens) == 1
    assert tokens[0].type == 'STR'
    assert tokens[0].value == 'quote: "test"'


def test_tokenize_given_complex_expression_when_tokenize_then_correct_parsing(lexer):
    """测试复杂表达式解析"""
    input_str = 'if x >= 10 and y in [1, 2, 3]'
    tokens = list(lexer.tokenize(input_str))
    # 验证能够正确解析而不抛出异常
    assert len(tokens) > 0


def test_tokenize_given_mixed_content_when_tokenize_then_correct_ordering(lexer):
    """测试混合内容解析顺序"""
    input_str = 'metadata "test" 123 true'
    tokens = list(lexer.tokenize(input_str))
    expected_types = ['METADATA', 'STR', 'NUM', 'SINGLETON']
    assert len(tokens) == len(expected_types)
    for token, expected_type in zip(tokens, expected_types):
        assert token.type == expected_type


# 特殊字符转义测试
def test_tokenize_given_special_escape_sequences_when_tokenize_then_correct_handling(lexer):
    """测试特殊转义序列"""
    test_cases = [
        (r"'\n'", '\n'),
    ]
    
    for input_str, expected in test_cases:
        tokens = list(lexer.tokenize(input_str))
        assert len(tokens) == 1
        assert tokens[0].type == 'STR'
        assert tokens[0].value == expected
