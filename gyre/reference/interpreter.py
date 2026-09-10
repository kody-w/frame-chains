"""Execute a deliberately small Python/data language without exec or eval.

The guest has expressions, functions, and control flow, but no imports, object
introspection, host objects, I/O, or access to this module's Python namespace.
This is a bounded interpreter, not a claim that venvs sandbox arbitrary Python.
"""

import ast
import json
import operator
import sys


MAX_SOURCE = 24000
MAX_NODES = 5000
MAX_STEPS = 120000
MAX_ITEMS = 4096
MAX_TEXT = 8192
MAX_INT = 10**12
MAX_DEPTH = 80


class GuestRejected(Exception):
    pass


class GuestLimit(Exception):
    pass


class Returned(Exception):
    def __init__(self, value):
        self.value = value


class Broken(Exception):
    pass


class Continued(Exception):
    pass


BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}
COMPARE = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.Is: operator.is_, ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}
METHODS = {
    str: {"strip", "lstrip", "rstrip", "split", "isdigit", "isdecimal", "isspace",
          "startswith", "endswith", "find", "count", "join"},
    list: {"append", "extend", "pop", "copy", "clear", "reverse"},
    dict: {"get", "keys", "values", "items", "copy"},
}
BUILTINS = {
    "len", "int", "str", "bool", "list", "tuple", "range", "enumerate", "zip",
    "min", "max", "abs", "all", "any", "sum", "sorted", "isinstance", "ValueError",
}
TYPE_MARKERS = {name: object() for name in ("str", "int", "bool", "list", "tuple")}
TYPES = {"str": str, "int": int, "bool": bool, "list": list, "tuple": tuple}
ALLOWED = (
    ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
    ast.Assign, ast.AugAssign, ast.Expr, ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass, ast.Raise, ast.Call, ast.Name,
    ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple, ast.Dict,
    ast.Subscript, ast.Slice, ast.Attribute, ast.UnaryOp, ast.UAdd,
    ast.USub, ast.Not, ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv,
    ast.Mod, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Eq, ast.NotEq,
    ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
    ast.IfExp, ast.keyword,
)


def bounded(value):
    if isinstance(value, int) and abs(value) > MAX_INT:
        raise GuestLimit("integer bound")
    if isinstance(value, str) and len(value) > MAX_TEXT:
        raise GuestLimit("text bound")
    if isinstance(value, (list, tuple, dict, range)) and len(value) > MAX_ITEMS:
        raise GuestLimit("collection bound")
    return value


class Program:
    def __init__(self, source):
        if len(source.encode("utf-8")) > MAX_SOURCE:
            raise GuestRejected("source byte limit")
        self.tree = ast.parse(source)
        nodes = list(ast.walk(self.tree))
        if len(nodes) > MAX_NODES:
            raise GuestRejected("AST size limit")
        self.nodes = len(nodes)
        self.functions = {}
        self.constants = {}
        self.steps = 0
        self.depth = 0
        attribute_calls = {
            id(node.func) for node in nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        for node in nodes:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id in BUILTINS or node.id in self.functions:
                    raise GuestRejected("do not shadow callable names")
            if isinstance(node, ast.arg) and (
                node.arg in BUILTINS or node.arg in self.functions
            ):
                raise GuestRejected("do not shadow callable names")
            if not isinstance(node, ALLOWED):
                raise GuestRejected(f"unsupported syntax: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise GuestRejected("dunder names are not guest capabilities")
            if isinstance(node, ast.Attribute) and (
                id(node) not in attribute_calls
                or node.attr.startswith("_")
                or node.attr not in set().union(*METHODS.values())
            ):
                raise GuestRejected("unsupported attribute access")
            if isinstance(node, ast.Constant):
                if not (node.value is None or type(node.value) in (str, int, bool)):
                    raise GuestRejected("unsupported literal")
                bounded(node.value)
            if isinstance(node, ast.Raise) and node.cause is not None:
                raise GuestRejected("exception chaining is not supported")
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("__") or node.decorator_list:
                    raise GuestRejected("unsupported function declaration")
                if node.args.vararg or node.args.kwarg or node.args.kwonlyargs or node.args.posonlyargs:
                    raise GuestRejected("use ordinary positional parameters")
                if any(arg.arg.startswith("__") for arg in node.args.args):
                    raise GuestRejected("unsupported argument name")
                if any(not isinstance(value, ast.Constant) for value in node.args.defaults):
                    raise GuestRejected("function defaults must be literal values")
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in self.functions or node.name in BUILTINS:
                    raise GuestRejected("duplicate or reserved function name")
                self.functions[node.name] = node
            elif isinstance(node, ast.Assign):
                if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                    raise GuestRejected("module constants need simple names")
                if not isinstance(node.value, ast.Constant):
                    raise GuestRejected("module constants must be scalar literals")
                self.constants[node.targets[0].id] = node.value.value
            elif not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                raise GuestRejected("module may contain only functions and scalar constants")
        if "solve" not in self.functions:
            raise GuestRejected("missing solve(expression)")
        for node in nodes:
            if isinstance(node, ast.FunctionDef) and node not in self.tree.body:
                raise GuestRejected("helpers must be top-level functions")
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in self.functions:
                raise GuestRejected("do not shadow guest functions")
            if isinstance(node, ast.arg) and node.arg in self.functions:
                raise GuestRejected("do not shadow guest functions")
            if isinstance(node, ast.Call) and not isinstance(node.func, (ast.Name, ast.Attribute)):
                raise GuestRejected("dynamic calls are not supported")

    def tick(self):
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise GuestLimit("instruction budget")

    def invoke(self, name, args, kwargs):
        self.tick()
        if name in self.functions:
            function = self.functions[name]
            names = [arg.arg for arg in function.args.args]
            if len(args) > len(names) or set(kwargs) - set(names):
                raise GuestRejected("function argument mismatch")
            env = dict(zip(names, args))
            if set(env) & set(kwargs):
                raise GuestRejected("duplicate function argument")
            env.update(kwargs)
            defaults = dict(zip(names[len(names) - len(function.args.defaults):], function.args.defaults))
            for parameter in names:
                if parameter not in env:
                    if parameter not in defaults:
                        raise GuestRejected("missing function argument")
                    env[parameter] = defaults[parameter].value
            self.depth += 1
            if self.depth > MAX_DEPTH:
                raise GuestLimit("call depth")
            try:
                self.block(function.body, env)
            except Returned as returned:
                return bounded(returned.value)
            finally:
                self.depth -= 1
            return None
        if name not in BUILTINS:
            raise GuestRejected(f"unavailable capability: {name}")
        if name == "ValueError":
            if len(args) > 1 or kwargs:
                raise GuestRejected("ValueError takes an optional plain message")
            return ValueError(args[0] if args else "invalid expression")
        if name == "range":
            value = range(*args, **kwargs)
            if len(value) > MAX_ITEMS:
                raise GuestLimit("range bound")
            return value
        if name == "enumerate":
            return enumerate(*args, **kwargs)
        if name == "zip":
            return zip(*args, **kwargs)
        if name == "isinstance":
            markers = args[1] if isinstance(args[1], tuple) else (args[1],)
            kinds = []
            for marker in markers:
                matches = [TYPES[key] for key, value in TYPE_MARKERS.items() if marker is value]
                if not matches:
                    raise TypeError("isinstance needs supported type names")
                kinds.append(matches[0])
            return isinstance(args[0], tuple(kinds))
        if name == "str" and args and type(args[0]) not in (int, str, bool, type(None)):
            raise GuestRejected("str conversion is limited to scalar values")
        if name == "sum" and (len(args) != 1 or any(type(item) not in (int, bool) for item in args[0])):
            raise GuestRejected("sum is limited to one integer collection")
        functions = {
            "len": len, "int": int, "str": str, "bool": bool, "list": list,
            "tuple": tuple, "min": min, "max": max, "abs": abs, "all": all,
            "any": any, "sum": sum, "sorted": sorted,
        }
        if kwargs:
            raise GuestRejected("keywords are only supported on guest helper calls")
        return bounded(functions[name](*args))

    def method(self, obj, name, args, kwargs):
        if type(obj) not in METHODS or name not in METHODS[type(obj)]:
            raise GuestRejected("method is not a guest capability")
        if kwargs:
            raise GuestRejected("method keywords are not supported")
        if name == "append" and len(obj) >= MAX_ITEMS:
            raise GuestLimit("append bound")
        if name == "extend" and len(obj) + len(args[0]) > MAX_ITEMS:
            raise GuestLimit("extend bound")
        if name == "join":
            if len(args[0]) > MAX_ITEMS or sum(len(item) for item in args[0]) + len(obj) * len(args[0]) > MAX_TEXT:
                raise GuestLimit("join bound")
        value = getattr(obj, name)(*args)
        if name in ("keys", "values", "items"):
            value = list(value)
        return bounded(value)

    def binary(self, op, left, right):
        if isinstance(op, ast.Mult):
            if isinstance(left, (str, list, tuple)) and isinstance(right, int):
                if len(left) * max(0, right) > MAX_ITEMS:
                    raise GuestLimit("repetition bound")
            elif isinstance(right, (str, list, tuple)) and isinstance(left, int):
                if len(right) * max(0, left) > MAX_ITEMS:
                    raise GuestLimit("repetition bound")
        if isinstance(op, ast.Add) and isinstance(left, (str, list, tuple)):
            if len(left) + len(right) > MAX_ITEMS:
                raise GuestLimit("concatenation bound")
        if isinstance(op, ast.Mod) and not isinstance(left, int):
            raise GuestRejected("only integer modulo is supported")
        return bounded(BINOPS[type(op)](left, right))

    def expr(self, node, env):
        self.tick()
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in self.constants:
                return self.constants[node.id]
            if node.id in ("str", "int", "bool", "list", "tuple"):
                return TYPE_MARKERS[node.id]
            raise GuestRejected(f"unbound name: {node.id}")
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [self.expr(item, env) for item in node.elts]
            return bounded(tuple(values) if isinstance(node, ast.Tuple) else values)
        if isinstance(node, ast.Dict):
            return bounded({self.expr(k, env): self.expr(v, env) for k, v in zip(node.keys, node.values)})
        if isinstance(node, ast.UnaryOp):
            value = self.expr(node.operand, env)
            return bounded({ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}[type(node.op)](value))
        if isinstance(node, ast.BinOp):
            return self.binary(node.op, self.expr(node.left, env), self.expr(node.right, env))
        if isinstance(node, ast.BoolOp):
            for operand in node.values:
                value = self.expr(operand, env)
                if isinstance(node.op, ast.And) and not value:
                    return value
                if isinstance(node.op, ast.Or) and value:
                    return value
            return value
        if isinstance(node, ast.Compare):
            value = self.expr(node.left, env)
            for op, other in zip(node.ops, node.comparators):
                right = self.expr(other, env)
                if not COMPARE[type(op)](value, right):
                    return False
                value = right
            return True
        if isinstance(node, ast.IfExp):
            return self.expr(node.body if self.expr(node.test, env) else node.orelse, env)
        if isinstance(node, ast.Slice):
            return slice(*[self.expr(item, env) if item else None for item in (node.lower, node.upper, node.step)])
        if isinstance(node, ast.Subscript):
            return bounded(self.expr(node.value, env)[self.expr(node.slice, env)])
        if isinstance(node, ast.Call):
            args = [self.expr(arg, env) for arg in node.args]
            kwargs = {arg.arg: self.expr(arg.value, env) for arg in node.keywords}
            if isinstance(node.func, ast.Name):
                return self.invoke(node.func.id, args, kwargs)
            return self.method(self.expr(node.func.value, env), node.func.attr, args, kwargs)
        raise GuestRejected(f"unsupported expression: {type(node).__name__}")

    def assign(self, target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = bounded(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            if len(target.elts) != len(value):
                raise GuestRejected("unpacking mismatch")
            for item, part in zip(target.elts, value):
                self.assign(item, part, env)
        elif isinstance(target, ast.Subscript):
            obj = self.expr(target.value, env)
            key = self.expr(target.slice, env)
            if isinstance(key, slice):
                raise GuestRejected("slice assignment is not supported")
            if not isinstance(obj, (list, dict)):
                raise GuestRejected("assignment needs a list or dictionary")
            if isinstance(obj, dict) and key not in obj and len(obj) >= MAX_ITEMS:
                raise GuestLimit("dictionary bound")
            obj[key] = bounded(value)
        else:
            raise GuestRejected("unsupported assignment target")

    def block(self, body, env):
        for node in body:
            self.tick()
            if isinstance(node, ast.Return):
                raise Returned(self.expr(node.value, env) if node.value else None)
            if isinstance(node, ast.Assign):
                value = self.expr(node.value, env)
                for target in node.targets:
                    self.assign(target, value, env)
            elif isinstance(node, ast.AugAssign):
                value = self.binary(node.op, self.expr(node.target, env), self.expr(node.value, env))
                self.assign(node.target, value, env)
            elif isinstance(node, ast.Expr):
                self.expr(node.value, env)
            elif isinstance(node, ast.If):
                self.block(node.body if self.expr(node.test, env) else node.orelse, env)
            elif isinstance(node, (ast.For, ast.While)):
                broke = False
                values = iter(self.expr(node.iter, env)) if isinstance(node, ast.For) else None
                while True:
                    self.tick()
                    if values is not None:
                        try:
                            value = next(values)
                        except StopIteration:
                            break
                        self.assign(node.target, value, env)
                    elif not self.expr(node.test, env):
                        break
                    try:
                        self.block(node.body, env)
                    except Continued:
                        continue
                    except Broken:
                        broke = True
                        break
                if not broke:
                    self.block(node.orelse, env)
            elif isinstance(node, ast.Break):
                raise Broken()
            elif isinstance(node, ast.Continue):
                raise Continued()
            elif isinstance(node, ast.Raise):
                if isinstance(node.exc, ast.Name) and node.exc.id == "ValueError":
                    raise ValueError()
                error = self.expr(node.exc, env)
                if type(error) is not ValueError:
                    raise GuestRejected("only explicit ValueError may be raised")
                raise error
            elif not isinstance(node, ast.Pass):
                raise GuestRejected(f"unsupported statement: {type(node).__name__}")

    def run(self, expression):
        self.steps = 0
        self.depth = 0
        result = self.invoke("solve", [expression], {})
        if not isinstance(result, list) or len(result) > 256:
            raise GuestRejected("solve must return a list of at most 256 integers")
        if any(type(value) is not int for value in result):
            raise GuestRejected("solve returned a non-integer")
        return result


def evaluate(source, cases):
    try:
        program = Program(source)
    except (GuestRejected, GuestLimit, SyntaxError, ValueError) as error:
        return {"admitted": False, "reason": str(error)[:300], "results": []}
    outcomes = []
    for case in cases:
        try:
            value = program.run(case["expression"])
            outcome = {"kind": "value", "value": value}
        except ValueError:
            outcome = {"kind": "error", "error": "ValueError"}
        except (GuestRejected, GuestLimit, TypeError, IndexError, KeyError, ZeroDivisionError, RecursionError) as error:
            outcome = {"kind": "execution_error", "error": type(error).__name__, "detail": str(error)[:200]}
        outcomes.append({"id": case["id"], "outcome": outcome, "steps": program.steps})
    return {"admitted": True, "ast_nodes": program.nodes, "results": outcomes}


if __name__ == "__main__":
    request = json.load(sys.stdin)
    print(json.dumps(evaluate(request["source"], request["cases"]), separators=(",", ":")))
