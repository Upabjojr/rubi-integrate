# -*- coding: utf-8 -*-
"""Render the many-to-one matching figures used in RuleBasedIntegration/Rubi#62.

Draws, straight from a live OmniMatch matcher:

  fig1_patterns.png      the 5 rules of Rubi 1.1.1.1 as pattern trees
  fig2_separate.png      the same 5 rules as 5 INDEPENDENT automata ("loop over rules")
  fig3_merged.png        the same 5 rules blended into ONE discrimination net
  fig4_one_traversal.png a real match walked over that net, visited states highlighted

Usage:  python docs/figures/generate_figures.py [outdir]
Requires the `graphviz` Python package and the `dot` binary.
"""
import html
import sys
import warnings

warnings.filterwarnings('ignore')

import sympy
from graphviz import Digraph
from sympy import Symbol

from omnimatch.expressions.expressions import Operation, Wildcard
from omnimatch.expressions.functions import op_iter
from omnimatch.matching import many_to_one as m2o_mod
from omnimatch.matching.many_to_one import (
    LabelTypeEnd, LabelTypeEpsilon, LabelTypeExpression, LabelTypeOperation,
)
from rubi_integrate.base_objects import Int, load_rule_patterns
from sympy_matching.matching_rule import build_replacer, to_omnimatch_expression

# The one rule file small enough to draw and typical enough to be worth drawing:
# 5 rules, all of them Int(Pow(...), x), three sharing a whole Add subtree.
MODULE = ('r_1_algebraic_functions/r_1_1_binomial_products/'
          'r_1_1_1_linear/r_1_1_1_1.py')
SUBJECT_FOR_TRAVERSAL = None  # set below, needs `x`

PALETTE = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd', '#ff7f0e', '#8c564b', '#17becf']


def pcolor(pid):
    return PALETTE[pid % len(PALETTE)]


def esc(obj):
    return html.escape(str(obj))


def fmt_label(label):
    """A terse, readable rendering of a transition label."""
    if isinstance(label, LabelTypeEnd):
        return ')'
    if isinstance(label, LabelTypeEpsilon):
        return '&epsilon;'
    if isinstance(label, LabelTypeOperation):
        head = label.unwrap()
        return esc(getattr(head, 'name', head)) + '('
    if isinstance(label, LabelTypeExpression):
        value = label.unwrap()
        if isinstance(value, Wildcard) or type(value).__name__ == 'Wildcard':
            return '_'
        return esc(getattr(value, 'name', value))
    return esc(label)


def pset(patterns, names):
    """The coloured {R1, R4} pattern-id set that annotates each transition."""
    return '{' + ', '.join(
        '<font color="{}"><b>{}</b></font>'.format(pcolor(p), names[p])
        for p in sorted(patterns)
    ) + '}'


def add_automaton(graph, matcher, prefix, names, highlight_shared=True):
    """Draw `matcher`'s automaton into `graph`, node names prefixed with `prefix`."""
    for state in matcher.states:
        name = '{}n{}'.format(prefix, state.number)
        if state.matcher is not None:
            graph.node(name, 'AC sub-matcher', shape='box', style='filled',
                       fillcolor='#f0e6ff', fontname='Helvetica', fontsize='11')
        elif state.number in matcher.finals:
            graph.node(name, '', shape='doublecircle', width='0.22', style='filled',
                       fillcolor='#2ca02c', color='#1a6b1a')
        else:
            graph.node(name, '', shape='circle', width='0.18', style='filled',
                       fillcolor='#dddddd', color='#888888')

    for state in matcher.states:
        for transitions in state.transitions.values():
            for transition in transitions:
                shared = len(transition.patterns) > 1
                attrs = {'fontname': 'Helvetica', 'fontsize': '11'}
                if highlight_shared and shared:
                    # A transition carrying several patterns is walked ONCE for all
                    # of them. This is where the many-to-one saving actually lives.
                    attrs['color'] = '#d62728'
                    attrs['penwidth'] = str(min(1.0 + len(transition.patterns), 6.0))
                else:
                    attrs['color'] = '#999999'
                graph.edge(
                    '{}n{}'.format(prefix, state.number),
                    '{}n{}'.format(prefix, transition.target.number),
                    '<{}<br/><font point-size="9">{}</font>>'.format(
                        fmt_label(transition.label), pset(transition.patterns, names)),
                    **attrs)


def rule_caption(index, rule):
    return '<<font color="{}"><b>R{}</b></font>&nbsp;&nbsp;{}>'.format(
        pcolor(index), rule.rule_number, esc(rule.pattern))


# --------------------------------------------------------------------------- fig 1

def fig_patterns(rules, outdir):
    """The rule patterns as plain expression trees -- shows how alike they are."""
    graph = Digraph('patterns', graph_attr={
        'rankdir': 'TB', 'bgcolor': 'white', 'fontname': 'Helvetica',
        'nodesep': '0.25', 'ranksep': '0.35'})
    counter = [0]

    def walk(sub, expr, prefix, parent=None):
        nid = '{}{}'.format(prefix, counter[0])
        counter[0] += 1
        if isinstance(expr, Operation):
            sub.node(nid, str(expr.head.name), shape='box', style='rounded,filled',
                     fillcolor='#e8eefc', color='#4a6fa5',
                     fontname='Helvetica-Bold', fontsize='12')
        elif isinstance(expr, Wildcard) or type(expr).__name__ == 'Wildcard':
            sub.node(nid, (getattr(expr, 'variable_name', None) or '') + '_',
                     shape='circle', style='filled', fillcolor='#fff2cc',
                     color='#d6a300', fontname='Helvetica-Bold', fontsize='12')
        else:
            sub.node(nid, str(expr), shape='circle', style='filled',
                     fillcolor='#e6ffe6', color='#4caf50',
                     fontname='Helvetica', fontsize='12')
        if parent is not None:
            sub.edge(parent, nid, color='#888888', arrowsize='0.6')
        if isinstance(expr, Operation):
            for child in op_iter(expr):
                walk(sub, child, prefix, nid)

    for i, rule in enumerate(rules):
        with graph.subgraph(name='cluster_p{}'.format(i)) as sub:
            sub.attr(label=rule_caption(i, rule).replace('R{}'.format(rule.rule_number),
                                                         'Rule {}'.format(rule.rule_number)),
                     fontname='Helvetica', fontsize='13', color='#cccccc', style='rounded')
            walk(sub, to_omnimatch_expression(rule.pattern), 'p{}_'.format(i))

    graph.render('{}/fig1_patterns'.format(outdir), format='png', cleanup=True)


# --------------------------------------------------------------------------- fig 2

def fig_separate(rules, outdir):
    """One independent automaton per rule -- what looping over the rules means."""
    graph = Digraph('separate', graph_attr={
        'rankdir': 'TB', 'bgcolor': 'white', 'fontname': 'Helvetica',
        'nodesep': '0.22', 'ranksep': '0.40', 'compound': 'true'})
    total = 0
    for i, rule in enumerate(rules):
        matcher = build_replacer([rule]).matcher
        total += len(matcher.states)
        with graph.subgraph(name='cluster_{}'.format(i)) as sub:
            sub.attr(label=rule_caption(i, rule), fontname='Helvetica', fontsize='13',
                     color='#bbbbbb', style='rounded')
            # each rule gets its OWN automaton, so node names must not collide
            add_automaton(sub, matcher, 'r{}_'.format(i),
                          names=['R{}'.format(rule.rule_number)], highlight_shared=False)
    graph.render('{}/fig2_separate'.format(outdir), format='png', cleanup=True)
    return total


# --------------------------------------------------------------------------- fig 3

def fig_merged(rules, matcher, names, outdir):
    """All rules blended into one net; edges shared by >1 pattern drawn in red."""
    graph = Digraph('merged', graph_attr={
        'rankdir': 'TB', 'bgcolor': 'white', 'fontname': 'Helvetica',
        'nodesep': '0.25', 'ranksep': '0.45', 'splines': 'true'})
    rows = ''.join(
        '<tr><td align="left"><font color="{}"><b>{}</b></font></td>'
        '<td align="left">{}</td></tr>'.format(pcolor(i), names[i], esc(r.pattern))
        for i, r in enumerate(rules))
    graph.node('legend',
               '<<table border="0" cellborder="0" cellspacing="2">'
               '<tr><td colspan="2"><b>Rubi 1.1.1.1 &nbsp;(a+b x)^m &mdash; all 5 rules'
               '</b></td></tr>{}</table>>'.format(rows),
               shape='box', style='rounded', fontname='Helvetica', fontsize='12')
    add_automaton(graph, matcher, 'm', names)
    graph.render('{}/fig3_merged'.format(outdir), format='png', cleanup=True)


# --------------------------------------------------------------------------- fig 4

def fig_one_traversal(matcher, names, subject, outdir):
    """A real match over the merged net, with the states it actually walked lit up.

    `_MatchIter._match` is wrapped to record visited states: the module already has
    a `_VISITED` set that the drawing code reads, but nothing ever populates it.
    """
    visited = set()
    original = m2o_mod._MatchIter._match

    def traced(self, state):
        visited.add(state.number)
        yield from original(self, state)

    m2o_mod._MatchIter._match = traced
    try:
        hits = [label for label, _subst in
                matcher.match(to_omnimatch_expression(subject))]
    finally:
        m2o_mod._MatchIter._match = original

    fired = sorted({getattr(h, '__qualname__', '').rsplit(':[', 1)[-1].rstrip(']')
                    for h in hits})
    pruned = [n for i, n in enumerate(names)
              if 'R{}'.format(names[i][1:]) not in ['R' + f for f in fired]]

    graph = Digraph('visited', graph_attr={
        'rankdir': 'TB', 'bgcolor': 'white', 'fontname': 'Helvetica',
        'nodesep': '0.25', 'ranksep': '0.45'})
    graph.node('title',
               '<<table border="0" cellspacing="2">'
               '<tr><td><b>ONE traversal for subject &nbsp;'
               '<font color="#b8860b">Int((2+3x)<sup>5</sup>, x)</font></b></td></tr>'
               '<tr><td align="left">orange = states actually walked ({} of {})</td></tr>'
               '<tr><td align="left">green = rule reached &mdash; <b>{} matches (rules {}) '
               'from that single walk</b></td></tr>'
               '<tr><td align="left">grey = pruned: {} were ruled out without ever being '
               'tried</td></tr></table>>'.format(
                   len(visited), len(matcher.states), len(hits),
                   ', '.join('R' + f for f in fired), ', '.join(pruned)),
               shape='box', style='rounded', fontname='Helvetica', fontsize='12')

    for state in matcher.states:
        name = 'n{}'.format(state.number)
        on = state.number in visited
        if state.matcher is not None:
            graph.node(name, 'AC sub-matcher', shape='box', style='filled',
                       fillcolor='#ffd9a0' if on else '#f3f3f3',
                       color='#e07b00' if on else '#cccccc',
                       fontname='Helvetica', fontsize='11')
        elif state.number in matcher.finals:
            graph.node(name, '', shape='doublecircle', width='0.24', style='filled',
                       fillcolor='#2ca02c' if on else '#eeeeee',
                       color='#1a6b1a' if on else '#cccccc')
        else:
            graph.node(name, '', shape='circle', width='0.20', style='filled',
                       fillcolor='#ffb347' if on else '#f3f3f3',
                       color='#e07b00' if on else '#cccccc')

    for state in matcher.states:
        for transitions in state.transitions.values():
            for transition in transitions:
                on = state.number in visited and transition.target.number in visited
                graph.edge('n{}'.format(state.number),
                           'n{}'.format(transition.target.number),
                           '<{}<br/><font point-size="9">{}</font>>'.format(
                               fmt_label(transition.label),
                               pset(transition.patterns, names)),
                           color='#e07b00' if on else '#dddddd',
                           penwidth='2.4' if on else '1.0',
                           fontcolor='#333333' if on else '#bbbbbb',
                           fontname='Helvetica', fontsize='11')

    graph.render('{}/fig4_one_traversal'.format(outdir), format='png', cleanup=True)
    return visited, hits


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else 'docs/figures'
    x = Symbol('x')
    subject = Int((2 + 3 * x) ** 5, x)

    rules = list(load_rule_patterns(MODULE))
    names = ['R{}'.format(r.rule_number) for r in rules]
    matcher = build_replacer(rules).matcher

    fig_patterns(rules, outdir)
    separate_states = fig_separate(rules, outdir)
    fig_merged(rules, matcher, names, outdir)
    visited, hits = fig_one_traversal(matcher, names, subject, outdir)

    print('rules                    : {}'.format(len(rules)))
    print('states, one net per rule : {}'.format(separate_states))
    print('states, single merged net: {}'.format(len(matcher.states)))
    print('subject                  : {}'.format(subject))
    print('states walked            : {} of {}'.format(len(visited), len(matcher.states)))
    print('matches returned         : {}'.format(len(hits)))
    print('figures written to       : {}'.format(outdir))


if __name__ == '__main__':
    main()
