class Node:
    pass


class Mod(Node):
    __slots__ = ('body',)
    
    def __init__(self, body):
        self.body = body


class Stmt(Node):
    __slots__ = ('lineno', 'col_offset')
    
    def __init__(self, lineno: int, col_offset: int):
        self.lineno = lineno
        self.col_offset = col_offset


class Expr(Node):
    __slots__ = ('lineno', 'col_offset')
    
    def __init__(self, lineno: int, col_offset: int):
        super().__init__()
        self.lineno = lineno
        self.col_offset = col_offset


class Document(Mod):
    pass


class Meta(Mod):
    pass


class Global(Mod):
    pass


class Dependency(Mod):
    pass


class Partition(Mod):
    __slots__ = ('target',) + Mod.__slots__
    
    def __init__(self, target, body):
        super().__init__(body)
        self.target = target


class Assign(Stmt):
    __slots__ = ('target', 'value') + Stmt.__slots__
    
    def __init__(self, lineno, col_offset, target, value):
        super().__init__(lineno, col_offset)
        self.target = target
        self.value = value


class Desc(Stmt):
    __slots__ = ('target', 'desc', 'parse_type') + Stmt.__slots__
    
    def __init__(self, lineno, col_offset, target, desc, parse_type):
        super().__init__(lineno, col_offset)
        self.target = target
        self.desc = desc
        self.parse_type = parse_type


class For(Stmt):
    __slots__ = ('target', 'it', 'body') + Stmt.__slots__
    
    def __init__(self, lineno, col_offset, target, it, body):
        super().__init__(lineno, col_offset)
        self.target = target
        self.it = it
        self.body = body


class If(Stmt):
    __slots__ = ('test', 'body', 'orelse') + Stmt.__slots__
    
    def __init__(self, lineno, col_offset, test, body, orelse=None):
        super().__init__(lineno, col_offset)
        self.test = test
        self.body = body
        self.orelse = orelse


class Rule(Stmt):
    __slots__ = ('test', 'msg', 'severity') + Stmt.__slots__
    
    def __init__(self, lineno, col_offset, test, msg, severity):
        super().__init__(lineno, col_offset)
        self.test = test
        self.msg = msg
        self.severity = severity
    

class Break(Stmt):
    pass


class Continue(Stmt):
    pass


class UnaryOp(Expr):
    __slots__ = ('op', 'operand') + Expr.__slots__
    
    def __init__(self, lineno, col_offset, op, operand):
        super().__init__(lineno, col_offset)
        self.op = op
        self.operand = operand


class BinOp(Expr):
    __slots__ = ('left', 'op', 'right') + Expr.__slots__
    
    def __init__(self, lineno, col_offset, left, op, right):
        super().__init__(lineno, col_offset)
        self.left = left
        self.op = op
        self.right = right


class Compare(Expr):
    __slots__ = ('left', 'op', 'comparator') + Expr.__slots__
    
    def __init__(self, lineno, col_offset, left, op, comparator):
        super().__init__(lineno, col_offset)
        self.left = left
        self.op = op
        self.comparator = comparator


class Call(Expr):
    __slots__ = ('func', 'args', 'keywords') + Expr.__slots__
    
    def __init__(self, lineno, col_offset, func, args, keywords):
        super().__init__(lineno, col_offset)
        self.func = func
        self.args = args
        self.keywords = keywords


class Name(Expr):
    __slots__ = ('id',) + Expr.__slots__
    
    def __init__(self, lineno, col_offset, id_):
        super().__init__(lineno, col_offset)
        self.id = id_


class DictPath(Expr):
    __slots__ = ('namespace', 'path') + Expr.__slots__
    
    def __init__(self, lineno, col_offset, path):
        super().__init__(lineno, col_offset)

        ns_symbol = '::'
        if ns_symbol not in path:
            self.namespace = None
            self.path = path
        else:
            self.namespace, self.path = path.split(ns_symbol, 1)


class List(Expr):
    __slots__ = ('elts',) + Expr.__slots__
    
    def __init__(self, lineno, col_offset, elts):
        super().__init__(lineno, col_offset)
        self.elts = elts


class Dict(Expr):
    __slots__ = ('keys', 'values') + Expr.__slots__
    
    def __init__(self, lineno, col_offset, keys, values):
        super().__init__(lineno, col_offset)
        self.keys = keys
        self.values = values


class Constant(Expr):
    __slots__ = ('value',) + Expr.__slots__
    
    def __init__(self, lineno, col_offset, value):
        super().__init__(lineno, col_offset)
        self.value = value
