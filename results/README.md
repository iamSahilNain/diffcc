# Campaigns

Counts are filled in from `summary.json` after each run. Nothing here is
estimated.

| Campaign | Origin | Programs | Compilers | Configs | agree | diverge | compiler-crash | ub | timeouts | harness-error |
|---|---|---|---|---|---|---|---|---|---|---|
| campaign1_csmith (11 Oct 2026, macOS arm64) | csmith 2.3.0 | 300 | Apple clang 17.0.0, Homebrew clang 22.1.2, GCC 15.2.0 | 15 | 257 | 0 | 0 | 2 | 41 skipped: timed out under ASan (labelled `ub` by the harness version that ran this campaign; fixed in the next commit, verdict `san-timeout`) | 0 |
