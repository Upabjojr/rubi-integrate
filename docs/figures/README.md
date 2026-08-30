# Many-to-one matching figures

Figures and measurements backing the discussion in
[RuleBasedIntegration/Rubi#62](https://github.com/RuleBasedIntegration/Rubi/issues/62):
why `rubi_integrate` blends every Rubi rule pattern into a single generalized
discrimination net instead of trying the rules one at a time, what that costs,
and how Rubi's first-match-wins rule order is recovered on top of it.

Everything here is generated from a live OmniMatch matcher — no hand-drawn
diagrams, no illustrative pseudo-data.

## The figures

| file | what it shows |
|---|---|
| `fig1_patterns.png` | the 5 rules of Rubi module `1.1.1.1 (a+b x)^m` as pattern trees — all `Int(Pow(…), x)`, three sharing an `Add` subtree |
| `fig2_separate.png` | the same 5 rules as 5 **independent** automata: `Int( → Pow(` re-walked once per rule |
| `fig3_merged.png` | the same 5 rules blended into **one** net; red edges are transitions carried by more than one pattern |
| `fig4_one_traversal.png` | a real match of `Int((2+3x)^5, x)` over that net — orange = states walked, green = rule reached, grey = pruned without ever being tried |

Module `1.1.1.1` is used throughout because it is the one rule file small enough
to draw legibly (5 rules) while still being representative: every rule is a power
of a linear form, so the patterns overlap the way real Rubi patterns do.

## Reproducing

Both scripts need the `graphviz` Python package and the `dot` binary.

```
python docs/figures/generate_figures.py [outdir]   # redraws all four figures
python docs/figures/benchmark.py                   # cold start, locality, speed-up
```

`benchmark.py` loads the full rule set and takes a few minutes.

## Measurements

Full rule set, CPython, this machine:

```
rules parsed from disk      : 7707 rules in 7.5s
discrimination net built    : 38403 states in 12.4s   RSS 942 MB
TOTAL cold start            : 19.9s
transitions                 : 38402 (1910 shared by >1 pattern)
```

How much of that 38k-state net a single match actually walks:

| subject | states visited | matches |
|---|---|---|
| `Int(1/x, x)` | 76 / 38403 (0.20 %) | 19 |
| `Int(x**3, x)` | 79 / 38403 (0.21 %) | 20 |
| `Int((2+3x)**5, x)` | 296 / 38403 (0.77 %) | 25 |
| `Int(1/(a+b x), x)` | 276 / 38403 (0.72 %) | 22 |
| `Int((a+b x**2)**3, x)` | 415 / 38403 (1.08 %) | 25 |
| `Int(sqrt(a+b x), x)` | 96 / 38403 (0.25 %) | 24 |
| `Int(x/(a+b x**6), x)` | 4435 / 38403 (11.55 %) | 39 |
| `Int(x**2 (a+b x)**3, x)` | 7001 / 38403 (18.23 %) | 48 |

The last two rows are the honest worst case: a product of commutative sums makes
the associative-commutative sub-matcher enumerate partitions, and locality
degrades. The typical case is well under 1 %.

Merged net against OmniMatch's own one-at-a-time matcher, same rules, same
subjects, best of three:

| rules | states | many-to-one | one-at-a-time | speed-up |
|---|---|---|---|---|
| 100 | 341 | 2.8 ms | 15.5 ms | 5.5× |
| 400 | 1334 | 7.9 ms | 50.9 ms | 6.4× |
| 1600 | 5160 | 24.1 ms | 212.7 ms | 8.8× |
| 3200 | 11741 | 120.0 ms | 598.1 ms | 5.0× |
| 6400 | 30404 | 288.8 ms | 1214.3 ms | 4.2× |
| 7707 | 38403 | 375.6 ms | 1502.8 ms | 4.0× |

## On rule order

A discrimination net yields matches in its own internal order, which is unrelated
to Rubi's. Rubi is first-match-wins, so the order *is* the semantics — getting it
wrong silently returns a different antiderivative rather than failing.

The net decides *which* rules match; a separate cheap step decides *which one
wins*. See `rubi_integrate/rule_order.py` and `_rule_priority` in
`rubi_integrate/base_objects.py`:

1. Priority comes from `Rubi.m`'s explicit `LoadRules[...]` sequence, not from the
   dotted section numbers — the two disagree in 22 places.
2. The rule list is sorted into that order **once**, at load time, and each rule's
   index is stamped onto the callback the matcher yields.
3. At match time the net's handful of candidates is sorted by that integer. The
   net has already cut 7707 rules down to ~20, so the sort is negligible.

Known gap: within a file, rules are ordered by their position in the source,
whereas Mathematica reorders `DownValues` by specificity. The authoritative order
is the one extracted from Mathematica's `DownValues`, published in
[symbolica-integrate](https://github.com/symbolica-dev/symbolica-integrate).

Known wart: sorting candidates by priority requires **exhausting** the match
generator, so every match is paid for even though only the first is wanted. The
proper fix is for the net to emit matches in priority order lazily.
