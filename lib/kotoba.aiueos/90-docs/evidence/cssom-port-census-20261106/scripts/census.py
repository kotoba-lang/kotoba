#!/usr/bin/env python3
"""Float-site census. usage: census.py OUT.tsv  (prints per-file x category table)."""
import re, sys, csv, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strip import strip_file
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../..')) + '/'
FILES = ['kotoba.cssom/src/cssom/core.cljk', 'kotoba.cssom/src/cssom/layout.cljk', 'kotoba.htmldom/src/htmldom/core.cljk',
         'kotoba.domGpu/src/kotoba/wasm/dom.cljk', 'kotoba.domGpu/src/kotoba/wasm/dom.kotoba',
         'kotoba.domGpu/src/kotoba/wasm/host/color.cljk',
         'kotoba.browser/src/browser/surface.cljk', 'kotoba.browser/src/browser/text_edit.kotoba',
         'kotoba.text/src/kotoba/lang/text.cljk', 'kotoba.text/src/kotoba/lang/text.kotoba',
         'kotoba.text/src/kotoba/lang/bounded_regex.kotoba']
PATS = [
    ('F1-double-parse-nan', re.compile(r'\((?:double|float)[\s)]|\b(?:double|float)\?|parse-double|parseFloat|Double/|Float/|##-?(?:Inf|NaN)|\bNaN\?|\binfinite\?|js/isFinite|js/isNaN|js/Number|js/parseInt|\(num[\s)]')),
    ('F2-Math', re.compile(r'(?:js/)?Math/[A-Za-z_]+|js/Math\.[A-Za-z]+')),
    ('F3-float-literal', re.compile(r'(?<![\w.\\/:#-])-?\d+\.\d+(?:[eE][-+]?\d+)?(?![\w.])|(?<![\w.\\/:#])-?\d+[eE][-+]?\d+(?![\w.])|(?<![\w.\\/:#])-?\d+\.(?![\w.\d])')),
    ('F4-slash-division', re.compile(r'\(/[\s)]')),
    ('F5-int-coercion', re.compile(r'\((?:long|int|unchecked-[a-z-]+)[\s)]')),
    ('F6-quot-rem-mod', re.compile(r'\((?:quot|rem|mod)[\s)]')),
    ('F7-round-floor-ceil-ident', re.compile(r'(?<![/\w-])(?:round|floor|ceil|round-\w+|floor-\w+|ceil-\w+)(?![\w?])')),
    ('F8-number-tower-check', re.compile(r'\b(?:number\?|ratio\?|integer\?|int\?|pos-int\?|float\?|decimal\?|rational\?)')),
    ('F9-typed-f64', re.compile(r':f64\b|\bf64-[a-z]+|\bf32\b')),
]
DEF = re.compile(r'^\((?:defn-?|def|defmacro|defmulti|defmethod|defonce|declare|defrecord|deftype)\s+(?:\^\S+\s+)*([^\s\[\(\)]+)')
rows = []
for rel in FILES:
    cur = '<top>'
    for ln, code, raw in strip_file(ROOT + rel):
        m = DEF.match(code)
        if m:
            cur = m.group(1)
        for cat, rx in PATS:
            for mm in rx.finditer(code):
                rows.append((rel.split('/')[-1], rel, ln, cat, cur, mm.group(0), raw.strip()[:160]))
with open(sys.argv[1], 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(['file', 'path', 'line', 'category', 'enclosing_def', 'match', 'source_line'])
    w.writerows(rows)
from collections import Counter
c = Counter((r[1], r[3]) for r in rows)
cats = [p[0] for p in PATS]
print('file\t' + '\t'.join(cats))
for rel in FILES:
    print(rel + '\t' + '\t'.join(str(c[(rel, k)]) for k in cats))
print('TOTAL\t' + '\t'.join(str(sum(1 for r in rows if r[3] == k)) for k in cats))
