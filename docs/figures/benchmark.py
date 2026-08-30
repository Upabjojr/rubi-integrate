# -*- coding: utf-8 -*-
"""Measure what the merged discrimination net buys, for RuleBasedIntegration/Rubi#62.

Three things, all on the real Rubi rule set:

  1. cold-start cost      -- what blending every pattern into one net costs in
                             time and resident memory (the downside)
  2. locality             -- how much of the net a single match actually walks
  3. many-to-one vs loop  -- the merged net against OmniMatch's own one-at-a-time
                             matcher, over a growing slice of the rule set

Usage:  python docs/figures/benchmark.py
"""
import resource
import time
import warnings

warnings.filterwarnings('ignore')

import sympy
from sympy import Symbol

from omnimatch.matching import many_to_one as m2o_mod
from omnimatch.matching.one_to_one import match as one_to_one_match
from rubi_integrate.base_objects import Int, _defer_expensive_guard, load_rule_patterns
from sympy_matching.matching_rule import build_replacer, to_omnimatch_expression

x = Symbol('x')
a, b = sympy.symbols('a b')

SUBJECTS = [
    Int(1 / x, x),
    Int(x ** 3, x),
    Int((2 + 3 * x) ** 5, x),
    Int(1 / (a + b * x), x),
    Int(x ** 2 * (a + b * x) ** 3, x),
    Int((a + b * x ** 2) ** 3, x),
    Int(x / (a + b * x ** 6), x),
    Int(sympy.sqrt(a + b * x), x),
]


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def count_visited(matcher, subject):
    """States walked, and matches returned, for one match over `matcher`.

    `_MatchIter._match` is wrapped to record the states it enters. (The module has
    a `_VISITED` set the drawing code reads, but nothing populates it.)
    """
    visited = set()
    original = m2o_mod._MatchIter._match

    def traced(self, state):
        visited.add(state.number)
        yield from original(self, state)

    m2o_mod._MatchIter._match = traced
    try:
        hits = sum(1 for _ in matcher.match(to_omnimatch_expression(subject)))
    finally:
        m2o_mod._MatchIter._match = original
    return visited, hits


def main():
    subjects_mp = [to_omnimatch_expression(s) for s in SUBJECTS]

    # ---------------------------------------------------------------- cold start
    print('=== cold start (the price of merging) ===')
    print('RSS at start                : {:8.0f} MB'.format(rss_mb()))
    t0 = time.perf_counter()
    rules = list(load_rule_patterns('**'))
    t_load = time.perf_counter() - t0
    print('rules parsed from disk      : {} rules in {:.1f}s   RSS {:.0f} MB'.format(
        len(rules), t_load, rss_mb()))

    t0 = time.perf_counter()
    matcher = build_replacer(rules, defer_constraint=_defer_expensive_guard).matcher
    t_build = time.perf_counter() - t0
    print('discrimination net built    : {} states in {:.1f}s   RSS {:.0f} MB'.format(
        len(matcher.states), t_build, rss_mb()))
    print('TOTAL cold start            : {:.1f}s'.format(t_load + t_build))
    print('states per rule             : {:.2f}'.format(len(matcher.states) / len(rules)))

    shared = total = carried = 0
    for state in matcher.states:
        for transitions in state.transitions.values():
            for transition in transitions:
                total += 1
                carried += len(transition.patterns)
                if len(transition.patterns) > 1:
                    shared += 1
    print('transitions                 : {} ({} shared by >1 pattern, {:.1f}%)'.format(
        total, shared, 100.0 * shared / total))
    print('avg patterns per transition : {:.1f}'.format(carried / total))

    # ------------------------------------------------------------------ locality
    print('\n=== how much of the net one match touches ===')
    print('{:<30} {:>22} {:>9}'.format('subject', 'states visited', 'matches'))
    for subject in SUBJECTS:
        visited, hits = count_visited(matcher, subject)
        print('{:<30} {:>7} / {} ({:5.2f}%) {:>9}'.format(
            str(subject), len(visited), len(matcher.states),
            100.0 * len(visited) / len(matcher.states), hits))

    # ------------------------------------------------- many-to-one vs one-at-a-time
    print('\n=== merged net vs looping over the patterns ===')
    print('{:>7} {:>9} {:>9} {:>12} {:>14} {:>9}'.format(
        'rules', 'states', 'build', 'many-to-one', 'one-at-a-time', 'speed-up'))
    for n in [100, 400, 1600, 3200, 6400, len(rules)]:
        t0 = time.perf_counter()
        sub_matcher = build_replacer(
            rules[:n], defer_constraint=_defer_expensive_guard).matcher
        t_build_n = time.perf_counter() - t0
        patterns = [p for p, _label, _c in sub_matcher.patterns]

        def run_many_to_one():
            t = time.perf_counter()
            for subject in subjects_mp:
                for _ in sub_matcher.match(subject):
                    pass
            return time.perf_counter() - t

        def run_one_at_a_time():
            t = time.perf_counter()
            for subject in subjects_mp:
                for pattern in patterns:
                    for _ in one_to_one_match(subject, pattern):
                        pass
            return time.perf_counter() - t

        # best of 3: this is a comparison of algorithms, not of GC luck
        t_m2o = min(run_many_to_one() for _ in range(3))
        t_o2o = min(run_one_at_a_time() for _ in range(3))
        print('{:>7} {:>9} {:>8.2f}s {:>10.1f}ms {:>12.1f}ms {:>8.1f}x'.format(
            n, len(sub_matcher.states), t_build_n,
            t_m2o * 1000, t_o2o * 1000, t_o2o / t_m2o))


if __name__ == '__main__':
    main()
