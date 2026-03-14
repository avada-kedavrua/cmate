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


class Node:
    pass


class Mod(Node):
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body


class Stmt(Node):
    __slots__ = ("lineno", "col_offset")

    def __init__(self, lineno: int, col_offset: int):
        self.lineno = lineno
        self.col_offset = col_offset


class Expr(Node):
    __slots__ = ("lineno", "col_offset")

    def __init__(self, lineno: int, col_offset: int):
        self.lineno = lineno
        self.col_offset = col_offset


# --- Mod subclasses ---


class Document(Mod):
    pass


class Meta(Mod):
    pass


class Global(Mod):
    pass


class Dependency(Mod):
    pass


class Partition(Mod):
    # Only declare fields not already in Mod.__slots__
    __slots__ = ("target",)

    def __init__(self, target, body):
        super().__init__(body)
        self.target = target


# --- Stmt subclasses ---


class Assign(Stmt):
    __slots__ = ("target", "value")

    def __init__(self, lineno, col_offset, target, value):
        super().__init__(lineno, col_offset)
        self.target = target
        self.value = value


class Desc(Stmt):
    __slots__ = ("target", "desc", "parse_format")

    def __init__(self, lineno, col_offset, target, desc, parse_format):
        super().__init__(lineno, col_offset)
        self.target = target
        self.desc = desc
        self.parse_format = parse_format


class For(Stmt):
    __slots__ = ("target", "it", "body")

    def __init__(self, lineno, col_offset, target, it, body):
        super().__init__(lineno, col_offset)
        self.target = target
        self.it = it
        self.body = body


class If(Stmt):
    __slots__ = ("test", "body", "orelse")

    def __init__(self, lineno, col_offset, test, body, orelse=None):
        super().__init__(lineno, col_offset)
        self.test = test
        self.body = body
        self.orelse = orelse


class Rule(Stmt):
    __slots__ = ("test", "msg", "severity")

    def __init__(self, lineno, col_offset, test, msg, severity):
        super().__init__(lineno, col_offset)
        self.test = test
        self.msg = msg
        self.severity = severity


class Alert(Stmt):
    """Alert statement for marking fields that need attention.

    Unlike Rule (assert), Alert doesn't evaluate a condition.
    It simply marks a field for attention with a message.
    Default severity is WARNING.
    """

    __slots__ = ("field", "msg", "severity")

    def __init__(self, lineno, col_offset, field, msg, severity):
        super().__init__(lineno, col_offset)
        self.field = field
        self.msg = msg
        self.severity = severity


class Break(Stmt):
    # Inherits lineno/col_offset from Stmt; must call super().__init__
    __slots__ = ()


class Continue(Stmt):
    __slots__ = ()


# --- Expr subclasses ---


class UnaryOp(Expr):
    __slots__ = ("op", "operand")

    def __init__(self, lineno, col_offset, op, operand):
        super().__init__(lineno, col_offset)
        self.op = op
        self.operand = operand


class BinOp(Expr):
    __slots__ = ("left", "op", "right")

    def __init__(self, lineno, col_offset, left, op, right):
        super().__init__(lineno, col_offset)
        self.left = left
        self.op = op
        self.right = right


class Compare(Expr):
    __slots__ = ("left", "op", "comparator")

    def __init__(self, lineno, col_offset, left, op, comparator):
        super().__init__(lineno, col_offset)
        self.left = left
        self.op = op
        self.comparator = comparator


class Call(Expr):
    __slots__ = ("func", "args", "keywords")

    def __init__(self, lineno, col_offset, func, args, keywords):
        super().__init__(lineno, col_offset)
        self.func = func
        self.args = args
        self.keywords = keywords


class Name(Expr):
    __slots__ = ("id",)

    def __init__(self, lineno, col_offset, id_):
        super().__init__(lineno, col_offset)
        self.id = id_


class DictPath(Expr):
    __slots__ = ("namespace", "path")

    def __init__(self, lineno, col_offset, path):
        super().__init__(lineno, col_offset)
        ns_symbol = "::"
        if ns_symbol not in path:
            self.namespace = None
            self.path = path
        else:
            self.namespace, self.path = path.split(ns_symbol, 1)


class List(Expr):
    __slots__ = ("elts",)

    def __init__(self, lineno, col_offset, elts):
        super().__init__(lineno, col_offset)
        self.elts = elts


class Dict(Expr):
    __slots__ = ("keys", "values")

    def __init__(self, lineno, col_offset, keys, values):
        super().__init__(lineno, col_offset)
        self.keys = keys
        self.values = values


class Constant(Expr):
    __slots__ = ("value",)

    def __init__(self, lineno, col_offset, value):
        super().__init__(lineno, col_offset)
        self.value = value
