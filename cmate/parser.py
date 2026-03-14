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

from ply import yacc

from ._ast import (
    Assign,
    BinOp,
    Break,
    Call,
    Compare,
    Constant,
    Continue,
    Dependency,
    Desc,
    Dict,
    DictPath,
    Document,
    For,
    Global,
    If,
    List,
    Meta,
    Name,
    Partition,
    Rule,
    UnaryOp,
)
from .lexer import Lexer

from .util import Severity


class ParserError(Exception):
    pass


class IteratorToTokenStream:
    def __init__(self, iterator):
        self.iterator = iterator

    def token(self):
        try:
            return next(self.iterator)
        except StopIteration:
            return None


class Parser:
    tokens = Lexer.tokens
    start = "document"

    def __init__(self, lexer=None, errorlog=None):
        self.lexer = lexer or Lexer(errorlog=errorlog)
        self.parser = yacc.yacc(
            module=self,
            debug=False,
            write_tables=False,
            optimize=True,
            errorlog=errorlog,
        )

    precedence = (
        ("left", "OR"),
        ("left", "AND"),
        ("right", "NOT"),
        ("nonassoc", "IN"),
        ("nonassoc", "EQ", "NE", "LT", "LE", "GT", "GE", "RE"),
        ("left", "ADD", "SUB"),
        ("left", "MUL", "TRUEDIV", "FLOORDIV", "MOD"),
        ("right", "POW"),
    )

    @staticmethod
    def p_error(p):
        if p:
            raise ParserError(
                f'Syntax error at line {p.lineno}, column {p.col_offset}. Unexpected token: "{p.value}"'
            )
        else:
            raise ParserError(
                "Syntax error: Unexpected end of file. Expected more tokens to complete the document."
            )

    @staticmethod
    def p_document(p):
        """
        document :
                 | body_list
        """
        body = [] if len(p) == 1 else p[1]
        p[0] = Document(body)

    @staticmethod
    def p_body_list(p):
        """
        body_list : body
                  | body_list body
        """

        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    @staticmethod
    def p_body(p):
        """
        body : meta
             | global
             | dependency
             | partition
        """
        p[0] = p[1]

    @staticmethod
    def p_meta(p):
        "meta : '[' METADATA ']' assign_stmts END"
        p[0] = Meta(p[4])

    @staticmethod
    def p_assign_stmts(p):
        """
        assign_stmts : assign_stmt
                     | assign_stmts assign_stmt
        """
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[2]]

    @staticmethod
    def p_assign_stmt(p):
        """
        assign_stmt : name '=' expr
                    | if_assign_stmt
                    | for_assign_stmt
                    | continue
                    | break
        """
        if len(p) == 2:
            p[0] = p[1]
        else:
            target = p[1]
            p[0] = Assign(target.lineno, target.col_offset, target, p[3])

    @staticmethod
    def p_name(p):
        """
        name : ID
        """

        tok = p.slice[1]
        p[0] = Name(tok.lineno, tok.col_offset, tok.value)

    @staticmethod
    def p_expr(p):
        """
        expr : unary_op
             | bin_op
             | compare
             | call
             | name
             | dict_path
             | list
             | dict
             | constant
             | '(' expr ')'
        """
        p[0] = p[1] if len(p) == 2 else p[2]

    @staticmethod
    def p_unary_op(p):
        "unary_op : NOT expr"

        tok = p.slice[1]
        p[0] = UnaryOp(tok.lineno, tok.col_offset, tok.value, p[2])

    @staticmethod
    def p_bin_op(p):
        """
        bin_op : expr ADD expr
               | expr SUB expr
               | expr MUL expr
               | expr TRUEDIV expr
               | expr FLOORDIV expr
               | expr MOD expr
               | expr POW expr
        """

        p[0] = BinOp(p[1].lineno, p[1].col_offset, p[1], p[2], p[3])

    @staticmethod
    def p_compare(p):
        """
        compare : expr OR expr
                | expr AND expr
                | expr LT expr
                | expr LE expr
                | expr EQ expr
                | expr NE expr
                | expr GT expr
                | expr GE expr
                | expr RE expr
                | expr IN expr
                | expr NOT IN expr
        """

        op = "not in" if len(p) == 5 else p[2]
        comparator = p[4] if len(p) == 5 else p[3]
        p[0] = Compare(p[1].lineno, p[1].col_offset, p[1], op, comparator)

    @staticmethod
    def p_call(p):
        """
        call : func '(' args ')'
        """

        func = p[1]
        args = p[3]
        p[0] = Call(func.lineno, func.col_offset, func, args, [])

    @staticmethod
    def p_func(p):
        "func : name"

        p[0] = p[1]

    @staticmethod
    def p_args(p):
        """
        args :
             | arg
             | args ',' arg
        """

        if len(p) == 1:
            p[0] = []
        elif len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    @staticmethod
    def p_arg(p):
        "arg : expr"

        p[0] = p[1]

    @staticmethod
    def p_dict_path(p):
        "dict_path : DICTPATH"

        tok = p.slice[1]
        p[0] = DictPath(tok.lineno, tok.col_offset, tok.value)

    @staticmethod
    def p_list(p):
        "list : '[' elts ']'"

        tok = p.slice[1]
        p[0] = List(tok.lineno, tok.col_offset, p[2])

    @staticmethod
    def p_elts(p):
        """
        elts :
             | elt
             | elts ',' elt
        """

        if len(p) == 1:
            p[0] = []
        elif len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    @staticmethod
    def p_elt(p):
        "elt : expr"

        p[0] = p[1]

    @staticmethod
    def p_dict(p):
        "dict : '{' dict_elts '}'"

        tok = p.slice[1]
        keys, values = p[2]

        p[0] = Dict(tok.lineno, tok.col_offset, keys, values)

    @staticmethod
    def p_dict_elts(p):
        """
        dict_elts :
                  | expr ':' expr
                  | dict_elts ',' expr ':' expr
        """

        if len(p) == 1:
            p[0] = [], []
        elif len(p) == 4:
            p[0] = [p[1]], [p[3]]
        else:
            keys = p[1][0]
            values = p[1][1]
            p[0] = keys + [p[3]], values + [p[5]]

    @staticmethod
    def p_constant(p):
        """
        constant : NUM
                 | STR
                 | SINGLETON
        """

        tok = p.slice[1]
        p[0] = Constant(tok.lineno, tok.col_offset, tok.value)

    @staticmethod
    def p_if_assign_stmt(p):
        """
        if_assign_stmt : IF expr ':' assign_stmts FI
                       | IF expr ':' assign_stmts elif_assign_stmts FI
                       | IF expr ':' assign_stmts ELSE ':' assign_stmts FI
                       | IF expr ':' assign_stmts elif_assign_stmts ELSE ':' assign_stmts FI
        """

        tok = p.slice[1]

        if len(p) == 6:
            orelse = None
        elif len(p) == 7:
            orelse = p[5]  # first elif node
        elif len(p) == 9:
            orelse = p[7]
        else:
            # if -> head -> p[5][1] -> ... -> tail -> p[8]
            head = p[5][0]
            tail = p[5][-1]
            orelse = [head]
            tail.orelse = p[8]
        p[0] = If(tok.lineno, tok.col_offset, p[2], p[4], orelse)

    @staticmethod
    def p_elif_assign_stmts(p):
        """
        elif_assign_stmts : ELIF expr ':' assign_stmts
                          | elif_assign_stmts ELIF expr ':' assign_stmts
        """

        if len(p) == 5:
            tok = p.slice[1]
            p[0] = [If(tok.lineno, tok.col_offset, p[2], p[4])]
        else:
            tok = p.slice[2]

            previous_if = p[1][-1]
            current_if = If(tok.lineno, tok.col_offset, p[3], p[5])
            previous_if.orelse = [current_if]
            p[0] = p[1] + [current_if]

    @staticmethod
    def p_for_assign_stmt(p):
        "for_assign_stmt : FOR name IN expr ':' assign_stmts DONE"

        tok = p.slice[1]
        p[0] = For(tok.lineno, tok.col_offset, p[2], p[4], p[6])

    @staticmethod
    def p_continue(p):
        "continue : CONTINUE"

        tok = p.slice[1]
        p[0] = Continue(tok.lineno, tok.col_offset)

    @staticmethod
    def p_break(p):
        "break : BREAK"

        tok = p.slice[1]
        p[0] = Break(tok.lineno, tok.col_offset)

    @staticmethod
    def p_global(p):
        "global : '[' GLOBAL ']' assign_stmts END"
        p[0] = Global(p[4])

    @staticmethod
    def p_dependency(p):
        "dependency : '[' DEPENDENCY ']' desc_stmts END"
        p[0] = Dependency(p[4])

    @staticmethod
    def p_desc_stmts(p):
        """
        desc_stmts : desc_stmt
                   | desc_stmts desc_stmt
        """

        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    @staticmethod
    def p_desc_stmt(p):
        """
        desc_stmt : name ':' STR
                  | name ':' STR '@' STR
        """

        parse_type = p[5] if len(p) == 6 else None
        p[0] = Desc(p[1].lineno, p[1].col_offset, p[1], p[3], parse_type)

    @staticmethod
    def p_partition(p):
        """
        partition : '[' PAR name ']' rule_stmts
                  | '[' PAR name ']' rule_stmts END
        """

        p[0] = Partition(p[3], p[5])

    @staticmethod
    def p_rule_stmts(p):
        """
        rule_stmts : rule_stmt
                   | rule_stmts rule_stmt
        """

        p[0] = [p[1]] if len(p) == 2 else p[1] + [p[2]]

    @staticmethod
    def p_rule_stmt(p):
        """
        rule_stmt : ASSERT expr ',' STR
                  | ASSERT expr ',' STR ',' severity
                  | if_rule_stmt
                  | for_rule_stmt
                  | continue
                  | break
        """

        tok = p.slice[1]
        if tok.type == "ASSERT":
            severity = Severity.ERROR if len(p) == 5 else p[6]
            p[0] = Rule(tok.lineno, tok.col_offset, p[2], p[4], severity)
        else:
            p[0] = p[1]

    @staticmethod
    def p_severity(p):
        """
        severity : INFO
                 | WARNING
                 | ERROR
        """
        p[0] = Severity[p[1].upper()]

    @staticmethod
    def p_if_rule_stmt(p):
        """
        if_rule_stmt : IF expr ':' rule_stmts FI
                     | IF expr ':' rule_stmts elif_rule_stmts FI
                     | IF expr ':' rule_stmts ELSE ':' rule_stmts FI
                     | IF expr ':' rule_stmts elif_rule_stmts ELSE ':' rule_stmts FI
        """

        tok = p.slice[1]

        if len(p) == 6:
            orelse = None
        elif len(p) == 7:
            orelse = p[5]  # first elif node
        elif len(p) == 9:
            orelse = p[7]
        else:
            # if -> head -> p[5][1] -> ... -> tail -> p[8]
            head = p[5][0]
            tail = p[5][-1]
            orelse = [head]
            tail.orelse = p[8]
        p[0] = If(tok.lineno, tok.col_offset, p[2], p[4], orelse)

    @staticmethod
    def p_elif_rule_stmts(p):
        """
        elif_rule_stmts : ELIF expr ':' rule_stmts
                        | elif_rule_stmts ELIF expr ':' rule_stmts
        """

        if len(p) == 5:
            tok = p.slice[1]
            p[0] = [If(tok.lineno, tok.col_offset, p[2], p[4])]
        else:
            tok = p.slice[2]

            previous_if = p[1][-1]
            current_if = If(tok.lineno, tok.col_offset, p[3], p[5])
            previous_if.orelse = [current_if]
            p[0] = p[1] + [current_if]

    @staticmethod
    def p_for_rule_stmt(p):
        "for_rule_stmt : FOR name IN expr ':' rule_stmts DONE"

        tok = p.slice[1]
        p[0] = For(tok.lineno, tok.col_offset, p[2], p[4], p[6])

    def parse(self, text: str):
        iterator = self.lexer.tokenize(text)
        document = self.parser.parse(lexer=IteratorToTokenStream(iterator))

        return document
