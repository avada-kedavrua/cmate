from ply import lex, yacc


tokens = (
    'NUM', 'STR',
    'ADD', 'SUB', 'MUL', 'DIV', 'TRUEDIV', 'MOD', 'POW',
    'EQ', 'NE', 'GT', 'GE', 'LT', 'LE',
    'AND', 'OR', 'NOT',
    'LPAREN', 'RPAREN',
    'SKIP'
)


def t_NUM(t):
    r'-?\d+(\.\d*)?'
    t.value = float(t.value) if '.' in t.value else int(t.value)
    return t


def t_STR(t):
    r"\'[^\']+\'"
    t.value = t.value[1:-1]
    return t


t_ADD = r'\+'
t_SUB = r'\-'
t_MUL = r'\*'
t_DIV = r'/'
t_TRUEDIV = r'//'
t_MOD = r'%'
t_POW = r'\*\*'

t_EQ = r'=='
t_NE = r'!='
t_GT = r'>'
t_GE = r'>='
t_LT = r'<'
t_LE = r'<='

t_AND = r'and'
t_OR = r'or'
t_NOT = r'not'

t_LPAREN = r'\('
t_RPAREN = r'\)'


def t_SKIP(t):
    r'\s+'
    return None


def t_error(t):
    print(f"在第 {t.lineno} 行遇到非法字符: '{t.value[0]}'")
    t.lexer.skip(1)  # 跳过这个字符继续分析

# ----

def p_error(p):
    if p:
        print(f"语法错误，跳过token: {p.value}")
        
        # 错误恢复机制
        parser.errok()       # 清除错误状态
        return parser.token()  # 跳过当前token，继续解析
    else:
        print("意外结尾")
        return


lexer = lex.lex(optimize=True)
parser = yacc.yacc(optimize=True)
result = parser.parse()
print(result)
