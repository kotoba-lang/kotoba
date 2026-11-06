#!/usr/bin/env python3
"""Assign each float-site row of sites.tsv to a computation group. usage: groups.py sites.tsv OUT-sites.tsv OUT-groups.tsv"""
import csv, sys, re
from collections import defaultdict
G = [
 ('G01-decimal-parse', r'^(parse-dbl|parse-px|parse-int|border-px|css-parse-number|parse-number|parse-style-value|parse-counter-amount|parse-media-number|parse-media-width|numeric-char-ref->str|codepoint->str|calc-pattern-parts|syntax-component-support|attr-typed-value|computationally-independent\?|nth-matches\?|parse-track-list|parse-grid-line-token|parse-grid-placement|non-initial\?|gap-shorthand-axis(-raw)?|spacing-px|vertical-align-length|resolve-constant-calc)$'),
 ('G02-percent-and-em-resolution', r'^(percentage-of|resolve-font-size|font-size-scale-step|parse-media-length|as-length|resolvable-container-width|text-indent-of|first-letter-unit-length|vertical-align-percentage|parse-minmax-token|parse-track-token|track-sizes|distribute-equally-with-caps|distribute-fr|distribute-excess|resolve-flexible-lengths)$'),
 ('G03-calc', r'^(eval-calc-node|calc-result->number|calc-number-at)$'),
 ('G04-colour', r'^(unit|parse-css-double|parse-channel-token|parse-alpha-token|parse-percent-token|hsl->rgb)$'),
 ('G05-transform-matrix', r'^(identity-matrix|round-4|transform-.*|apply-element-transform|flow-rotation|apply-flow-rotation|reanchor-text-ops|orthogonal-fallback-inline-size)$'),
 ('G06-line-height-and-font-metrics', r'^(resolve-line-height|line-height-multiplier|inherited-line-height|leading-ascent|font-metrics|inline-line-metrics|glyph-advance|tab-runs|tab-stop-width|symbol-marker-advance|ua-control-font|select-option-height|longest-word-width|atomic-intrinsic-width|flex-item-min-content-width|layout-form-control|text-lines|layout-text|line-align-offset|text-advance|tab-.*)$'),
 ('G07-flex-grid-table-multicol-sizing', r'^(place-main-axis(-auto-margins)?|cross-offset|layout-flex(-wrap-row)?|layout-grid|layout-table|table-.*|multicol-.*|layout-multicol|frag-.*|flex-item-baseline|layout-block|layout-children-block|layout-absolute-children)$'),
 ('G08-aspect-ratio-and-replaced-size', r'^(aspect-ratio.*|replaced-.*)$'),
 ('G09-vertical-align-and-inline-fragments', r'^(vertical-align-shift|inline-fragments|inline-line-metrics)$'),
 ('G10-form-number-validation', r'^(step-invalid\?|step-mismatch-tolerance)$'),
 ('G11-opacity-flex-factors-and-style-numbers', r'^(node-style|stacking-context\?|layout-node|draw-ops)$'),
 ('G12-cascade-proximity-sentinels', r'^(resolve-style-and-flow)$'),
 ('G13-text-format-helpers', r'^(fixed|format|fmt-one|to-hex|expand-template|java-whitespace\?|codepoints|from-codepoints|index-of|last-index-of|pad-center-text|kotoba-code-unit-at|adv-step)$'),
]
G = [(n, re.compile(rx)) for n, rx in G]
def grp(d):
    for n, rx in G:
        if rx.match(d):
            return n
    return 'UNGROUPED'
rows = list(csv.DictReader(open(sys.argv[1]), delimiter='\t'))
for r in rows:
    r['group'] = grp(r['enclosing_def'])
    r['strong'] = '1' if r['category'][:2] in ('F1', 'F2', 'F3', 'F9') else '0'
cols = ['file', 'path', 'line', 'category', 'group', 'strong', 'enclosing_def', 'match', 'source_line']
with open(sys.argv[2], 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter='\t', extrasaction='ignore'); w.writeheader(); w.writerows(rows)
agg = defaultdict(lambda: {'strong_hits': 0, 'secondary_hits': 0, 'strong_lines': set(), 'all_lines': set(), 'defs': set(), 'files': defaultdict(int)})
for r in rows:
    a = agg[r['group']]
    key = (r['path'], r['line'])
    a['all_lines'].add(key); a['defs'].add(r['enclosing_def'])
    if r['strong'] == '1':
        a['strong_hits'] += 1; a['strong_lines'].add(key); a['files'][r['file']] += 1
    else:
        a['secondary_hits'] += 1
with open(sys.argv[3], 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(['group', 'strong_hits', 'strong_distinct_lines', 'secondary_hits', 'distinct_lines_any', 'distinct_defs', 'strong_hits_by_file'])
    for n in sorted(agg):
        a = agg[n]
        w.writerow([n, a['strong_hits'], len(a['strong_lines']), a['secondary_hits'], len(a['all_lines']), len(a['defs']), ';'.join('%s=%d' % kv for kv in sorted(a['files'].items()))])
tot = [sum(a['strong_hits'] for a in agg.values()), len(set().union(*[a['strong_lines'] for a in agg.values()])), sum(a['secondary_hits'] for a in agg.values())]
print('TOTAL strong_hits=%d strong_distinct_lines=%d secondary_hits=%d' % tuple(tot))
print([ (r['enclosing_def'], r['file'], r['line']) for r in rows if r['group']=='UNGROUPED'][:20])
for n in sorted(agg): print(n, agg[n]['strong_hits'], len(agg[n]['strong_lines']), agg[n]['secondary_hits'])
