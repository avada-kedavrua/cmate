from io import StringIO

import ply.lex

from .data_source import NA


class LexerError(Exception):
    pass


class Lexer:
    headers = {'metadata': 'METADATA', 'dependency': 'DEPENDENCY', 'par': 'PAR', 'global': 'GLOBAL'}
    conditiion_keywords = {'if': 'IF', 'elif': 'ELIF', 'else': 'ELSE', 'fi': 'FI'}
    rule_keywords = {'assert': 'ASSERT', 'error': 'ERROR', 'warning': 'WARNING', 'info': 'INFO'}
    loop_keywords = {'for': 'FOR', 'done': 'DONE', 'continue': 'CONTINUE', 'break': 'BREAK'}
    logical_keywords = {'and': 'AND', 'or': 'OR', 'not': 'NOT', 'in': 'IN'}

    reserved_words = {
        **headers,
        **conditiion_keywords,
        **rule_keywords,
        **loop_keywords,
        **logical_keywords,
    }

    primitive_tokens = ['NUM', 'STR', 'SINGLETON']
    compound_tokens = ['ID', 'DICTPATH']
    comparison_tokens = ['EQ', 'NE', 'GE', 'GT', 'LE', 'LT', 'RE']
    arithmetic_tokens = ['ADD', 'SUB', 'MUL', 'TRUEDIV', 'FLOORDIV', 'MOD', 'POW']
    terminator_token = ['END']

    reserved_vals = list(dict.fromkeys(reserved_words.values()))
    tokens = (
        primitive_tokens + compound_tokens + comparison_tokens + \
        arithmetic_tokens + terminator_token + reserved_vals
    )
    literals = ['[', ']', '=', '(', ')', ':', ',', '{', '}', '@']
    states = [ 
        ('comment', 'exclusive'),
        ('singlequote', 'exclusive'),
        ('doublequote', 'exclusive'),
        ('dollar', 'exclusive')
    ]

    t_ignore = ' \t'

    # comparison_tokens
    t_EQ = r'=='
    t_NE = r'!='
    t_GE = r'>='
    t_GT = r'>'
    t_LE = r'<='
    t_LT = r'<'
    t_RE = r'=~'

    # arithmetic_tokens
    t_POW = r'\*\*'
    t_FLOORDIV = r'//'
    t_MUL = r'\*'
    t_TRUEDIV = r'/'
    t_MOD = r'%'
    t_ADD = r'\+'
    t_SUB = r'-'

    def __init__(self, errorlog=None):
        self.lexer = ply.lex.lex(module=self, errorlog=errorlog)
        self.lexer.latest_newline = 0
    
    @staticmethod
    def t_NUM(t):
        r'-?\d+(\.\d+)?'
        t.value = float(t.value) if '.' in t.value else int(t.value)
        return t

    @staticmethod
    def t_SINGLETON(t):
        r'false|true|None|NA|False|True'
        singleton_map = {
            'false': False, 'true': True,
            'False': False, 'True': True,
            'None': None, 'NA': NA
        }
        t.value = singleton_map.get(t.value)
        return t

    # support '---' as an explicit section terminator (new terminator)
    @staticmethod
    def t_END(t):
        r'---'
        t.type = 'END'
        return t

    t_comment_ignore = ''

    @staticmethod
    def t_comment(t):
        r'\#'
        t.lexer.push_state('comment')

    @staticmethod
    def t_comment_content(t):
        r'[^\n]+'

    @staticmethod
    def t_comment_end(t):
        r'\n'
        t.lexer.lineno += 1
        t.lexer.latest_newline = t.lexpos + 1
        t.lexer.pop_state()

    @staticmethod
    def t_comment_error(t):
        raise LexerError(
            'Error on line %s, col %s while lexing comment field: Unexpected character: %s' %
            (t.lexer.lineno, t.lexpos - t.lexer.latest_newline, t.value[0])
        )

    t_singlequote_ignore = ''

    @staticmethod
    def t_singlequote(t):
        r"'"
        t.lexer.buffer = StringIO()
        t.lexer.push_state('singlequote')

    @staticmethod
    def t_singlequote_content(t):
        r"[^'\\]+"
        t.lexer.buffer.write(t.value)

    @staticmethod
    def t_singlequote_escape(t):
        r"\\."
        char = t.value[1]
        t.lexer.buffer.write('\n' if char == 'n' else char)

    @staticmethod
    def t_singlequote_end(t):
        r"'"
        t.value = t.lexer.buffer.getvalue()
        t.lexer.buffer.close()
        t.lexer.buffer = None
        t.type = 'STR'
        t.lexer.pop_state()
        return t

    @staticmethod
    def t_singlequote_error(t):
        if hasattr(t.lexer, 'buffer') and t.lexer.buffer is not None:
            t.lexer.buffer.close()
            t.lexer.buffer = None
        raise LexerError(
            'Error on line %s, col %s while lexing singlequoted field: Unexpected character: %s' %
            (t.lexer.lineno, t.lexpos - t.lexer.latest_newline, t.value[0])
        )

    t_doublequote_ignore = ''

    @staticmethod
    def t_doublequote(t):
        r'"'
        t.lexer.buffer = StringIO()  # Use StringIO for better performance
        t.lexer.push_state('doublequote')

    @staticmethod
    def t_doublequote_content(t):
        r'[^"\\]+'
        t.lexer.buffer.write(t.value)

    @staticmethod
    def t_doublequote_escape(t):
        r'\\.'
        char = t.value[1]
        t.lexer.buffer.write('\n' if char == 'n' else char)

    @staticmethod
    def t_doublequote_end(t):
        r'"'
        t.value = t.lexer.buffer.getvalue()
        t.lexer.buffer.close()
        t.lexer.buffer = None
        t.type = 'STR'
        t.lexer.pop_state()
        return t

    @staticmethod
    def t_doublequote_error(t):
        if hasattr(t.lexer, 'buffer') and t.lexer.buffer is not None:
            t.lexer.buffer.close()
            t.lexer.buffer = None
        raise LexerError(
            'Error on line %s, col %s while lexing doublequoted field: Unexpected character: %s' % 
            (t.lexer.lineno, t.lexpos - t.lexer.latest_newline, t.value[0])
        )

    t_dollar_ignore = ''

    @staticmethod
    def t_dollar(t):
        r'\$\{'
        t.lexer.buffer = StringIO()
        t.lexer.brace_count = 1
        t.lexer.push_state('dollar')

    @staticmethod
    def t_dollar_content(t):
        r'[^{}]+'
        t.lexer.buffer.write(t.value)

    @staticmethod
    def t_dollar_brace(t):
        r'[{}]'
        if t.value == '}':
            t.lexer.brace_count -= 1
            if t.lexer.brace_count == 0:
                t.value = t.lexer.buffer.getvalue()
                t.type = 'DICTPATH'

                t.lexer.buffer.close()
                t.lexer.buffer = None
                t.lexer.brace_count = None
                t.lexer.pop_state()
                return t
        else:
            t.lexer.brace_count += 1
        
        t.lexer.buffer.write(t.value)
        return None

    @staticmethod
    def t_dollar_error(t):
        if hasattr(t.lexer, 'buffer') and t.lexer.buffer is not None:
            t.lexer.buffer.close()
            t.lexer.buffer = None
        raise LexerError(
            'Error on line %s, col %s while lexing DICTPATH: Unexpected character: %s' %
            (t.lexer.lineno, t.lexpos - t.lexer.latest_newline, t.value[0])
        )

    @staticmethod
    def t_newline(t):
        r'\n'
        t.lexer.lineno += 1
        t.lexer.latest_newline = t.lexpos + 1

    @staticmethod
    def t_error(t):
        raise LexerError(
            'Error on line %s, col %s: Unexpected character: %s' %
            (t.lexer.lineno, t.lexpos - t.lexer.latest_newline, t.value[0])
        )

    # compound_tokens
    def t_ID(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_\-]*'
        t.type = self.reserved_words.get(t.value, 'ID')
        return t

    def tokenize(self, s):
        """Tokenize the input string. 'lineno' starts from 1 and 'col' starts from 1"""
        self.lexer.latest_newline = 0
        self.lexer.input(s)

        while True:
            t = self.lexer.token()
            if t is None:
                break
            t.col_offset = t.lexpos - self.lexer.latest_newline + 1 # lexpos starts from 0
            yield t

        if hasattr(self.lexer, 'buffer') and self.lexer.buffer is not None:
            self.cleanup()
            raise LexerError('Unexpected EOF in string literal: %s' % s)

    def cleanup(self):
        if hasattr(self.lexer, 'buffer') and self.lexer.buffer is not None:
            self.lexer.buffer.close()
            self.lexer.buffer = None
