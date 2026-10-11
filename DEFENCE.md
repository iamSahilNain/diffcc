# Interview notes for diffcc (read before any interview that may ask about it)

**One sentence.** diffcc generates C programs, throws away any that have undefined behaviour, compiles the rest with every compiler and optimisation level on the machine, runs all the binaries, and reports any program on which they disagree or on which a compiler crashes.

**Why the oracle works.** A correct program has one meaning under the C standard, so every conforming compiler at every optimisation level must produce the same observable output. Any disagreement is a bug in at least one of them. This is differential testing (McKeeman, 1998); Csmith (Yang, Chen, Eide, Regehr, PLDI 2011) used it to find 325 bugs in GCC and LLVM.

**Why UB must be filtered first.** If the program has undefined behaviour, the compilers are allowed to disagree, so a divergence proves nothing. UBSan and ASan at -O1 catch signed overflow, bad shifts, division by zero, out-of-bounds, misaligned and null access. Programs that trip them get verdict `ub` and never reach the comparison. A build failure in the sanitizer stage is reported as `harness-error`, never as `ub`, so a broken toolchain cannot hide behind the UB filter.

**Why I wrote my own generator next to Csmith.** Csmith covers the whole language but its programs are thousands of lines and each one takes tens of seconds through 15 configs. The integer corner of C (promotions, signed/unsigned comparison, shifts, wraparound) is where both compilers and people slip, so smallgen emits 30-line programs that are dense in exactly that and UB-free by construction: overflow-prone arithmetic in unsigned types, shift counts masked to width minus one, divisors forced into 1..1024, array indices cast to uint32_t then reduced modulo the length. It still goes through the sanitizer gate; `tests/test_generators.py` pushes 40 seeds through it.

**The bug I found in my own generator.** The first version indexed arrays with `(expr) % 6u`. When `expr` was a 64-bit signed value the usual arithmetic conversions made the `%` an int64 operation, so the index could be negative. UBSan caught it on seeds 8 and 9 of the first smoke run. Fix: cast to `uint32_t` before the modulo. Lesson: "UB-free by construction" is a claim to test, not to assume.

**How I know the detector detects.** `tests/test_harness.py` wraps `cc` in a shell script that rewrites `+ 1` to `+ 2` before compiling; the harness must report `diverge` between it and the honest config. A second wrapper always exits 1 and must be reported as `compiler-crash`. A program with an out-of-bounds read must come back `ub`. A detector that has only ever seen passing inputs is untested.

**How a candidate becomes a bug report.** `diffcc reduce` writes a C-Reduce interestingness script that re-checks three things on each shrink: still sanitizer-clean, both configs still compile and run it, outputs still differ. C-Reduce shrinks the program while that stays true. Then read the reduced program against the standard to decide which compiler is wrong.

**Numbers.** Only the counts in `results/README.md` and `results/*/summary.json`. Do not quote anything else.

**Honest limits.** One architecture (arm64) per machine; no pointers, structs, floats or calls in smallgen; divergence tells you that someone is wrong, not who; a few thousand programs rarely catch a release-compiler bug, and the harness was built in a day.

**Likely follow-ups.** What is integer promotion; why `-1 < 1u` is false; why signed overflow is UB but unsigned is not; what `-O2` may legally change (anything unobservable); what a miscompile looks like versus a crash; why `volatile` appears in the test program (to stop constant folding of `x + 1`); how you would extend to cross-targets (QEMU user mode) or to PTX (nvcc at several levels, compare kernel outputs on the device).
