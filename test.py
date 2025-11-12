import ply.lex as lex
import ply.yacc as yacc


tokens = ('NUM', 'OP', 'STR', 'SKIP')


def t_NUM(t):
    r'-?\d+(\.\d*)?'
    t.value = float(t.value) if '.' in t.value else int(t.value)
    return t


def t_OP(t):
    r'==|!=|>=|<=|\*\*|//|>|<|and|or|not|[+\-*/%]'
    return t


def t_SKIP(t):
    r'\s+'
    return None


def t_STR(t):
    r"\'[^\']+\'"
    return t


def t_error(t):
    return t


def p_a(p):
    '''
    expr : NUM OP NUM
    '''
    p[0] = p[1] + p[3]


def p_error(p):
    ''''''


lexer = lex.lex()
parser = yacc.yacc()
result = parser.parse("1 + 2")
print(result)
