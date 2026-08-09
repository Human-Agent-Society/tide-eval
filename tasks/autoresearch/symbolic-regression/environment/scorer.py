"""Public scorer (untrusted by design): RMSE on the TRAINING points only.

The trusted grade uses held-out points you never see — an expression that
merely memorizes these training points will collapse there. Find the
structure, not the samples.
"""

import ast
import json
import math
import operator
import sys
from pathlib import Path

TRAIN = json.loads(Path("/app/train.json").read_text())["points"]

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "exp": math.exp,
    "log": math.log,
    "sqrt": math.sqrt,
    "abs": abs,
}


def _eval_node(node, x):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, x)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id == "x":
        return x
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](
            _eval_node(node.left, x), _eval_node(node.right, x)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval_node(node.operand, x))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCS
        and len(node.args) == 1
        and not node.keywords
    ):
        return _FUNCS[node.func.id](_eval_node(node.args[0], x))
    raise ValueError("disallowed syntax")


def score(path: str) -> float:
    expr = json.loads(Path(path).read_text())["expr"]
    tree = ast.parse(expr, mode="eval")
    errs = [(_eval_node(tree, x) - y) ** 2 for x, y in TRAIN]
    return 1.0 / (1.0 + math.sqrt(sum(errs) / len(errs)))


if __name__ == "__main__":
    print(score(sys.argv[1] if len(sys.argv) > 1 else "/app/best/solution.json"))
