"""A sanitizer-stage timeout must not be counted as undefined behaviour."""
import os
import tempfile

from diffcc.config import Config, sanitizer_config
from diffcc.harness import check_program


def test_sanitizer_timeout_is_not_ub():
    san = sanitizer_config()
    if san is None:
        return
    with tempfile.TemporaryDirectory() as wd:
        src = os.path.join(wd, "p.c")
        with open(src, "w") as f:
            f.write('#include <stdio.h>\nint main(void){ volatile unsigned x=0; for(;;) x++; return 0; }\n')
        v = check_program("p", src, [Config("cc-O0", "cc", ("-O0",))], san=san, run_timeout=0.5)
        assert v.verdict == "san-timeout", (v.verdict, v.note)
