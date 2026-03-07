from cmate._ast import (
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
    Node,
    Partition,
    Rule,
    UnaryOp,
)


class TestNode:
    """Tests for base Node class"""

    def test_node_is_base_class(self):
        """Test that Node is the base class"""
        node = Node()
        assert isinstance(node, Node)


class TestDocument:
    """Tests for Document AST node"""

    def test_document_creation(self):
        """Test Document node creation"""
        body = []
        doc = Document(body)
        assert doc.body == body

    def test_document_with_body(self):
        """Test Document with actual body"""
        meta = Meta([])
        doc = Document([meta])
        assert len(doc.body) == 1
        assert isinstance(doc.body[0], Meta)


class TestMeta:
    """Tests for Meta AST node"""

    def test_meta_creation(self):
        """Test Meta node creation"""
        body = []
        meta = Meta(body)
        assert meta.body == body

    def test_meta_with_assignments(self):
        """Test Meta with assignments"""
        name = Name(1, 1, "version")
        const = Constant(1, 10, "1.0")
        assign = Assign(1, 1, name, const)
        meta = Meta([assign])
        assert len(meta.body) == 1


class TestGlobal:
    """Tests for Global AST node"""

    def test_global_creation(self):
        """Test Global node creation"""
        body = []
        global_node = Global(body)
        assert global_node.body == body


class TestDependency:
    """Tests for Dependency AST node"""

    def test_dependency_creation(self):
        """Test Dependency node creation"""
        body = []
        dep = Dependency(body)
        assert dep.body == body


class TestPartition:
    """Tests for Partition AST node"""

    def test_partition_creation(self):
        """Test Partition node creation"""
        target = Name(1, 5, "test_target")
        body = []
        partition = Partition(target, body)
        assert partition.target == target
        assert partition.body == body

    def test_partition_with_rules(self):
        """Test Partition with rules"""
        target = Name(1, 5, "env")
        const = Constant(2, 10, True)
        rule = Rule(2, 1, const, "test message", None)
        partition = Partition(target, [rule])
        assert partition.target.id == "env"
        assert len(partition.body) == 1


class TestAssign:
    """Tests for Assign AST node"""

    def test_assign_creation(self):
        """Test Assign node creation"""
        target = Name(1, 1, "variable")
        value = Constant(1, 10, 42)
        assign = Assign(1, 1, target, value)
        assert assign.target == target
        assert assign.value == value
        assert assign.lineno == 1
        assert assign.col_offset == 1


class TestDesc:
    """Tests for Desc AST node"""

    def test_desc_creation(self):
        """Test Desc node creation"""
        target = Name(1, 1, "config")
        desc = "Configuration description"
        parse_type = "json"
        desc_node = Desc(1, 1, target, desc, parse_type)
        assert desc_node.target == target
        assert desc_node.desc == desc
        assert desc_node.parse_type == parse_type

    def test_desc_without_parse_type(self):
        """Test Desc without parse_type"""
        target = Name(1, 1, "config")
        desc_node = Desc(1, 1, target, "desc", None)
        assert desc_node.parse_type is None


class TestFor:
    """Tests for For AST node"""

    def test_for_creation(self):
        """Test For node creation"""
        target = Name(1, 5, "item")
        it = Name(1, 12, "items")
        body = []
        for_node = For(1, 1, target, it, body)
        assert for_node.target == target
        assert for_node.it == it
        assert for_node.body == body

    def test_for_with_body(self):
        """Test For with body"""
        target = Name(1, 5, "i")
        it = List(1, 10, [Constant(1, 11, 1), Constant(1, 13, 2)])
        assign = Assign(2, 5, Name(2, 5, "x"), Constant(2, 10, 1))
        for_node = For(1, 1, target, it, [assign])
        assert len(for_node.body) == 1


class TestIf:
    """Tests for If AST node"""

    def test_if_creation(self):
        """Test If node creation"""
        test = Constant(1, 4, True)
        body = []
        if_node = If(1, 1, test, body)
        assert if_node.test == test
        assert if_node.body == body
        assert if_node.orelse is None

    def test_if_with_else(self):
        """Test If with else branch"""
        test = Constant(1, 4, True)
        body = [Assign(2, 5, Name(2, 5, "a"), Constant(2, 10, 1))]
        orelse = [Assign(4, 5, Name(4, 5, "b"), Constant(4, 10, 2))]
        if_node = If(1, 1, test, body, orelse)
        assert if_node.orelse == orelse


class TestRule:
    """Tests for Rule AST node"""

    def test_rule_creation(self):
        """Test Rule node creation"""
        test = Compare(1, 8, Constant(1, 8, 5), ">", Constant(1, 12, 0))
        msg = "Value must be positive"
        severity = "error"
        rule = Rule(1, 1, test, msg, severity)
        assert rule.test == test
        assert rule.msg == msg
        assert rule.severity == severity


class TestBreak:
    """Tests for Break AST node"""

    def test_break_creation(self):
        """Test Break node creation"""
        break_node = Break(5, 9)
        assert break_node.lineno == 5
        assert break_node.col_offset == 9


class TestContinue:
    """Tests for Continue AST node"""

    def test_continue_creation(self):
        """Test Continue node creation"""
        continue_node = Continue(5, 9)
        assert continue_node.lineno == 5
        assert continue_node.col_offset == 9


class TestUnaryOp:
    """Tests for UnaryOp AST node"""

    def test_unaryop_creation(self):
        """Test UnaryOp node creation"""
        operand = Constant(1, 9, True)
        op = "not"
        unary = UnaryOp(1, 5, op, operand)
        assert unary.op == op
        assert unary.operand == operand


class TestBinOp:
    """Tests for BinOp AST node"""

    def test_binop_creation(self):
        """Test BinOp node creation"""
        left = Constant(1, 1, 5)
        op = "+"
        right = Constant(1, 5, 3)
        binop = BinOp(1, 1, left, op, right)
        assert binop.left == left
        assert binop.op == op
        assert binop.right == right


class TestCompare:
    """Tests for Compare AST node"""

    def test_compare_creation(self):
        """Test Compare node creation"""
        left = Constant(1, 1, 5)
        op = "=="
        comparator = Constant(1, 6, 5)
        compare = Compare(1, 1, left, op, comparator)
        assert compare.left == left
        assert compare.op == op
        assert compare.comparator == comparator

    def test_compare_different_ops(self):
        """Test Compare with different operators"""
        left = Constant(1, 1, 5)
        right = Constant(1, 6, 10)

        for op in ["==", "!=", "<", ">", "<=", ">=", "=~", "in", "not in"]:
            compare = Compare(1, 1, left, op, right)
            assert compare.op == op


class TestCall:
    """Tests for Call AST node"""

    def test_call_creation(self):
        """Test Call node creation"""
        func = Name(1, 1, "my_func")
        args = [Constant(1, 10, 1), Constant(1, 13, 2)]
        keywords = []
        call = Call(1, 1, func, args, keywords)
        assert call.func == func
        assert call.args == args
        assert call.keywords == keywords

    def test_call_no_args(self):
        """Test Call with no arguments"""
        func = Name(1, 1, "func")
        call = Call(1, 1, func, [], [])
        assert call.args == []
        assert call.keywords == []


class TestName:
    """Tests for Name AST node"""

    def test_name_creation(self):
        """Test Name node creation"""
        id_ = "variable_name"
        name = Name(1, 1, id_)
        assert name.id == id_

    def test_name_with_dash(self):
        """Test Name with dash in identifier"""
        name = Name(1, 1, "var-name")
        assert name.id == "var-name"


class TestDictPath:
    """Tests for DictPath AST node"""

    def test_dictpath_without_namespace(self):
        """Test DictPath without namespace"""
        path = "key.subkey"
        dictpath = DictPath(1, 3, path)
        assert dictpath.namespace is None
        assert dictpath.path == path

    def test_dictpath_with_namespace(self):
        """Test DictPath with namespace"""
        path = "global::config.key"
        dictpath = DictPath(1, 3, path)
        assert dictpath.namespace == "global"
        assert dictpath.path == "config.key"

    def test_dictpath_with_different_namespaces(self):
        """Test DictPath with various namespaces"""
        test_cases = [
            ("env::VAR", "env", "VAR"),
            ("context::setting", "context", "setting"),
            ("config::nested.key", "config", "nested.key"),
            ("test::a.b.c", "test", "a.b.c"),
        ]

        for path, expected_ns, expected_path in test_cases:
            dictpath = DictPath(1, 3, path)
            assert dictpath.namespace == expected_ns
            assert dictpath.path == expected_path

    def test_dictpath_multiple_separators(self):
        """Test DictPath with multiple :: in path"""
        # Only first :: should be treated as namespace separator
        path = "global::config::key"
        dictpath = DictPath(1, 3, path)
        assert dictpath.namespace == "global"
        assert dictpath.path == "config::key"


class TestList:
    """Tests for List AST node"""

    def test_list_creation_empty(self):
        """Test List node creation with empty elements"""
        list_node = List(1, 5, [])
        assert list_node.elts == []

    def test_list_creation_with_elements(self):
        """Test List node creation with elements"""
        elts = [Constant(1, 6, 1), Constant(1, 9, 2), Constant(1, 12, 3)]
        list_node = List(1, 5, elts)
        assert list_node.elts == elts


class TestDict:
    """Tests for Dict AST node"""

    def test_dict_creation_empty(self):
        """Test Dict node creation with empty keys/values"""
        dict_node = Dict(1, 5, [], [])
        assert dict_node.keys == []
        assert dict_node.values == []

    def test_dict_creation_with_items(self):
        """Test Dict node creation with items"""
        keys = [Constant(1, 6, "a"), Constant(1, 12, "b")]
        values = [Constant(1, 10, 1), Constant(1, 16, 2)]
        dict_node = Dict(1, 5, keys, values)
        assert dict_node.keys == keys
        assert dict_node.values == values


class TestConstant:
    """Tests for Constant AST node"""

    def test_constant_creation_int(self):
        """Test Constant node with integer"""
        const = Constant(1, 5, 42)
        assert const.value == 42

    def test_constant_creation_string(self):
        """Test Constant node with string"""
        const = Constant(1, 5, "hello")
        assert const.value == "hello"

    def test_constant_creation_bool(self):
        """Test Constant node with boolean"""
        const = Constant(1, 5, True)
        assert const.value is True

    def test_constant_creation_none(self):
        """Test Constant node with None"""
        const = Constant(1, 5, None)
        assert const.value is None
