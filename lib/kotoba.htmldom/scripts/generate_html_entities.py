#!/usr/bin/env python3
"""Regenerate static lookup data from the pinned WHATWG table; not a build step."""
from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parents[1]
raw = (root / 'data/whatwg-entities.json').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'd741d877ac77c4194c4ad526b5b4a19aef8dfe411ab840a466891cdbb9f362e6'
rows = json.loads(raw)
assert len(rows) == 2231
entries = []
for key, value in sorted(rows.items()):
    name = key.removeprefix('&')
    cps = value['codepoints']
    assert key.startswith('&') and len(name) <= 32 and name.isascii() and 1 <= len(cps) <= 2
    assert all(c.isalnum() or c == ';' for c in name) and name.count(';') <= 1
    assert ';' not in name or name.endswith(';')
    assert name.endswith(';') or rows[key + ';']['codepoints'] == cps
    assert all(0 < cp <= 0x10ffff and not 0xd800 <= cp <= 0xdfff for cp in cps)
    assert ''.join(chr(cp) for cp in cps) == value['characters']
    entries.append(name.ljust(32) + ''.join(f'{cp:06x}' for cp in (cps + [0])[:2]))
assert all(len(x) == 44 for x in entries)
chunks = [''.join(entries[i:i + 300]) for i in range(0, len(entries), 300)]
source = (';; Generated from the pinned WHATWG entities JSON; see data/whatwg-entities.json.\n'
          ';; 44-byte rows: name(32, space padded), first and second code point(6 hex each).\n'
          '(ns html-entities-data (:export [entry-count chunk]))\n'
          '(defn entry-count [] :i64 2231)\n'
          '(defn chunk [index :i64] :string\n  (cond\n' +
          ''.join(f'    (= index {i}) "{part}"\n' for i, part in enumerate(chunks)) +
          '    :else ""))\n')
out = root / 'kotoba/html_entities_data.kotoba'
if '--check' in sys.argv:
    assert out.read_text() == source
    print('PASS_ENTITY_SOURCE_PIN')
else:
    out.write_text(source)
