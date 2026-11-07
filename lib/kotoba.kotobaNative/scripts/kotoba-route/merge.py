#!/usr/bin/env python3
"""merge.py HOST TWINS OUT : put Kotoba twins beside the verbatim host definitions.

Every top-level `(defn NAME ..)` / `(defn- NAME ..)` in TWINS whose NAME is a host definition becomes
    #?(:kotoba
       <twin>
       :default
    <host form, verbatim>)
A twin whose name is no host definition is a Kotoba-only helper; it is emitted as `#?(:kotoba <helper>)`
immediately before the next twinned host form (in TWINS order), or after the ns form when none follows.
`(nil-twin A B ..)` in TWINS makes the Kotoba reading of host definitions A B .. empty (`#?(:kotoba nil :default ..)`).
Host `(declare ..)` forms always read as nil on the Kotoba route (top-level declare is not Kotoba).
The ns form gets the :form/r schemas and `kotoba.form` under :kotoba (see NS_SCHEMAS)."""
import re, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from ov import scan

NAME = re.compile(r'^\((defn-?|def|defmacro|declare|nil-twin|folded-twin)\s+(?:\^[^\s]+\s+)*([^\s\[\]()]+)')

NS_SCHEMAS = """  #?(:kotoba (:schemas {:form/r [:record :form/r [[:tag :i64] [:s :string] [:n :i64] [:k :keyword]
                                          [:kids [:list [:ref :form/r]]] [:span :i64] [:data :bytes]]]
                                 :form/rd [:record :form/rd [[:form [:ref :form/r]] [:pos :i64]]]
                                 :mi/lv [:record :mi/lv [[:code [:list [:ref :form/r]]] [:value [:ref :form/r]]
                                                         [:reg :i64] [:label :i64]]]}))
"""

def toplevel(text):
    out = []
    for s, e in scan(text):
        body = text[s:e]
        m = NAME.match(body)
        out.append((s, e, body, m.group(1) if m else None, m.group(2) if m else None))
    return out

def main(host_path, twins_path, out_path):
    host = open(host_path).read()
    twins = open(twins_path).read()
    hforms = toplevel(host)
    hnames = {n for (_, _, _, k, n) in hforms if n and k != 'declare'}
    # twins in order
    twin_of, nil_names, pending, before = {}, set(), [], {}
    trailing = []
    kotoba_exports = None
    folded = set()
    for s, e, body, kind, name in toplevel(twins):
        if body.startswith('(kotoba-exports'):
            kotoba_exports = body[len('(kotoba-exports'):-1].strip()
            continue
        if kind in ('nil-twin', 'folded-twin'):
            for n in body[1:-1].split()[1:]:
                nil_names.add(n)
                if kind == 'folded-twin': folded.add(n)
            continue
        if kind is None:
            raise SystemExit(f"twins: unrecognised top-level form at {twins[:s].count(chr(10))+1}: {body[:60]}")
        # keep the comment block immediately above the twin
        pre = twins[:s]
        cm = re.search(r'((?:[ \t]*;[^\n]*\n)*)\Z', pre)
        comment = cm.group(1) if cm else ''
        if name in hnames:
            if name in twin_of:
                raise SystemExit(f"twins: duplicate twin {name}")
            twin_of[name] = comment + body
            before[name] = pending
            pending = []
        else:
            pending.append(comment + body)
    trailing = pending
    unknown = nil_names - hnames
    if unknown: raise SystemExit(f"nil-twin of unknown host names: {sorted(unknown)}")
    res, pos = [], 0
    ns_done = False
    for s, e, body, kind, name in hforms:
        res.append(host[pos:s])
        pos = e
        if body.startswith('(ns ') and not ns_done:
            ns_done = True
            b = body
            i = b.index('(:require')
            b = b[:i] + NS_SCHEMAS.lstrip() + '  ' + b[i:]
            b = b.replace('(:require ', '(:require #?@(:kotoba [[kotoba.form :as form]])\n            ', 1)
            if kotoba_exports:
                m = re.search(r':kotoba/export\s*(\[[^\]]*\])', b)
                b = b[:m.start(1)] + '#?(:kotoba ' + kotoba_exports + ' :default ' + m.group(1) + ')' + b[m.end(1):]
            res.append(b)
            if trailing and False: pass
            continue
        if kind == 'declare':
            res.append(f"#?(:kotoba nil :default {body})")
            continue
        if name in twin_of:
            for h in before[name]:
                res.append('#?(:kotoba\n' + indent(h) + ')\n\n')
            res.append('#?(:kotoba\n' + indent(twin_of[name]) + '\n   :default\n' + body + ')')
        elif name in folded:
            res.append(f"#?(:kotoba nil ;; folded into the Kotoba twins under another name\n   :default\n{body})")
        elif name in nil_names:
            res.append(f"#?(:kotoba nil :default\n{body})")
        else:
            res.append(body)
    res.append(host[pos:])
    if trailing:
        res.append('\n' + ''.join('#?(:kotoba\n' + indent(h) + ')\n\n' for h in trailing))
    open(out_path, 'w').write(''.join(res))

def indent(t):
    return '\n'.join(('   ' + l) if l.strip() else l for l in t.strip('\n').split('\n'))

if __name__ == '__main__':
    main(*sys.argv[1:4])
