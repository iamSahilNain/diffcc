"""Run a campaign: N programs from a generator, every config, record candidates."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

from .config import Config, compiler_version, csmith_include, default_configs, sanitizer_config
from .generators import Program, csmith_program, smallgen_program
from .harness import ProgramVerdict, check_program


def make_program(origin: str, seed: int) -> Program:
    if origin == "csmith":
        return csmith_program(seed)
    if origin == "smallgen":
        return smallgen_program(seed)
    raise ValueError(origin)


def run_campaign(origin: str, n: int, seed0: int, out_dir: str, configs: list[Config] | None = None,
                 jobs: int = 4, compile_timeout: float = 60.0, run_timeout: float = 10.0,
                 progress=None) -> dict:
    configs = configs or default_configs()
    san = sanitizer_config()
    include = csmith_include() if origin == "csmith" else None
    os.makedirs(out_dir, exist_ok=True)
    cand_dir = os.path.join(out_dir, "candidates")
    os.makedirs(cand_dir, exist_ok=True)

    summary = {
        "origin": origin, "n": n, "seed0": seed0, "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "configs": [c.name for c in configs],
        "compilers": {c.cc: compiler_version(c.cc) for c in {c.cc: c for c in configs}.values()},
        "counts": {"agree": 0, "diverge": 0, "compiler-crash": 0, "ub": 0, "all-timeout": 0, "harness-error": 0, "gen-error": 0},
        "candidates": [],
    }
    log_path = os.path.join(out_dir, "campaign.jsonl")

    def one(seed: int) -> tuple[int, Program | None, ProgramVerdict | None, str]:
        try:
            prog = make_program(origin, seed)
        except Exception as e:  # csmith failure etc.
            return seed, None, None, f"gen-error: {e}"[:300]
        with_src = os.path.join(cand_dir, f"{origin}_{seed}.c")
        v = check_program(f"{origin}_{seed}", _write_tmp(prog.source, with_src), configs, san, include,
                          compile_timeout, run_timeout)
        if v.verdict not in ("diverge", "compiler-crash"):
            try:
                os.remove(with_src)
            except OSError:
                pass
        return seed, prog, v, ""

    with ThreadPoolExecutor(max_workers=jobs) as ex, open(log_path, "a") as log:
        futures = [ex.submit(one, seed0 + i) for i in range(n)]
        done = 0
        for fut in as_completed(futures):
            seed, prog, v, err = fut.result()
            done += 1
            if v is None:
                summary["counts"]["gen-error"] += 1
                log.write(json.dumps({"seed": seed, "verdict": "gen-error", "note": err}) + "\n")
            else:
                summary["counts"][v.verdict] += 1
                rec = {"seed": seed, "verdict": v.verdict, "note": v.note, "groups": v.groups}
                log.write(json.dumps(rec) + "\n")
                if v.verdict in ("diverge", "compiler-crash"):
                    rec["source"] = os.path.join(cand_dir, f"{origin}_{seed}.c")
                    rec["results"] = [asdict(r) for r in v.results]
                    summary["candidates"].append(rec)
            log.flush()
            if progress and (done % 10 == 0 or done == n):
                progress(done, n, summary["counts"])
    summary["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    return summary


def _write_tmp(source: str, path: str) -> str:
    with open(path, "w") as f:
        f.write(source)
    return path
