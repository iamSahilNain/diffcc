"""Minimise a divergent program with creduce.

The interestingness test is: the program is still sanitizer-clean, both
named configs still compile and run it, and their outputs still differ
(or the named config still fails to compile it, for compiler crashes).
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile

from .config import Config, csmith_include, default_configs, sanitizer_config


def _config_by_name(name: str, configs: list[Config]) -> Config:
    for c in configs:
        if c.name == name:
            return c
    raise KeyError(name)


def write_interestingness(path: str, src_name: str, a: Config, b: Config, include: str | None,
                          mode: str = "diverge") -> None:
    san = sanitizer_config()
    inc = f"-I{include}" if include else ""
    san_line = ""
    if san:
        san_line = (f"{san.cc} {' '.join(san.flags)} {inc} -w -o san {src_name} >/dev/null 2>&1 || exit 1\n"
                    f"./san >san.out 2>san.err || exit 1\n"
                    f"grep -q 'runtime error\\|Sanitizer' san.err && exit 1\n")
    if mode == "diverge":
        body = (f"{a.cc} {' '.join(a.flags)} {inc} -w -o A {src_name} >/dev/null 2>&1 || exit 1\n"
                f"{b.cc} {' '.join(b.flags)} {inc} -w -o B {src_name} >/dev/null 2>&1 || exit 1\n"
                f"timeout 10 ./A >A.out 2>/dev/null; timeout 10 ./B >B.out 2>/dev/null\n"
                f"! cmp -s A.out B.out\n")
    else:  # compiler crash: config a must still fail, config b must still succeed
        body = (f"{b.cc} {' '.join(b.flags)} {inc} -w -o B {src_name} >/dev/null 2>&1 || exit 1\n"
                f"! {a.cc} {' '.join(a.flags)} {inc} -w -o A {src_name} >/dev/null 2>&1\n")
    script = "#!/bin/sh\n" + san_line + body
    with open(path, "w") as f:
        f.write(script)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)


def reduce_program(src: str, a_name: str, b_name: str, out_path: str, mode: str = "diverge",
                   configs: list[Config] | None = None, timeout: int = 1800) -> str:
    configs = configs or default_configs()
    a, b = _config_by_name(a_name, configs), _config_by_name(b_name, configs)
    include = csmith_include()
    with tempfile.TemporaryDirectory(prefix="diffcc_reduce_") as wd:
        work_src = os.path.join(wd, "prog.c")
        shutil.copy(src, work_src)
        test = os.path.join(wd, "interesting.sh")
        write_interestingness(test, "prog.c", a, b, include, mode)
        creduce = shutil.which("creduce")
        if not creduce:
            raise RuntimeError("creduce not found")
        subprocess.run([creduce, "--n", "4", test, "prog.c"], cwd=wd, timeout=timeout,
                       stdout=sys.stderr, stderr=sys.stderr)
        shutil.copy(work_src, out_path)
    return out_path
