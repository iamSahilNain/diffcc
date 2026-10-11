# diffcc — differential testing of C compilers

Generate C programs, compile each one with every compiler and optimisation
level on the machine, run every binary, and report any program on which the
compilers disagree or on which a compiler crashes. Programs that trip
UBSan or ASan are discarded before comparison, so every report is a
candidate compiler bug rather than undefined behaviour. Candidates are
minimised with C-Reduce.

```
csmith / smallgen ──> program.c ──> UBSan+ASan gate ──> {clang, gcc} x {-O0 -O1 -O2 -O3 -Os}
                                        │                        │
                                   reject if UB            run all binaries, hash outputs
                                                                 │
                                           agree | diverge | compiler-crash  ──> creduce
```

## Why

A compiler is verified the same way any other program is: by executing it
on inputs and checking the output against an oracle. For a compiler the
cheapest oracle is *another compiler*, or the same compiler at another
optimisation level: a correct program must behave identically under all of
them. This is the technique behind Csmith (Yang et al., PLDI 2011), which
found hundreds of bugs in GCC and LLVM. `diffcc` is a small, dependency-free
harness around that idea, with its own generator for the part of C where
both compilers and people make mistakes.

## Program sources

* **csmith** (external): large random C99 programs covering structs,
  pointers, arrays, loops and most operators.
* **smallgen** (built in, `diffcc/generators.py`): short programs that
  stress integer semantics only: mixed signed/unsigned arithmetic, integer
  promotion of `char` and `short`, shifts, wraparound, comparisons across
  widths, `?:`, small loops over arrays. It is UB-free by construction
  (overflow-prone arithmetic is done in unsigned types, shift counts are
  masked, divisors are forced into [1, 1024], array indices are cast to
  `uint32_t` and reduced modulo the length). The sanitizer gate is still
  applied, and `tests/test_generators.py` checks 40 seeds through it, so a
  generator bug cannot be reported as a compiler bug.

## Usage

```
python -m diffcc configs                 # compilers and configs found on this machine
python -m diffcc gen --seed 3            # print one smallgen program
python -m diffcc run --origin smallgen -n 2000 --seed 1 --out results/run1
python -m diffcc run --origin csmith   -n 200  --seed 1 --out results/run2 --run-timeout 20
python -m diffcc reduce results/run1/candidates/smallgen_17.c llvm-clang-O3 gcc-O0 --out min.c
```

`run` writes `campaign.jsonl` (one verdict per program), `summary.json`
(counts, compiler versions, candidates with per-config results) and keeps
the source of every candidate under `candidates/`.

Verdicts: `agree`, `diverge` (two configs print different output or exit
differently), `compiler-crash` (a config fails or times out compiling a
sanitizer-clean program), `ub` (rejected by the gate), `all-timeout`,
`harness-error` (the sanitizer build itself failed: a toolchain problem,
never counted as UB).

## Tests

```
pytest -q
```

* `tests/test_harness.py` proves detection against a **planted bug**: a
  fake compiler that rewrites `+ 1` to `+ 2` before calling `cc` must be
  reported as a divergence, a fake compiler that always exits 1 must be
  reported as a crash, and a program with an out-of-bounds read must be
  rejected as UB rather than reported. A detector that is only ever shown
  passing inputs has not been tested.
* `tests/test_generators.py` runs 40 smallgen seeds through UBSan+ASan.

CI (`.github/workflows/ci.yml`) runs the tests and a short campaign with
both generators on Ubuntu with clang and gcc.

## Results

See `results/README.md` for the campaigns run so far, with compiler
versions and counts.

## Limitations

* Only one architecture per machine; cross-target runs would need QEMU.
* smallgen covers integers only: no pointers, structs, floats or function
  calls yet. csmith covers those.
* Differential testing finds disagreements, not which side is wrong; each
  candidate needs a reduced program and a reading of the standard.
* Finding a bug in a release compiler in a few thousand programs is
  unlikely; the harness is the deliverable, the campaign numbers are
  reported as they come out.
