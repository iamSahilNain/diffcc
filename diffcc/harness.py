"""Compile, run and compare one program across every config."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

from .config import Config


@dataclass
class BuildResult:
    config: str
    status: str            # "ok" | "compile-error" | "compile-timeout" | "run-timeout" | "run-crash"
    stdout: str = ""
    returncode: int | None = None
    detail: str = ""       # compiler stderr (truncated) or signal info


@dataclass
class ProgramVerdict:
    program_id: str
    verdict: str           # "agree" | "diverge" | "compiler-crash" | "ub" | "san-timeout" | "all-timeout" | "harness-error"
    results: list[BuildResult] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)  # output hash -> configs
    note: str = ""


def _run(cmd: list[str], timeout: float, cwd: str | None = None) -> tuple[int | None, str, str, bool]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, errors="replace")
        return p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "", True


def build_and_run(cfg: Config, src: str, workdir: str, include: str | None,
                  compile_timeout: float, run_timeout: float) -> BuildResult:
    out = os.path.join(workdir, f"bin_{cfg.name}")
    extra: tuple[str, ...] = (f"-I{include}",) if include else ()
    rc, _, err, timed_out = _run(cfg.cmd(src, out, extra), compile_timeout)
    if timed_out:
        return BuildResult(cfg.name, "compile-timeout")
    if rc != 0:
        return BuildResult(cfg.name, "compile-error", returncode=rc, detail=err[-2000:])
    rc, so, se, timed_out = _run([out], run_timeout)
    if timed_out:
        return BuildResult(cfg.name, "run-timeout")
    if rc is not None and rc < 0:
        return BuildResult(cfg.name, "run-crash", returncode=rc, detail=f"signal {-rc}")
    return BuildResult(cfg.name, "ok", stdout=so, returncode=rc, detail=se[-2000:])


def sanitizer_clean(cfg: Config, src: str, workdir: str, include: str | None,
                    compile_timeout: float, run_timeout: float) -> tuple[bool, str]:
    """True if the program compiles and runs under UBSan+ASan without a report."""
    r = build_and_run(cfg, src, workdir, include, compile_timeout, run_timeout)
    if r.status in ("compile-error", "compile-timeout"):
        # The sanitizer build failing is a harness or toolchain problem, never evidence of UB.
        return False, f"HARNESS {r.status}: {r.detail[:300]}"
    if r.status == "run-timeout":
        # Too slow under ASan to decide; not evidence of UB. Skipped, counted separately.
        return False, "TIMEOUT under sanitizers"
    if r.status != "ok":
        return False, f"{r.status}: {r.detail[:300]}"
    if "runtime error" in r.detail or "AddressSanitizer" in r.detail or "UndefinedBehaviorSanitizer" in r.detail:
        return False, r.detail[:600]
    if r.returncode not in (0, None):
        return False, f"exit {r.returncode}"
    return True, ""


def check_program(program_id: str, src: str, configs: list[Config], san: Config | None,
                  include: str | None = None, compile_timeout: float = 60.0,
                  run_timeout: float = 10.0) -> ProgramVerdict:
    with tempfile.TemporaryDirectory(prefix="diffcc_") as wd:
        if san is not None:
            ok, why = sanitizer_clean(san, src, wd, include, compile_timeout, run_timeout * 3)
            if not ok:
                kind = "harness-error" if why.startswith("HARNESS") else "san-timeout" if why.startswith("TIMEOUT") else "ub"
                return ProgramVerdict(program_id, kind, note=why)
        results = [build_and_run(c, src, wd, include, compile_timeout, run_timeout) for c in configs]

    verdict = ProgramVerdict(program_id, "agree", results=results)
    crashes = [r for r in results if r.status in ("compile-error", "compile-timeout")]
    if crashes:
        verdict.verdict = "compiler-crash"
        verdict.note = "; ".join(f"{r.config}: {r.status}" for r in crashes)
        return verdict
    ok = [r for r in results if r.status == "ok"]
    if not ok:
        verdict.verdict = "all-timeout"
        return verdict
    groups: dict[str, list[str]] = {}
    for r in results:
        key = hashlib.sha1(f"{r.status}|{r.returncode}|{r.stdout}".encode()).hexdigest()[:12]
        groups.setdefault(key, []).append(r.config)
    verdict.groups = groups
    if len(groups) > 1:
        verdict.verdict = "diverge"
        verdict.note = " vs ".join(",".join(v) for v in groups.values())
    return verdict
