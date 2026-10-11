"""diffcc: differential testing of C compilers.

Generate C programs (csmith, or the built-in generator), compile each one
with several compilers and optimisation levels, run every binary, and report
any program on which the compilers disagree or crash. Programs that trip
UBSan or ASan are discarded before comparison so that every reported
divergence is a candidate compiler bug, not undefined behaviour.
"""
__version__ = "0.1.0"
