"""Controlled, inspectable agent workflow primitives; no unrestricted system access."""
from __future__ import annotations

import ast
import difflib
import operator

from .documents import read_document

ALLOWED_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow}


def plan(question: str) -> list[dict]:
    steps = [{"tool": "retrieve", "purpose": "Find grounded supporting sources."}]
    if any(word in question.lower() for word in ("calculate", "sum", "average", "percent", "ratio")):
        steps.insert(0, {"tool": "calculator", "purpose": "Evaluate a numeric expression without using the language model."})
    steps.append({"tool": "generate", "purpose": "Write a cited answer from approved tool outputs."})
    return steps


def calculate(expression: str) -> float:
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return evaluate(node.operand) if isinstance(node.op, ast.UAdd) else -evaluate(node.operand)
        raise ValueError("Only basic numeric expressions are allowed.")
    return evaluate(ast.parse(expression, mode="eval").body)


def analyze_document(path) -> dict:
    text = read_document(path)
    return {"characters": len(text), "lines": len(text.splitlines()), "preview": text[:600]}


def compare_documents(left_path, right_path) -> dict:
    left, right = read_document(left_path).splitlines(), read_document(right_path).splitlines()
    changes = list(difflib.unified_diff(left, right, fromfile=left_path.name, tofile=right_path.name, lineterm=""))
    return {"changes": changes[:120], "changed_lines": len(changes)}
