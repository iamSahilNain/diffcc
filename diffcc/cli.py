from __future__ import annotations

import argparse
import json
import sys

from .campaign import run_campaign
from .config import compiler_version, default_configs, discover_compilers
from .generators import csmith_program, smallgen_program
from .reduce import reduce_program


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="diffcc", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("configs", help="list compilers and configs found on this machine")

    p = sub.add_parser("gen", help="print one generated program")
    p.add_argument("--origin", choices=["csmith", "smallgen"], default="smallgen")
    p.add_argument("--seed", type=int, default=1)

    p = sub.add_parser("run", help="run a campaign")
    p.add_argument("--origin", choices=["csmith", "smallgen"], default="smallgen")
    p.add_argument("-n", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default="results/latest")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--compile-timeout", type=float, default=60.0)
    p.add_argument("--run-timeout", type=float, default=10.0)

    p = sub.add_parser("reduce", help="minimise a candidate with creduce")
    p.add_argument("src")
    p.add_argument("config_a")
    p.add_argument("config_b")
    p.add_argument("--out", required=True)
    p.add_argument("--mode", choices=["diverge", "crash"], default="diverge")

    a = ap.parse_args(argv)
    if a.cmd == "configs":
        for label, cc in discover_compilers().items():
            print(f"{label:12s} {cc}  ({compiler_version(cc)})")
        print("configs:", ", ".join(c.name for c in default_configs()))
        return 0
    if a.cmd == "gen":
        prog = csmith_program(a.seed) if a.origin == "csmith" else smallgen_program(a.seed)
        sys.stdout.write(prog.source)
        return 0
    if a.cmd == "run":
        def progress(done, n, counts):
            print(f"[{done}/{n}] {counts}", file=sys.stderr, flush=True)
        s = run_campaign(a.origin, a.n, a.seed, a.out, jobs=a.jobs, compile_timeout=a.compile_timeout,
                         run_timeout=a.run_timeout, progress=progress)
        print(json.dumps({k: s[k] for k in ("origin", "n", "counts")}, indent=2))
        print(f"candidates: {len(s['candidates'])} (see {a.out}/summary.json)")
        return 0
    if a.cmd == "reduce":
        out = reduce_program(a.src, a.config_a, a.config_b, a.out, a.mode)
        print(f"reduced program written to {out}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
