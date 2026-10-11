# Campaigns

Counts are filled in from `summary.json` after each run. Nothing here is
estimated.

| Campaign | Origin | Programs | Compilers | Configs | agree | diverge | compiler-crash | ub | timeouts | harness-error |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign1_csmith (11 Oct 2026, macOS arm64) | csmith 2.3.0 | 300 | Apple clang 17.0.0, Homebrew clang 22.1.2, GCC 15.2.0 | 15 | 257 | 0 | 0 | 2 | 41 skipped: timed out under ASan (labelled `ub` by the harness version that ran this campaign; fixed in the next commit, verdict `san-timeout`) | 0 |
| campaign2_csmith (11 Oct 2026, macOS arm64, harness with `san-timeout`) | csmith 2.3.0 | 300 | Apple clang 17.0.0, Homebrew clang 22.1.2, GCC 15.2.0 | 15 | 272 | 0 | 0 | 1 | 27 skipped (`san-timeout`, 90 s under ASan) | 0 |
| campaign1_smallgen (11 Oct 2026, macOS arm64) | smallgen (built in) | 4000 | Apple clang 17.0.0, Homebrew clang 22.1.2, GCC 15.2.0 | 15 | 4000 | 0 | 0 | 0 | 0 | 0 |

Totals so far: 4,600 programs generated; 4,529 passed the sanitizer gate and were compiled and run under all 15 configs (about 68,000 compile-and-run pairs); 0 divergences, 0 compiler crashes. 0 of 4,000 smallgen programs were rejected by the sanitizer gate after the index fix (the first smoke run caught 2 of 20 before it).
