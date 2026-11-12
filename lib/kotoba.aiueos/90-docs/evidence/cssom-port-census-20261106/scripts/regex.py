#!/usr/bin/env python3
"""Regex literal + re-* call census. usage: regex.py OUT.tsv"""
import re, sys, csv, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strip import strip_file
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../..')) + '/'
FILES = ['kotoba.cssom/src/cssom/core.cljk', 'kotoba.cssom/src/cssom/layout.cljk', 'kotoba.htmldom/src/htmldom/core.cljk',
         'kotoba.css/src/css/core.cljk', 'kotoba.css/src/css/utility.cljk', 'kotoba.css/src/css/build.cljk',
         'kotoba.html/src/html/core.cljk',
         'kotoba.domGpu/src/kotoba/wasm/dom.cljk', 'kotoba.domGpu/src/kotoba/wasm/host/color.cljk',
         'kotoba.browser/src/browser/surface.cljk', 'kotoba.text/src/kotoba/lang/text.cljk']
CALLS = re.compile(r'\((re-find|re-seq|re-matches|re-pattern|re-matcher|re-groups|re-quote-replacement)[\s)]|\((str/(?:replace|replace-first|split|split-lines)|clojure\.string/(?:replace|split))[\s)]')


def literals(path):
    """Yield (lineno, pattern_text, preceding_call_on_line) for each #"..." literal outside strings/comments."""
    lines = open(path, encoding='utf-8').read().split('\n')
    in_str = False
    cur = None
    cur_start = None
    out = []
    for ln, line in enumerate(lines, 1):
        i = 0
        n = len(line)
        while i < n:
            c = line[i]
            if in_str:
                if c == '\\' and i + 1 < n:
                    if cur is not None:
                        cur.append(line[i:i + 2])
                    i += 2
                    continue
                if c == '"':
                    in_str = False
                    if cur is not None:
                        out.append((cur_start, ''.join(cur), line[:i]))
                        cur = None
                else:
                    if cur is not None:
                        cur.append(c)
                i += 1
                continue
            if c == ';':
                break
            if c == '\\' and i + 1 < n:
                i += 2
                continue
            if c == '#' and i + 1 < n and line[i + 1] == '"':
                in_str = True
                cur = []
                cur_start = ln
                i += 2
                continue
            if c == '"':
                in_str = True
                cur = None
                i += 1
                continue
            i += 1
        if in_str and cur is not None:
            cur.append('\n')
    return out


def features(p):
    f = []
    q = re.sub(r'\\.', 'E', p)          # drop escapes
    q = re.sub(r'\[(?:[^\]\\]|\\.)*\]', 'K', p.replace('\\\\', 'E')) if False else q
    # bracket classes collapsed to K (handles ]-first loosely)
    q2 = re.sub(r'\[\^?\]?(?:[^\]\\]|\\.)*\]', 'K', p)
    q2 = re.sub(r'\\.', 'E', q2)
    if re.search(r'\(\?<[=!]', p): f.append('lookbehind')
    if re.search(r'\(\?[=!]', p): f.append('lookahead')
    if re.search(r'\(\?:', p): f.append('noncapture-group')
    if re.search(r'\((?!\?)', q2): f.append('capture-group')
    elif '(' in q2 and 'noncapture-group' not in f and 'lookahead' not in f and 'lookbehind' not in f: f.append('group')
    if re.search(r'\{\d', q2): f.append('counted-repeat')
    if re.search(r'\\[1-9]', p): f.append('backref')
    if re.search(r'\\[pP]\{', p): f.append('unicode-prop')
    if re.search(r'\\b|\\B', p): f.append('word-boundary')
    if re.search(r'[*+?}]\?', q2): f.append('lazy')
    if re.search(r'\(\?[a-z]+\)', p): f.append('inline-flag')
    if re.search(r'\\[uUxX]', p): f.append('hex-escape')
    if '|' in q2 and any(x in f for x in ('capture-group', 'noncapture-group', 'group')): f.append('alt-in-group')
    return f


def classify(p, feats, call):
    call = call.split('->')[-1] if call.startswith('def:') else call
    hard = {'backref', 'unicode-prop', 'lookbehind'}
    if hard & set(feats):
        return 'c'
    bounded_ok = not ({'capture-group', 'noncapture-group', 'group', 'counted-repeat', 'lookahead', 'lookbehind', 'word-boundary', 'lazy', 'inline-flag', 'hex-escape', 'unicode-prop', 'backref'} & set(feats))
    if bounded_ok and not any(x in call for x in ('str/replace', 'str/split', 're-seq', 're-groups', 'no direct re-call')):
        return 'b'
    return 'a'


rows = []
callrows = []
for rel in FILES:
    for ln, pat, before in literals(ROOT + rel):
        m = None
        for mm in re.finditer(r'\(\s*([A-Za-z./-]+)[\s]', before):
            m = mm.group(1)
        # find nearest known call
        call = ''
        for mm in re.finditer(r'\((re-find|re-seq|re-matches|re-pattern|re-matcher|re-groups|str/replace-first|str/replace|str/split-lines|str/split|clojure\.string/replace|clojure\.string/split)[\s]', before):
            call = mm.group(1)
        if not call:
            call = '(def/value)'
        feats = features(pat)
        if call == '(def/value)':
            lines_ = open(ROOT + rel, encoding='utf-8').read().split('\n')
            ctx = ' '.join(lines_[max(0, ln - 3):ln])
            dm = re.findall(r'\((?:def|defn-?|def\^?\S*)\s+(?:\^\S+\s+)*([^\s\[\(\)]+)', ctx)
            if dm:
                nm = dm[-1]
                uses = set()
                for l2, code2, _ in strip_file(ROOT + rel):
                    for mm in re.finditer(r'\((re-find|re-seq|re-matches|re-matcher|str/replace-first|str/replace|str/split)\s+(?:[^()]*\s)?' + re.escape(nm) + r'(?![\w-])', code2):
                        uses.add(mm.group(1))
                    for mm in re.finditer(r'\((re-find|re-seq|re-matches|re-matcher|str/replace-first|str/replace|str/split)\s+' + re.escape(nm) + r'(?![\w-])', code2):
                        uses.add(mm.group(1))
                call = 'def:' + nm + ('->' + '+'.join(sorted(uses)) if uses else '->(no direct re-call found)')
        rows.append((rel.split('/')[-1], rel, ln, call, ','.join(feats), classify(pat, feats, call), pat.replace('\n', '\\n').replace('\t', '\\t')))
    for ln, code, raw in strip_file(ROOT + rel):
        for mm in CALLS.finditer(code):
            callrows.append((rel, ln, mm.group(1) or mm.group(2)))
with open(sys.argv[1], 'w', newline='') as f:
    w = csv.writer(f, delimiter='\t')
    w.writerow(['file', 'path', 'line', 'call', 'features', 'class', 'pattern'])
    w.writerows(rows)
from collections import Counter
print('literals per file:')
c = Counter(r[1] for r in rows)
d = {}
for r in rows:
    d.setdefault(r[1], set()).add(r[6])
cc = Counter((r[1], r[5]) for r in rows)
for rel in FILES:
    print('%-55s lit=%3d distinct=%3d a=%3d b=%3d c=%3d' % (rel, c[rel], len(d.get(rel, ())), cc[(rel, 'a')], cc[(rel, 'b')], cc[(rel, 'c')]))
print('TOTAL lit=%d distinct=%d' % (len(rows), len(set(r[6] for r in rows))))
print('call sites (re-*, str/replace|split):')
cc2 = Counter((r[0], r[2]) for r in callrows)
byf = {}
for (rel, call), n in sorted(cc2.items()):
    byf.setdefault(rel, []).append('%s=%d' % (call, n))
for rel in FILES:
    print(rel, ' '.join(byf.get(rel, [])) or '-')
