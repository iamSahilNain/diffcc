"""The generator must produce programs that compile and are sanitizer-clean.

This is the test that protects every result the tool reports: if the
generator emits undefined behaviour, a 'divergence' is a generator bug.
"""
import os
import subprocess
import tempfile

import pytest

from diffcc.config import csmith_include, sanitizer_config
from diffcc.generators import csmith_program, smallgen_program
from diffcc.harness import sanitizer_clean

SAN = sanitizer_config()
pytestmark = pytest.mark.skipif(SAN is None, reason="no clang with sanitizers on this machine")


@pytest.mark.parametrize("seed", list(range(1, 41)))
def test_smallgen_is_sanitizer_clean(seed):
    prog = smallgen_program(seed)
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write(prog.source)
        ok, why = sanitizer_clean(SAN, src, wd, None, 60, 30)
        assert ok, why


def test_smallgen_is_deterministic():
    assert smallgen_program(7).source == smallgen_program(7).source
    assert smallgen_program(7).source != smallgen_program(8).source


def test_smallgen_prints_checksum():
    prog = smallgen_program(5)
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write(prog.source)
        subprocess.run(["cc", "-w", "-o", os.path.join(wd, "p"), src], check=True)
        out = subprocess.run([os.path.join(wd, "p")], capture_output=True, text=True, check=True).stdout
        assert out.startswith("checksum = ")


@pytest.mark.skipif(csmith_include() is None, reason="csmith not installed")
def test_csmith_program_compiles():
    prog = csmith_program(1)
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write(prog.source)
        subprocess.run(["cc", "-w", f"-I{csmith_include()}", "-o", os.path.join(wd, "p"), src], check=True)
