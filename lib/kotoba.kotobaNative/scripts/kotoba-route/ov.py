#!/usr/bin/env python3
"""Overlay + ledger for the machine_ir / aarch64 port.

  ov.py ledger FILE...         per-file ledger: top-level definitions, with a real Kotoba body, refusal twin, host-only
  ov.py rows FILE...           one TSV row per definition (module, name, host-lines, status)
  ov.py overlay FILE OUT       write OUT: FILE with every host-only definition hidden from the Kotoba reading
                               (exported names get a refusal stub), so `amu check` reaches the ported code.

A definition's status:
  real      the top-level form is `#?(:kotoba <typed defn> ...)` and the defn is not a refusal twin
  twin      Kotoba reading is a refusal (`(deferred! ...)` body) or `nil` (host-only by design, counted apart)
  host      the Kotoba reading is the host text (untyped): not ported
"""
import re, sys

def scan(text):
    """yield (start, end, prefix) of top-level forms; prefix is '#?' for a reader conditional"""
    i, n, depth, start = 0, len(text), 0, None
    while i < n:
        c = text[i]
        if c == ';':
            while i < n and text[i] != '\n': i += 1
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\': i += 1
                i += 1
            i += 1; continue
        if c == '\\' and depth > 0:
            m = re.match(r'\\(newline|space|tab|return|formfeed|backspace|u[0-9a-fA-F]{4}|o[0-7]{1,3}|.)', text[i:])
            i += len(m.group(0)); continue
        if c in '([{':
            if depth == 0:
                start = i
                if text[i-2:i] == '#?': start = i - 2
                elif text[i-3:i] == '#?@': start = i - 3
                elif text[i-1:i] == '#': start = i - 1
            depth += 1
        elif c in ')]}':
            depth -= 1
            if depth == 0:
                yield start, i + 1
        i += 1

NAME = re.compile(r'\((defn-?|def|defmacro|declare)\s+(?:\^[^\s]+\s+)*([^\s\[\]()]+)')

def items(path):
    text = open(path).read()
    out = []
    for s, e in scan(text):
        body = text[s:e]
        if body.startswith('(ns '): continue
        m = NAME.search(body)
        if not m: continue
        kind, name = m.group(1), m.group(2)
        line = text.count('\n', 0, s) + 1
        nlines = body.count('\n') + 1
        if kind == 'declare':
            status = 'declare'
        elif body.startswith('#?(:kotoba'):
            arm = body[len('#?(:kotoba'):].lstrip()
            if not re.search(r'\n\s*:default\s*\n', body) and not arm.startswith('nil'):
                status = 'helper'
            elif arm.startswith('nil ;; folded'):
                status = 'folded'
            elif arm.startswith('nil'):
                status = 'nil'
            elif '(deferred! ' in body.split(':default')[0]:
                status = 'twin'
            else:
                status = 'real'
        else:
            status = 'host'
        out.append(dict(name=name, kind=kind, s=s, e=e, line=line, lines=nlines, status=status, body=body))
    return text, out

def exports(text):
    m = re.search(r':kotoba/export\s*\[([^\]]*)\]', text)
    return set(m.group(1).split()) if m else set()

def ledger(paths):
    for p in paths:
        text, its = items(p)
        defs = [x for x in its if x['status'] not in ('declare', 'helper')]
        helpers = [x for x in its if x['status'] == 'helper']
        names = {}
        for x in defs: names.setdefault(x['name'], []).append(x)
        st = lambda k: [x for x in defs if x['status'] == k]
        real, twin, nil, host, folded = st('real'), st('twin'), st('nil'), st('host'), st('folded')
        hl = lambda xs: sum(x['lines'] for x in xs)
        print(f"{p}\n  definitions {len(defs)} ({hl(defs)} lines): real {len(real)} ({hl(real)}), "
              f"folded {len(folded)} ({hl(folded)}), deferred-nil {len(nil)} ({hl(nil)}), host-only {len(host)} ({hl(host)}); "
              f"Kotoba-only helpers {len(helpers)}")

def rows(paths):
    for p in paths:
        mod = p.split('/src/')[-1]
        text, its = items(p)
        for x in its:
            if x['status'] in ('declare', 'helper'): continue
            print(f"{mod}\t{x['name']}\t{x['line']}\t{x['lines']}\t{x['status']}")

def overlay(path, out):
    text, its = items(path)
    ex = exports(text)
    res, pos = [], 0
    for x in its:
        if x['status'] not in ('host',) and not (x['status'] == 'declare' and not x['body'].startswith('#?')): continue
        res.append(text[pos:x['s']])
        if x['name'] in ex and x['status'] != 'declare':
            stub = f"(defn {x['name']} [] :i64 0)"
        else:
            stub = "nil"
        res.append(f"#?(:kotoba {stub} :default {x['body']})")
        pos = x['e']
    res.append(text[pos:])
    open(out, 'w').write(''.join(res))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'ledger': ledger(sys.argv[2:])
    elif cmd == 'rows': rows(sys.argv[2:])
    elif cmd == 'overlay': overlay(sys.argv[2], sys.argv[3])
