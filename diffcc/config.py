"""Compiler configurations under test.

A Config is one (compiler binary, flag list) pair. Every program is compiled
with every config; a divergence is any pair of configs whose binaries print
different output on the same program.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    name: str
    cc: str
    flags: tuple[str, ...] = ()

    def cmd(self, src: str, out: str, extra: tuple[str, ...] = ()) -> list[str]:
        return [self.cc, *self.flags, *extra, "-w", "-o", out, src]


OPT_LEVELS = ("-O0", "-O1", "-O2", "-O3", "-Os")


def _first_existing(*paths: str) -> str | None:
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def macos_sdk() -> str | None:
    """Homebrew clang does not know where the macOS SDK lives; Apple clang and brew gcc do."""
    env = os.environ.get("SDKROOT")
    if env and os.path.isdir(env):
        return env
    try:
        p = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True, text=True, timeout=30).stdout.strip()
        return p if p and os.path.isdir(p) else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def base_flags(cc: str) -> tuple[str, ...]:
    """Flags every config for this compiler needs just to compile hello world."""
    if "/opt/homebrew/opt/llvm" in cc or "/usr/local/opt/llvm" in cc:
        sdk = macos_sdk()
        if sdk:
            return ("-isysroot", sdk)
    return ()


def discover_compilers() -> dict[str, str]:
    """Return {label: path} for every compiler found on this machine."""
    found: dict[str, str] = {}
    apple = _first_existing("/usr/bin/clang")
    if apple:
        found["apple-clang"] = apple
    brew_llvm = _first_existing("/opt/homebrew/opt/llvm/bin/clang", "/usr/local/opt/llvm/bin/clang")
    if brew_llvm:
        found["llvm-clang"] = brew_llvm
    for gcc in ("gcc-15", "gcc-14", "gcc-13"):
        p = shutil.which(gcc)
        if p:
            found["gcc"] = p
            break
    if not found:
        generic = shutil.which("cc")
        if generic:
            found["cc"] = generic
    return found


def compiler_version(cc: str) -> str:
    try:
        out = subprocess.run([cc, "--version"], capture_output=True, text=True, timeout=20).stdout
        return out.splitlines()[0].strip() if out else "?"
    except (OSError, subprocess.TimeoutExpired):
        return "?"


def default_configs(opt_levels: tuple[str, ...] = OPT_LEVELS) -> list[Config]:
    configs: list[Config] = []
    for label, cc in discover_compilers().items():
        for o in opt_levels:
            configs.append(Config(name=f"{label}{o}", cc=cc, flags=(*base_flags(cc), o)))
    return configs


def sanitizer_config() -> Config | None:
    """The config used to reject programs with undefined behaviour.

    clang's UBSan and ASan at -O0 (and -O1 for a second opinion on UB that
    only optimisation exposes) are the gate; a program is kept only if both
    runs are silent.
    """
    ccs = discover_compilers()
    cc = ccs.get("llvm-clang") or ccs.get("apple-clang")
    if not cc:
        return None
    return Config(
        name="ubsan",
        cc=cc,
        flags=(*base_flags(cc), "-O1", "-fsanitize=undefined,address", "-fno-sanitize-recover=all",
               "-fno-omit-frame-pointer"),
    )


def csmith_include() -> str | None:
    env = os.environ.get("CSMITH_PATH")
    if env and os.path.isdir(env):
        return env
    try:
        prefix = subprocess.run(["brew", "--prefix", "csmith"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        prefix = ""
    if prefix:
        inc = os.path.join(prefix, "include")
        if os.path.isdir(inc):
            for name in sorted(os.listdir(inc)):
                if name.startswith("csmith"):
                    return os.path.join(inc, name)
    return None
