#!/usr/bin/env python3
"""scripts/gen-table-lookups.py -- generate allocation-free membership tests for the frontend's symbol tables
(agent ARENA, 2026-10-04). Rewrites the generated block at the end of src/kotoba/compiler/frontend_tables.cljk and
the `:kotoba/export` list there; run from the repository root, commit the result. Idempotent.

Why. On the Kotoba route every table is a zero-argument function that re-parses its printed EDN (`form/edn-form`), so
`(table-has? (arithmetic) op)` builds the whole table -- one Form record per entry -- on EVERY lookup. Measured on the
native analyze (amu-front, census of the seed's 00-ns..02-io prefix): reading tables is ~68% of all pair handles and
~54% of vector handles, most of it the per-definition `reserved-function-names` union of 45 tables.

What. For every Kotoba table whose members (a set) or keys (a map) are all plain symbols, two functions:
  NAME-has-name? [s :string] :bool          s is a member / key; dispatch on (byte length, first code point), then
                                           string=? against the few candidates; no allocation (string literals are
                                           interned pairs under the loader's hash-consing)
  NAME-has? [k [:ref :form/r]] :bool        (table-has? (NAME) k) for any Form k: a symbol whose name is a member
The host (:default) gets NAME-has? as (table-has? NAME k) and no NAME-has-name?.
Equality is form/eq's for symbols (string=? of the name), so the answers are those of table-has? on the built table.
"""
import re
import sys

PATH = 'src/kotoba/compiler/frontend_tables.cljk'
BEGIN = ';; ---- generated lookups (scripts/gen-table-lookups.py; do not edit by hand) BEGIN'
END = ';; ---- generated lookups END'


def tokens(t):
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c in ' \n\t,':
            i += 1
        elif t.startswith('#{', i):
            yield ('open', '#{'); i += 2
        elif c in '{[(':
            yield ('open', c); i += 1
        elif c in '}])':
            yield ('close', c); i += 1
        elif c == '"':
            j = i + 1
            while t[j] != '"':
                j += 2 if t[j] == '\\' else 1
            yield ('str', t[i:j + 1]); i = j + 1
        else:
            j = i
            while j < n and t[j] not in ' \n\t,{}[]()"':
                j += 1
            yield ('atom', t[i:j]); i = j


def top_items(t):
    """kind ('set'|'map'|'other') and the top-level items as ('atom', text) or ('coll', None)"""
    ts = list(tokens(t))
    if not ts or ts[0][0] != 'open' or ts[0][1] not in ('#{', '{'):
        return 'other', []
    kind = 'set' if ts[0][1] == '#{' else 'map'
    items, depth = [], 0
    for k, v in ts[1:-1]:
        if k == 'open':
            if depth == 0:
                items.append(('coll', None))
            depth += 1
        elif k == 'close':
            depth -= 1
        elif depth == 0:
            items.append((k, v))
    return kind, items


def is_symbol(tok):
    k, v = tok
    if k != 'atom':
        return False
    if v[0] == ':' or re.fullmatch(r'-?\d+', v) or v in ('nil', 'true', 'false'):
        return False
    return True


def names_of(t):
    kind, items = top_items(t)
    if kind == 'set':
        keys = items
    elif kind == 'map':
        if len(items) % 2:
            return None
        keys = items[0::2]
    else:
        return None
    if not keys or not all(is_symbol(x) for x in keys):
        return None
    out = []
    for _, v in keys:
        if v not in out:
            out.append(v)
    return out


def lit(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def has_name_fn(name, names):
    groups = {}
    for s in names:
        b = s.encode('utf-8')
        key = len(b) * 1024 + ord(s[0])
        groups.setdefault(key, []).append(s)
    clauses = []
    for key in sorted(groups):
        ss = groups[key]
        test = ('(string=? s %s)' % lit(ss[0])) if len(ss) == 1 else \
            '(or ' + ' '.join('(string=? s %s)' % lit(x) for x in ss) + ')'
        clauses.append('             (= h %d) %s' % (key, test))
    return ('#?(:kotoba\n'
            '   (defn %s-has-name? [s :string] :bool\n'
            '     (let [n (string-byte-length s)]\n'
            '       (if (= n 0)\n'
            '         false\n'
            '         (let [h (+ (* n 1024) (string-code-point-at s 0))]\n'
            '           (cond\n%s\n'
            '             :else false)))))\n'
            '   :default nil)\n') % (name, '\n'.join(clauses))


def has_fn(name):
    return ('#?(:kotoba\n'
            '   (defn %s-has? [k [:ref :form/r]] :bool\n'
            '     (if (form/is-symbol? k) (%s-has-name? (form/symbol-value k)) false))\n'
            '   :default\n'
            '   (defn %s-has? [k] (table-has? %s k)))\n') % (name, name, name, name)


def main():
    s = open(PATH).read()
    if BEGIN in s:
        s = s[:s.index(BEGIN)].rstrip('\n') + '\n'
    tables = re.findall(r'\(defn ([a-z0-9?!>-]+) \[\] \[:ref :form/r\]\s*\(form/edn-form "((?:[^"\\]|\\.)*)"\)\)', s)
    gen, made = [], []
    for name, text in tables:
        text = text.encode().decode('unicode_escape') if '\\' in text else text
        names = names_of(text)
        if names is None:
            continue
        made.append(name)
        gen.append(has_name_fn(name, names))
        gen.append(has_fn(name))
    block = '\n' + BEGIN + '\n;; ' + str(len(made)) + ' symbol tables\n\n' + '\n'.join(gen) + END + '\n'
    s = s + block
    m = re.search(r'\{:kotoba/export \[([^\]]*)\]\}', s)
    new = [n + '-has?' for n in made] + [n + '-has-name?' for n in made]
    ex = [x for x in m.group(1).split() if x not in new] + new
    s = s[:m.start(1)] + ' '.join(ex) + s[m.end(1):]
    open(PATH, 'w').write(s)
    print('generated %d symbol tables: %s' % (len(made), ' '.join(made)))


if __name__ == '__main__':
    main()
