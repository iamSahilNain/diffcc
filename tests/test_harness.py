"""Detection must be proven against a known-bad compiler, not only a known-good one.

A fake compiler (a shell script) is wrapped around the system cc; it rewrites
`+ 1` to `+ 2` before compiling, so any program whose output depends on that
expression must be reported as a divergence against the honest config. A
second fake compiler always exits 1, which must be reported as a compiler crash.
"""
import os
import stat
import tempfile

from diffcc.config import Config
from diffcc.harness import check_program

GOOD = Config(name="good-O0", cc="cc", flags=("-O0",))

PROG = """
#include <stdio.h>
int main(void) { volatile int x = 41; printf("%d\\n", x + 1); return 0; }
"""


def _script(path: str, body: str) -> str:
    with open(path, "w") as f:
        f.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def test_detects_miscompile_against_planted_bug():
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write(PROG)
        # last argument is the source file; everything else is passed to cc unchanged
        bad = _script(os.path.join(wd, "badcc.sh"),
                      'src="${@: -1}"; set -- "${@:1:$#-1}"; sed "s/+ 1/+ 2/" "$src" > "$src.bad.c"; exec cc "$@" "$src.bad.c"\n')
        bad = _script(os.path.join(wd, "badcc"), f'exec bash "{bad}" "$@"\n')
        v = check_program("p", src, [GOOD, Config("bad-O0", bad, ("-O0",))], san=None)
        assert v.verdict == "diverge", (v.verdict, v.note, [r.status for r in v.results])
        assert len(v.groups) == 2


def test_agreement_when_no_bug_planted():
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write(PROG)
        v = check_program("p", src, [GOOD, Config("good-O2", "cc", ("-O2",))], san=None)
        assert v.verdict == "agree", (v.note, [r.status for r in v.results])


def test_detects_compiler_crash():
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write(PROG)
        crash = _script(os.path.join(wd, "crashcc"), "echo 'internal compiler error' >&2; exit 1\n")
        v = check_program("p", src, [GOOD, Config("crash-O0", crash, ())], san=None)
        assert v.verdict == "compiler-crash"
        assert "crash-O0" in v.note


def test_ub_program_is_rejected_not_reported():
    from diffcc.config import sanitizer_config
    san = sanitizer_config()
    if san is None:
        return
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write('#include <stdio.h>\nint main(void){ int a[2]={1,2}; volatile int i=5; printf("%d\\n", a[i]); return 0; }\n')
        v = check_program("p", src, [GOOD], san=san)
        assert v.verdict == "ub", (v.verdict, v.note)
