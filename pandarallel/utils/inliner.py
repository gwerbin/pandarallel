import ast
import inspect
from types import FunctionType


def pin_arguments(
    func: FunctionType, immutable_arguments: dict, mutable_arguments: dict
):
    """Return the AST of `func` transformed in a function with no arguments.

    Example:

    def func(a, b):
        c = 4
        print(str(a) + str(c))

        return b

    The AST returned by pin_arguments(func, {"a": 10, "b": 11}, {}) has for equivalent
    function:

    def pinned_func():
        c = 4
        print(str(10) + str(c))

        return 11

    This function is in some ways equivalent to functools.partials but with a faster
    runtime.
    """

    class Visitor(ast.NodeTransformer):
        def visit_Name(self, node):
            if not node.id in immutable_arguments:
                ast.NodeVisitor.generic_visit(self, node)
                return node

            value = immutable_arguments[node.id]

            new_node = ast.Constant(value)
            ast.copy_location(new_node, node)
            ast.NodeVisitor.generic_visit(self, node)
            return new_node

    func_code = inspect.getsource(func)
    func_ast = ast.parse(func_code)

    pinned_func_ast = Visitor().visit(func_ast)

    body, *trash = pinned_func_ast.body
    assert not trash

    return body.body


def inline(
    pre_func: FunctionType,
    func: FunctionType,
    immutable_pre_func_arguments: dict,
    mutable_pre_func_arguments: dict,
):
    """Insert `prefunc` at the beginning of `func` and return the corresponding
    function.

    This approach takes less CPU instructions than the standard decorator approach.

    Example:

    def pre_func(b, c):
        a = "hello"
        print(a + " " + b + " " + c)

    def func(x, y):
        z = x + 2 * y
        return z ** 2

    The returned function if `pre_fun_arguments == {"b": "foo", "c": "bar"}
    corresponds to:

    def inlined(x, y):
        a = "hello"
        print(a + " " + "foo" + " " + "bar")
        z = x + 2 * y
        return z ** 2
    """
    pinned_pre_func_ast_body_body = pin_arguments(
        pre_func, immutable_pre_func_arguments, mutable_pre_func_arguments
    )

    func_code = inspect.getsource(func)
    func_ast = ast.parse(func_code)

    func_body, *trash = func_ast.body
    assert not trash

    func_body.body = pinned_pre_func_ast_body_body + func_body.body

    namespace = {}

    compiled = compile(func_ast, filename="pandarallel", mode="exec")
    exec(compiled, namespace)

    inlined_func = namespace[func_body.name]

    for key, value in func.__globals__.items():
        inlined_func.__globals__[key] = value

    return inlined_func
