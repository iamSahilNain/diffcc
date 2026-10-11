"""Program sources: csmith, and a built-in generator for a UB-free C subset.

The built-in generator ("smallgen") targets the integer-semantics corner of C
that compilers get wrong most often and that students mispredict most often:
mixed signed/unsigned arithmetic, integer promotions of char and short,
shifts, wraparound, comparisons across widths, and loops over small arrays.
It is UB-free by construction:
  * all arithmetic that can overflow is done in unsigned types;
  * every shift count is masked to the width of the promoted operand;
  * every divisor is forced non-zero and signed division avoids INT_MIN/-1;
  * every array index is cast to uint32_t and reduced modulo the array length.
"""
from __future__ import annotations

import os
import random
import subprocess
from dataclasses import dataclass


@dataclass
class Program:
    source: str
    origin: str
    seed: int


def csmith_program(seed: int, extra_args: tuple[str, ...] = ()) -> Program:
    cmd = ["csmith", "--seed", str(seed), "--no-packed-struct", "--no-volatiles", "--no-bitfields",
           "--max-funcs", "6", *extra_args]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True).stdout
    return Program(source=out, origin="csmith", seed=seed)


_INT_TYPES = [
    ("signed char", "int8_t"), ("unsigned char", "uint8_t"),
    ("short", "int16_t"), ("unsigned short", "uint16_t"),
    ("int", "int32_t"), ("unsigned", "uint32_t"),
    ("long long", "int64_t"), ("unsigned long long", "uint64_t"),
]
_UNSIGNED = {"uint8_t", "uint16_t", "uint32_t", "uint64_t"}
_WIDTH = {"int8_t": 8, "uint8_t": 8, "int16_t": 16, "uint16_t": 16,
          "int32_t": 32, "uint32_t": 32, "int64_t": 64, "uint64_t": 64}


class SmallGen:
    def __init__(self, seed: int, n_vars: int = 6, n_stmts: int = 14, depth: int = 3):
        self.rng = random.Random(seed)
        self.seed = seed
        self.n_vars = n_vars
        self.n_stmts = n_stmts
        self.depth = depth
        self.vars: list[tuple[str, str]] = []   # (name, ctype)
        self.arrays: list[tuple[str, str, int]] = []

    # ---- expressions -------------------------------------------------
    def _lit(self, t: str) -> str:
        w = _WIDTH[t]
        if t in _UNSIGNED:
            v = self.rng.choice([0, 1, 2, 3, 7, 127, 128, 255, 256, 65535, 65536,
                                 (1 << (w - 1)) - 1, (1 << w) - 1, self.rng.getrandbits(w)])
            v &= (1 << w) - 1
            return f"(({t}){v}ULL)"
        v = self.rng.choice([0, 1, -1, 2, -2, 7, 127, -128, 255, 32767, -32768,
                             (1 << (w - 1)) - 1, -(1 << (w - 1)), self.rng.getrandbits(w - 1)])
        v = max(-(1 << (w - 1)), min((1 << (w - 1)) - 1, v))
        if v == -(1 << 63):
            return "((int64_t)(-9223372036854775807LL - 1))"
        return f"(({t})({v}LL))"

    def _var(self) -> tuple[str, str]:
        if self.arrays and self.rng.random() < 0.25:
            name, t, n = self.rng.choice(self.arrays)
            idx = self._expr("uint32_t", 1)
            # cast first: a 64-bit signed operand would otherwise drag the `%` into int64 and go negative
            return f"{name}[((uint32_t)({idx})) % {n}u]", t
        return self.rng.choice(self.vars)

    def _expr(self, want: str, d: int) -> str:
        """Return an expression whose value is well-defined; its C type may differ from `want`
        (that is the point: implicit conversions are what we test), but we cast at the end."""
        r = self.rng.random()
        if d <= 0 or r < 0.25:
            if r < 0.12:
                return self._lit(want)
            name, t = self._var()
            return name
        op = self.rng.choice(["+", "-", "*", "&", "|", "^", "<<", ">>", "/", "%", "<", "<=", "==",
                              "!=", ">", "&&", "||", "?:", "~", "!", "neg", "cast", "cmp-mixed"])
        ut = self.rng.choice(sorted(_UNSIGNED))
        if op in ("+", "-", "*"):
            # overflow-safe: compute in an unsigned type of at least 32 bits
            t = self.rng.choice(["uint32_t", "uint64_t"])
            return f"(({t})({self._expr(t, d-1)}) {op} ({t})({self._expr(t, d-1)}))"
        if op in ("&", "|", "^"):
            return f"(({self._expr(want, d-1)}) {op} ({self._expr(want, d-1)}))"
        if op == "<<":
            t = self.rng.choice(["uint32_t", "uint64_t"])
            w = _WIDTH[t]
            return f"(({t})({self._expr(t, d-1)}) << (({self._expr('uint32_t', d-1)}) & {w-1}u))"
        if op == ">>":
            t = self.rng.choice(["uint32_t", "uint64_t", "int32_t", "int64_t"])
            w = _WIDTH[t]
            return f"(({t})({self._expr(t, d-1)}) >> (({self._expr('uint32_t', d-1)}) & {w-1}u))"
        if op in ("/", "%"):
            t = self.rng.choice(["uint32_t", "uint64_t", "int32_t"])
            a = self._expr(t, d-1)
            b = self._expr(t, d-1)
            if t == "int32_t":
                # avoid /0 and INT_MIN / -1 by forcing the divisor into [1, 1000]
                return f"(({t})({a}) {op} ((int32_t)((({b}) & 1023) + 1)))"
            return f"(({t})({a}) {op} ((({t})({b}) & 1023u) + 1u))"
        if op in ("<", "<=", "==", "!=", ">"):
            return f"(({self._expr(want, d-1)}) {op} ({self._expr(want, d-1)}))"
        if op == "cmp-mixed":
            # the classic: signed vs unsigned comparison after promotion
            a, ta = self._var()
            b, tb = self._var()
            cmp = self.rng.choice(["<", ">", "==", "<=", ">="])
            return f"(({a}) {cmp} ({b}))"
        if op in ("&&", "||"):
            return f"(({self._expr(want, d-1)}) {op} ({self._expr(want, d-1)}))"
        if op == "?:":
            return f"(({self._expr('int32_t', d-1)}) ? ({self._expr(want, d-1)}) : ({self._expr(want, d-1)}))"
        if op == "~":
            return f"(~({self._expr(want, d-1)}))"
        if op == "!":
            return f"(!({self._expr(want, d-1)}))"
        if op == "neg":
            t = self.rng.choice(["uint32_t", "uint64_t"])
            return f"(-(({t})({self._expr(t, d-1)})))"
        if op == "cast":
            t = self.rng.choice([ct for _, ct in _INT_TYPES])
            return f"(({t})({self._expr(t, d-1)}))"
        return self._lit(want)

    # ---- statements --------------------------------------------------
    def _assign(self) -> str:
        name, t = self._var()
        return f"    {name} = ({t})({self._expr(t, self.depth)});"

    def _loop(self) -> str:
        n = self.rng.randint(1, 9)
        name, t = self._var()
        body = self._expr(t, self.depth - 1)
        return (f"    for (uint32_t i_ = 0; i_ < {n}u; i_++) {{\n"
                f"        {name} = ({t})((uint64_t)({name}) + (uint64_t)({body}) + i_);\n"
                f"    }}")

    def _branch(self) -> str:
        c = self._expr("int32_t", self.depth - 1)
        return f"    if ({c}) {{\n    {self._assign()}\n    }} else {{\n    {self._assign()}\n    }}"

    def generate(self) -> Program:
        rng = self.rng
        self.vars = [(f"v{i}", rng.choice(_INT_TYPES)[1]) for i in range(self.n_vars)]
        self.arrays = [(f"a{i}", rng.choice(_INT_TYPES)[1], rng.randint(2, 6)) for i in range(rng.randint(1, 2))]
        lines = ["#include <stdint.h>", "#include <stdio.h>", "#include <inttypes.h>", ""]
        for name, t in self.vars:
            lines.append(f"static {t} {name} = {self._lit(t)};")
        for name, t, n in self.arrays:
            init = ", ".join(self._lit(t) for _ in range(n))
            lines.append(f"static {t} {name}[{n}] = {{{init}}};")
        lines.append("")
        lines.append("static uint64_t crc = 0xcbf29ce484222325ULL;")
        lines.append("static void mix(uint64_t x) { crc ^= x; crc *= 0x100000001b3ULL; }")
        lines.append("")
        lines.append("int main(void) {")
        for _ in range(self.n_stmts):
            k = rng.random()
            if k < 0.6:
                lines.append(self._assign())
            elif k < 0.8:
                lines.append(self._loop())
            else:
                lines.append(self._branch())
        for name, t in self.vars:
            lines.append(f"    mix((uint64_t){name});")
        for name, t, n in self.arrays:
            lines.append(f"    for (uint32_t i_ = 0; i_ < {n}u; i_++) mix((uint64_t){name}[i_]);")
        lines.append('    printf("checksum = %" PRIx64 "\\n", crc);')
        lines.append("    return 0;")
        lines.append("}")
        return Program(source="\n".join(lines) + "\n", origin="smallgen", seed=self.seed)


def smallgen_program(seed: int, **kw) -> Program:
    return SmallGen(seed, **kw).generate()
