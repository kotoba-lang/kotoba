#!/usr/bin/env python3
"""Stage a test-only native comparison from actual Amu receipt/v2 corpus bytes.

This is a deliberately limited data adapter, not VM admission or evaluation.
It decodes test inputs for const/binary add/sub/mul/div/mod/if only; the native Kotoba
reference computes results and compares actual AOT observations. Unsupported
cases are skipped, never claimed. Run only on trusted local test artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Unsupported(Exception):
    pass


def decode(data):
    pos = 0

    def item(depth):
        nonlocal pos
        if depth > 64 or pos >= len(data):
            raise ValueError('CBOR truncated or too deep')
        first = data[pos]; pos += 1
        major, width = first >> 5, first & 31
        if width < 24:
            n = width
        elif width in (24, 25, 26, 27):
            size = 1 << (width - 24)
            if pos + size > len(data):
                raise ValueError('CBOR length truncated')
            n = int.from_bytes(data[pos:pos + size], 'big'); pos += size
        else:
            raise Unsupported('indefinite or unsupported CBOR')
        if major == 0:
            return n
        if major == 1:
            return -1 - n
        if major == 3:
            if n > len(data) - pos:
                raise ValueError('CBOR text truncated')
            text = data[pos:pos + n].decode('utf-8'); pos += n
            return text
        if major == 4:
            if n > 4096:
                raise Unsupported('array too large')
            return [item(depth + 1) for _ in range(n)]
        if major == 5:
            if n > 4096:
                raise Unsupported('map too large')
            result = {}
            for _ in range(n):
                key, value = item(depth + 1), item(depth + 1)
                if not isinstance(key, str) or key in result:
                    raise ValueError('non-text or duplicate key')
                result[key] = value
            return result
        if major == 7 and width == 22:
            return None
        raise Unsupported('unsupported CBOR major type')

    value = item(0)
    if pos != len(data):
        raise ValueError('trailing bytes')
    return value


def tree(program):
    try:
        if not isinstance(program, list) or len(program) != 3 or program[:2] != ['kototama.vm/program', 1]:
            raise Unsupported('not a program')
        p = program[2]; entry = p['entry']; method = p['methods'][entry]
        if method['params'] or method['effects']:
            raise Unsupported('entry parameters or effects')
        root = method['body']; nodes = []

        def emit(expr):
            if len(nodes) >= 63 or not isinstance(expr, list):
                raise Unsupported('tree too large or invalid')
            index = len(nodes); nodes.append(None)
            if (len(expr) == 2 and expr[0] == 'const' and isinstance(expr[1], list)
                    and len(expr[1]) == 2 and expr[1][0] == 'integer'):
                text = expr[1][1]
                if not isinstance(text, str):
                    raise Unsupported('integer is not text')
                n = int(text)
                if str(n) != text or not -(1 << 63) <= n < (1 << 63):
                    raise Unsupported('integer not canonical i64')
                nodes[index] = [0, 0, 0, n]
            elif (len(expr) == 3 and expr[0] == 'arith' and expr[1] in ('add', 'sub', 'mul', 'div', 'quot', 'mod')
                  and isinstance(expr[2], list) and len(expr[2]) == 2):
                left, right = emit(expr[2][0]), emit(expr[2][1])
                nodes[index] = [{'add': 1, 'div': 2, 'quot': 2, 'sub': 4, 'mul': 5, 'mod': 6}[expr[1]], left, right, 0]
            elif len(expr) == 4 and expr[0] == 'if':
                condition, yes, no = emit(expr[1]), emit(expr[2]), emit(expr[3])
                nodes[index] = [3, condition, yes, no]
            else:
                raise Unsupported('outside model')
            return index

        emit(root)
        return [value for node in nodes for value in node]
    except (KeyError, TypeError, ValueError, IndexError, RecursionError) as exc:
        raise Unsupported('outside model') from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt-dir', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    corpus = a.receipt_dir.resolve(strict=True)
    report_bytes = (corpus / 'report.json').read_bytes()
    report = json.loads(report_bytes)
    if report.get('status') != 'PASS' or report.get('profile') != 'kototama.pure-i64-receipt/v2':
        raise ValueError('receipt corpus is not a passing v2 observation')
    rows = []
    for record in report['cases']:
        if record['compileExit'] != 0 or record['outputBytes'] != 64:
            continue
        i = record['index']
        if type(i) is not int or not 0 <= i <= 999999:
            raise ValueError('invalid index')
        raw = (corpus / f'{i:03d}.cbor').read_bytes()
        if sha(raw) != record['inputSHA256']:
            raise ValueError('program digest mismatch')
        try:
            nodes = tree(decode(raw))
        except Unsupported:
            continue
        receipt = (corpus / f'{i:03d}-guest.stdout').read_bytes()
        if len(receipt) != 64:
            raise ValueError('invalid receipt size')
        words = struct.unpack('<8q', receipt)
        if list(words) != record['receipt'] or words[0] != 0x003252343649544b:
            raise ValueError('receipt observation mismatch')
        budget = record['budget']
        if type(budget) is not int or budget != words[3] or words[1] not in (0, 1, 2, 3):
            raise ValueError('invalid observed context')
        rows.append((i, nodes, budget, words[1], words[2], words[4]))
    if not rows:
        raise ValueError('no comparable observations')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    source = out / 'reference.kotoba'; gate = out / 'gate.kotoba'
    shutil.copyfile(a.reference, source)
    parts = ['(ns gate (:export [main]) (:require [reference :as r]))\n',
             '(defn- is [a :vector-i64 s :i64 v :i64 f :i64] :bool '
             '(and (= (vector-at a 0) s) (= (vector-at a 1) v) (= (vector-at a 2) f)))\n']
    for start in range(0, len(rows), 8):
        terms = []
        for _, nodes, budget, status, value, spent in rows[start:start + 8]:
            vec = '[' + ' '.join(map(str, nodes)) + ']'
            call = f'(r/evaluate {vec} {budget})'
            terms.append(f'(is {call} {status} {value} {spent})')
            terms.append(f'(not (is {call} {(status + 1) % 4} {value} {spent}))')
        parts.append(f'(defn- group-{start // 8} [] :bool (and ' + ' '.join(terms) + '))\n')
    groups = ' '.join(f'(group-{i})' for i in range((len(rows) + 7) // 8))
    parts.append(f'(defn main [] :i64 (if (and {groups}) 42 0))\n')
    gate.write_text(''.join(parts))
    lock = out / 'project.ksl'
    lock.write_text(f'KSL2\nentry {gate}\nmodule gate {gate}\nmodule reference {source}\n'
                    f'file {sha(gate.read_bytes())} {gate}\nfile {sha(source.read_bytes())} {source}\n')
    manifest = {'schema': 'kototama.experimental-reference-comparison.v1', 'caseCount': len(rows),
                'indices': [row[0] for row in rows], 'reportSha256': sha(report_bytes),
                'referenceSha256': sha(source.read_bytes()), 'gateSha256': sha(gate.read_bytes()),
                'lockSha256': sha(lock.read_bytes()), 'sameCanonicalInputDecodedByNativeReference': False,
                'wholeVmQualified': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('staged', len(rows), 'actual receipt observations')


if __name__ == '__main__':
    main()
