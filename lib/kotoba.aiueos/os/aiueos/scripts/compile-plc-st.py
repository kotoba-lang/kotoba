#!/usr/bin/env python3
"""Compile the bounded AIUEOS PLC Structured Text subset to Kotoba source."""

import argparse
import dataclasses
import pathlib
import re
import sys


MAX_INPUTS = 16
MAX_OUTPUTS = 16
MAX_ASSIGNMENTS = 16

TOKEN = re.compile(
    r"\s+|:=|<=|>=|<>|[();:+\-*=<>]|[A-Za-z_][A-Za-z0-9_]*|[0-9]+"
)
KEYWORDS = {
    "PROGRAM", "END_PROGRAM", "VAR_INPUT", "VAR_OUTPUT", "END_VAR",
    "BOOL", "DINT", "TRUE", "FALSE", "NOT", "AND", "OR", "XOR",
}
PRECEDENCE = {
    "OR": 10, "XOR": 20, "AND": 30,
    "=": 40, "<>": 40, "<": 40, "<=": 40, ">": 40, ">=": 40,
    "+": 50, "-": 50, "*": 60,
}


class PlcCompileError(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class Variable:
    source_name: str
    name: str
    type: str
    direction: str
    index: int


@dataclasses.dataclass(frozen=True)
class Expr:
    op: str
    value: object
    args: tuple = ()
    type: str = ""


def strip_comments(source):
    if "(*" in re.sub(r"\(\*.*?\*\)", "", source, flags=re.S):
        raise PlcCompileError("nested or unterminated comment")
    return re.sub(r"\(\*.*?\*\)", " ", source, flags=re.S)


def tokenize(source):
    source = strip_comments(source)
    tokens = []
    position = 0
    while position < len(source):
        match = TOKEN.match(source, position)
        if not match:
            excerpt = source[position:position + 20].splitlines()[0]
            raise PlcCompileError(f"unsupported token near {excerpt!r}")
        raw = match.group(0)
        position = match.end()
        if raw.isspace():
            continue
        upper = raw.upper()
        tokens.append(upper if upper in KEYWORDS else raw)
    return tokens


class Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.at = 0
        self.variables = {}
        self.inputs = []
        self.outputs = []
        self.assignments = []
        self.assigned = set()

    def peek(self):
        return self.tokens[self.at] if self.at < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None:
            raise PlcCompileError(f"expected {expected or 'token'}, found end of file")
        if expected is not None and token != expected:
            raise PlcCompileError(f"expected {expected}, found {token}")
        self.at += 1
        return token

    def identifier(self):
        token = self.take()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) or token.upper() in KEYWORDS:
            raise PlcCompileError(f"expected identifier, found {token}")
        return token

    def parse(self):
        self.take("PROGRAM")
        program = self.identifier()
        seen_sections = set()
        while self.peek() in ("VAR_INPUT", "VAR_OUTPUT"):
            direction = "input" if self.take() == "VAR_INPUT" else "output"
            if direction in seen_sections:
                raise PlcCompileError(f"duplicate VAR_{direction.upper()} section")
            seen_sections.add(direction)
            self.declarations(direction)
        if seen_sections != {"input", "output"}:
            raise PlcCompileError("VAR_INPUT and VAR_OUTPUT are both required")
        if not self.inputs or not self.outputs:
            raise PlcCompileError("at least one input and one output are required")
        while self.peek() != "END_PROGRAM":
            self.assignment()
            if len(self.assignments) > MAX_ASSIGNMENTS:
                raise PlcCompileError(f"more than {MAX_ASSIGNMENTS} assignments")
        self.take("END_PROGRAM")
        if self.peek() is not None:
            raise PlcCompileError(f"trailing token {self.peek()}")
        missing = [v.source_name for v in self.outputs if v.name not in self.assigned]
        if missing:
            raise PlcCompileError("outputs not assigned: " + ", ".join(missing))
        return program, self.inputs, self.outputs, self.assignments

    def declarations(self, direction):
        target = self.inputs if direction == "input" else self.outputs
        limit = MAX_INPUTS if direction == "input" else MAX_OUTPUTS
        while self.peek() != "END_VAR":
            source_name = self.identifier()
            key = source_name.lower()
            if key in self.variables:
                raise PlcCompileError(f"duplicate variable {source_name}")
            self.take(":")
            type_name = self.take()
            if type_name not in ("BOOL", "DINT"):
                raise PlcCompileError(f"unsupported type {type_name}")
            self.take(";")
            variable = Variable(source_name, "plc-v-" + key,
                                type_name, direction, len(target))
            self.variables[key] = variable
            target.append(variable)
            if len(target) > limit:
                raise PlcCompileError(f"more than {limit} {direction}s")
        self.take("END_VAR")

    def assignment(self):
        source_name = self.identifier()
        name = source_name.lower()
        variable = self.variables.get(name)
        if variable is None or variable.direction != "output":
            raise PlcCompileError(f"assignment target is not an output: {source_name}")
        if variable.name in self.assigned:
            raise PlcCompileError(f"output assigned more than once: {source_name}")
        self.take(":=")
        expression = self.expression(0)
        self.take(";")
        if expression.type != variable.type:
            raise PlcCompileError(
                f"type mismatch assigning {expression.type} to {variable.type} {source_name}"
            )
        self.assigned.add(variable.name)
        self.assignments.append((variable, expression))

    def expression(self, minimum):
        left = self.prefix()
        while self.peek() in PRECEDENCE and PRECEDENCE[self.peek()] >= minimum:
            operator = self.take()
            precedence = PRECEDENCE[operator]
            right = self.expression(precedence + 1)
            left = self.binary(operator, left, right)
        return left

    def prefix(self):
        token = self.take()
        if token == "(":
            result = self.expression(0)
            self.take(")")
            return result
        if token == "NOT":
            child = self.expression(70)
            if child.type != "BOOL":
                raise PlcCompileError("NOT requires BOOL")
            return Expr("NOT", None, (child,), "BOOL")
        if token == "-":
            child = self.expression(70)
            if child.type != "DINT":
                raise PlcCompileError("unary minus requires DINT")
            return Expr("NEGATE", None, (child,), "DINT")
        if token in ("TRUE", "FALSE"):
            return Expr("BOOL", token == "TRUE", (), "BOOL")
        if token.isdigit():
            value = int(token)
            if value > 2147483647:
                raise PlcCompileError("DINT literal exceeds 2147483647")
            return Expr("DINT", value, (), "DINT")
        name = token.lower()
        variable = self.variables.get(name)
        if variable is None:
            raise PlcCompileError(f"unknown variable {token}")
        if variable.direction == "output" and variable.name not in self.assigned:
            raise PlcCompileError(f"output read before assignment: {token}")
        return Expr("VARIABLE", variable, (), variable.type)

    @staticmethod
    def binary(operator, left, right):
        if operator in ("AND", "OR", "XOR"):
            if left.type != "BOOL" or right.type != "BOOL":
                raise PlcCompileError(f"{operator} requires BOOL operands")
            return Expr(operator, None, (left, right), "BOOL")
        if operator in ("+", "-", "*"):
            if left.type != "DINT" or right.type != "DINT":
                raise PlcCompileError(f"{operator} requires DINT operands")
            return Expr(operator, None, (left, right), "DINT")
        if left.type != right.type:
            raise PlcCompileError(f"{operator} operands have different types")
        return Expr(operator, None, (left, right), "BOOL")


def kotoba_expr(expression):
    op = expression.op
    if op == "VARIABLE":
        return expression.value.name
    if op == "BOOL":
        return "true" if expression.value else "false"
    if op == "DINT":
        return str(expression.value)
    args = [kotoba_expr(arg) for arg in expression.args]
    if op == "NOT":
        return f"(not {args[0]})"
    if op == "NEGATE":
        return f"(plc-dint (- 0 {args[0]}))"
    if op == "AND":
        return f"(and {args[0]} {args[1]})"
    if op == "OR":
        return f"(or {args[0]} {args[1]})"
    if op == "XOR":
        return f"(not (= {args[0]} {args[1]}))"
    names = {"=": "=", "<>": "not-equal", "<": "<", "<=": "<=",
             ">": ">", ">=": ">=", "+": "+", "-": "-", "*": "*"}
    if op == "<>":
        return f"(not (= {args[0]} {args[1]}))"
    rendered = f"({names[op]} {args[0]} {args[1]})"
    return f"(plc-dint {rendered})" if op in ("+", "-", "*") else rendered


def generate(program, inputs, outputs, assignments):
    safe_program = re.sub(r"[^a-z0-9_]+", "-", program.lower()).strip("-")
    bindings = []
    for variable in inputs:
        call = f"(cap-call 16 {variable.index})"
        value = f"(not (= {call} 0))" if variable.type == "BOOL" else f"(plc-dint {call})"
        bindings.append((variable.name, value))
    assignment_map = dict(assignments)
    for variable, expression in assignments:
        bindings.append((variable.name, kotoba_expr(expression)))
    for variable in outputs:
        value = variable.name
        word = f"(if {value} 1 0)" if variable.type == "BOOL" else f"(bit-and {value} 4294967295)"
        packed = f"(+ {word} (* {variable.index} 4294967296))"
        bindings.append((f"stage-{variable.index}", f"(cap-call 17 {packed})"))
    stage_checks = [f"(= stage-{v.index} 1)" for v in outputs]
    stages = stage_checks[0] if len(stage_checks) == 1 else f"(and {' '.join(stage_checks)})"
    bindings.append(("stages-ok", stages))
    bindings.append(("watchdog", "(if stages-ok (cap-call 19 1) 0)"))
    bindings.append(("commit", f"(if (= watchdog 1) (cap-call 18 {len(outputs)}) 0)"))
    rendered = "\n        ".join(f"{name} {value}" for name, value in bindings)
    return (
        f"(ns aiueos.plc.{safe_program} (:export [main]))\n\n"
        ";; Generated by compile-plc-st.py. Do not interpret this source at runtime.\n"
        "(defn plc-dint [value]\n"
        "  (let [word (bit-and value 4294967295)]\n"
        "    (if (>= word 2147483648) (- word 4294967296) word)))\n\n"
        "(defn main []\n"
        f"  (let [{rendered}]\n"
        "    (if (= commit 1) 1 0)))\n"
    )


def compile_source(source):
    return generate(*Parser(source).parse())


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        generated = compile_source(args.source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, PlcCompileError) as error:
        print(f"error: PLC ST refused: {error}", file=sys.stderr)
        return 2
    args.output.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
