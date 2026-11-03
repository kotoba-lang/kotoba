#!/usr/bin/env python3
"""Inventory the AIUEOS kernel's remaining C/asm against Amu's kernel intrinsics (JUN-597).

Reads the 18 kernel files named by JUN-552 at the checked-out revision and the kernel
intrinsic names that an Amu checkout's seed declares, and writes:

  OUT.json  every C function / asm global symbol with its line range, the inline-asm and
            .S instruction mnemonics it uses, the Kotoba-emitted objects it calls
            (kotoba_aiueos_*), the privileged helpers it calls, and a heuristic class
  OUT.md    per-file counts, the instruction -> intrinsic gap matrix, the asm entry
            symbols and the per-function list

This is a source inventory, not a build, QEMU or hardware observation. The class is a
heuristic from the text (see CLASSES); a reviewer decides the real migration step.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

FILES = ['main.c', 'entry.S', 'qualification.c', 'qualification_entry.S', 'ap_trampoline.S',
         'paging.c', 'memory.c', 'acpi.c', 'apic.c', 'ioapic.c', 'smp.c', 'vtd.c', 'pci.c',
         'framebuffer.c', 'syscall.c', 'process.c', 'scheduler.c', 'loader.c']

CLASSES = {
    'kotoba-glue': 'calls a Kotoba-emitted object and uses no inline asm itself',
    'needs-intrinsic': 'uses inline asm directly; every mnemonic has an Amu kernel intrinsic',
    'unresolved-instruction': 'uses inline asm with at least one mnemonic that has no Amu kernel intrinsic',
    'privileged-via-helper': 'no asm of its own, but calls a C helper that uses inline asm',
    'c-logic': 'plain C: no asm, no Kotoba object call, no privileged helper',
    'asm-entry': 'a .S global symbol (entry, stub or trampoline code)',
}

# mnemonic (without size suffix where the intrinsic family covers widths) -> intrinsics
INTRINSIC_FOR = {
    'in': ['kernel-in-u8', 'kernel-in-u16', 'kernel-in-u32'],
    'out': ['kernel-out-u8', 'kernel-out-u16', 'kernel-out-u32'],
    'rdmsr': ['kernel-read-msr'], 'wrmsr': ['kernel-write-msr'],
    'mov-cr0': ['kernel-read-cr0', 'kernel-write-cr0'], 'mov-cr2': ['kernel-read-cr2'],
    'mov-cr3': ['kernel-read-cr3', 'kernel-write-cr3'], 'mov-cr4': ['kernel-read-cr4', 'kernel-write-cr4'],
    'invlpg': ['kernel-invlpg'], 'lidt': ['kernel-load-idt'], 'cli': ['kernel-cli'], 'sti': ['kernel-sti'],
    'hlt': ['kernel-hlt'], 'pause': ['kernel-pause'], 'rdtsc': ['kernel-rdtsc'], 'rdrand': ['kernel-rdrand'],
    'rdseed': ['kernel-rdseed'], 'cpuid': ['kernel-cpuid-eax', 'kernel-cpuid-ebx', 'kernel-cpuid-ecx', 'kernel-cpuid-edx'],
    'xgetbv': ['kernel-xgetbv'], 'xsetbv': ['kernel-xsetbv'], 'int3': ['kernel-debug-break'],
    'mov-cs': ['kernel-read-cs'],
}
SUFFIXED = {'inb': 'in', 'inw': 'in', 'inl': 'in', 'outb': 'out', 'outw': 'out', 'outl': 'out',
            'rdtscp': 'rdtscp', 'invlpga': 'invlpga'}
# plain data-movement / arithmetic / control-flow mnemonics are ordinary codegen, not intrinsics
ORDINARY = set('''mov movq movl movw movb movabs movabsq movzx movzbl movzwl movsx lea leaq push pushq pop popq
add addq addl sub subq subl and andq andl or orq orl xor xorq xorl not neg inc incq dec decq shl shlq shr shrq sar
sal rol ror cmp cmpq cmpl cmpb test testq testl testb jmp jz jnz je jne jb jbe ja jae jl jle jg jge js jns jc jnc
call callq ret retq nop imul mul div idiv cqo cdq cdqe xchg bt bts btr bsf bsr sete setne cmove cmovne
rep stosb stosq movsb movsq lods lodsb lodsq'''.split())

def strip_comments(text):
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith('/*', i):
            j = text.find('*/', i + 2); j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', text[i:j])); i = j
        elif text.startswith('//', i):
            j = text.find('\n', i); j = n if j < 0 else j
            out.append(' ' * (j - i)); i = j
        elif text[i] in '"\'':
            q = text[i]; j = i + 1
            while j < n and text[j] != q:
                j += 2 if text[j] == '\\' else 1
            out.append(text[i:j + 1]); i = j + 1
        else:
            out.append(text[i]); i += 1
    return ''.join(out)

def mnemonics(asm_text):
    found = []
    for piece in re.split(r'[;\n]|\\n|\\t', asm_text):
        piece = re.sub(r'^\s*[\w.$]+:\s*', '', piece.strip())
        if not piece or '\\' in piece or piece.startswith(('.', '#', '%', '"')) or not re.match(r'[a-z]', piece):
            continue
        tokens = piece.split()
        if not tokens:
            continue
        op = tokens[0].lower()
        if op in ('lock', 'rep', 'repe', 'repne') and len(tokens) > 1:
            op = op + ' ' + tokens[1].lower()
        rest = ' '.join(tokens[1:]).lower()
        if op.startswith('mov') and re.search(r'%?cr[0-8]', rest):
            op = 'mov-' + re.search(r'cr[0-8]', rest)[0]
        elif op.startswith('mov') and re.search(r'%cs\b', rest):
            op = 'mov-cs'
        found.append(SUFFIXED.get(op, op))
    return found

def c_functions(path):
    raw = path.read_text(errors='replace')
    text = strip_comments(raw)
    lines = text.count('\n')
    funcs, depth, i, n = [], 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch in '"\'':
            q = ch; i += 1
            while i < n and text[i] != q:
                i += 2 if text[i] == '\\' else 1
        elif ch == '{':
            if depth == 0:
                head = text[max(0, i - 600):i]
                head = re.sub(r'__attribute__\s*\(\((?:[^()]|\([^()]*\))*\)\)', lambda x: ' ' * len(x[0]), head)
                m = re.search(r'\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*$', head)
                if m and m[1] not in ('if', 'for', 'while', 'switch', 'sizeof', 'return'):
                    start = i; d = 0; j = i
                    while j < n:
                        if text[j] in '"\'':
                            q = text[j]; j += 1
                            while j < n and text[j] != q:
                                j += 2 if text[j] == '\\' else 1
                        elif text[j] == '{':
                            d += 1
                        elif text[j] == '}':
                            d -= 1
                            if d == 0:
                                break
                        j += 1
                    body = text[start:j + 1]
                    first = text.count('\n', 0, i - len(head) + m.start()) + 1
                    funcs.append(dict(name=m[1], first=first, last=text.count('\n', 0, j) + 1,
                                      static=bool(re.search(r'\bstatic\b[^;{}]*$', head[:m.start()].split(';')[-1].split('}')[-1])),
                                      body=body))
                    i = j + 1
                    continue
            depth += 1
        elif ch == '}':
            depth = max(0, depth - 1)
        i += 1
    return funcs, lines

def asm_symbols(path):
    lines = re.sub(r'/\*.*?\*/', lambda m: re.sub(r'[^\n]', ' ', m[0]), path.read_text(errors='replace'), flags=re.S).splitlines()
    globals_ = set()
    for ln in lines:
        m = re.match(r'\s*\.glob[a]?l\s+([\w.$]+)', ln)
        if m:
            globals_.update(s.strip() for s in m[1].split(','))
    syms, cur = [], None
    for k, ln in enumerate(lines, 1):
        code = re.split(r'#|//|;\s*$', ln)[0]
        m = re.match(r'\s*([A-Za-z_.$][\w.$]*):', code)
        if m and m[1] in globals_:
            cur = dict(name=m[1], first=k, last=k, mnemonics=[]); syms.append(cur)
            code = code[m.end():]
        if cur is not None:
            cur['last'] = k
            cur['mnemonics'] += mnemonics(code)
    return syms, len(lines)

def intrinsics(amu, rev):
    out = subprocess.run(['git', '-C', str(amu), 'grep', '-h', '-o', '-I', r'"kernel-[a-z0-9!?-]*"', rev, '--', 'seed/*.kotoba'],
                         capture_output=True, text=True, check=True).stdout
    return sorted({s.strip('"') for s in out.split()} - {'kernel-load-', 'kernel-store-'})

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--amu', type=Path, required=True, help='an Amu checkout')
    p.add_argument('--amu-rev', required=True)
    p.add_argument('--out', type=Path, required=True, help='output stem (writes .json and .md)')
    a = p.parse_args()
    kernel_rev = subprocess.run(['git', '-C', str(a.kernel), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    amu_rev = subprocess.run(['git', '-C', str(a.amu), 'rev-parse', a.amu_rev], capture_output=True, text=True, check=True).stdout.strip()
    have = intrinsics(a.amu, amu_rev)
    files, entries = [], []
    asm_using = {}
    for name in FILES:
        path = a.kernel / name
        data = path.read_bytes()
        rec = dict(file=name, sha256=hashlib.sha256(data).hexdigest(), lines=data.count(b'\n'))
        if name.endswith('.S'):
            syms, _ = asm_symbols(path)
            for s in syms:
                entries.append(dict(file=name, kind='asm', name=s['name'], first=s['first'], last=s['last'],
                                    mnemonics=sorted(set(s['mnemonics'])), kotoba_calls=[], helper_calls=[]))
        else:
            funcs, _ = c_functions(path)
            for f in funcs:
                body = f['body']
                templates = []
                for m in re.finditer(r'\b(?:__asm__|asm)\s*(?:__volatile__|volatile)?\s*(?:goto)?\s*\(((?:"(?:[^"\\]|\\.)*"\s*)+)', body):
                    before = re.split(r'[;{}]', body[max(0, m.start() - 120):m.start()])[-1]
                    if re.search(r'\bregister\b', before) or re.search(r'\w\s*$', before):
                        continue  # a register variable's asm("reg"), not an instruction template
                    templates.append('\n'.join(re.findall(r'"((?:[^"\\]|\\.)*)"', m[1])))
                ms = mnemonics('\n'.join(templates))
                e = dict(file=name, kind='c', name=f['name'], first=f['first'], last=f['last'], static=f['static'],
                         mnemonics=sorted(set(ms)), volatile_access=bool(re.search(r'\bvolatile\b', body.replace('__volatile__', ''))),
                         kotoba_calls=sorted(set(re.findall(r'\b(kotoba_aiueos_\w+)\s*\(', body))),
                         calls=sorted(set(re.findall(r'\b([A-Za-z_]\w*)\s*\(', body))))
                entries.append(e)
                if ms:
                    asm_using[f['name']] = e
        files.append(rec)
    for e in entries:
        if e['kind'] == 'c':
            e['helper_calls'] = sorted(c for c in e.pop('calls') if c in asm_using and c != e['name'])
    def missing(ms):
        return [m for m in ms if m not in ORDINARY and not (INTRINSIC_FOR.get(m) and all(x in have for x in INTRINSIC_FOR[m]))]
    for e in entries:
        if e['kind'] == 'asm':
            e['class'] = 'asm-entry'
        elif e['mnemonics']:
            e['class'] = 'unresolved-instruction' if missing(e['mnemonics']) else 'needs-intrinsic'
        elif e['kotoba_calls']:
            e['class'] = 'kotoba-glue'
        elif e['helper_calls']:
            e['class'] = 'privileged-via-helper'
        else:
            e['class'] = 'c-logic'
        e['unmatched_mnemonics'] = missing(e['mnemonics'])
    matrix = {}
    for e in entries:
        for m in e['mnemonics']:
            if m in ORDINARY:
                continue
            row = matrix.setdefault(m, dict(mnemonic=m, intrinsics=INTRINSIC_FOR.get(m, []), uses=[]))
            row['uses'].append(f"{e['file']}:{e['name']}")
    for row in matrix.values():
        row['present'] = bool(row['intrinsics']) and all(x in have for x in row['intrinsics'])
    receipt = dict(schema='aiueos.kernel-c-inventory.v1', issue='JUN-597', kotoba_revision=kernel_rev,
                   amu_revision=amu_rev, amu_kernel_intrinsics=have, classes=CLASSES, files=files,
                   matrix=sorted(matrix.values(), key=lambda r: (r['present'], r['mnemonic'])), entries=entries,
                   scope='source text inventory; no build, QEMU or hardware observation; classes are heuristics')
    a.out.with_suffix('.json').write_text(json.dumps(receipt, indent=1) + '\n')
    a.out.with_suffix('.md').write_text(render(receipt) + '\n')
    counts = {c: sum(1 for e in entries if e['class'] == c) for c in CLASSES}
    print(json.dumps(dict(entries=len(entries), **counts)))

def render(r):
    out = ['# AIUEOS kernel C/asm inventory (JUN-597)', '',
           f"Generated by `tools/kernel_c_inventory.py` from kotoba `{r['kotoba_revision'][:12]}` and Amu `{r['amu_revision'][:12]}`. "
           'This is a source-text inventory: nothing here was built, run in QEMU or measured on hardware. '
           'The class of each function is a heuristic from its text; the JSON receipt beside this file has every field.', '',
           '## Classes', '']
    out += [f'- `{k}`: {v}.' for k, v in r['classes'].items()]
    out += ['', '## Per file', '', '| file | lines | ' + ' | '.join(r['classes']) + ' |', '|---|---|' + '---|' * len(r['classes'])]
    for f in r['files']:
        es = [e for e in r['entries'] if e['file'] == f['file']]
        out.append(f"| `{f['file']}` | {f['lines']} | " + ' | '.join(str(sum(1 for e in es if e['class'] == c)) for c in r['classes']) + ' |')
    out += ['', '## Instruction to intrinsic matrix', '',
            'Every non-ordinary mnemonic found in inline asm or `.S`, the Amu kernel intrinsics that would replace it, and whether all of them exist at the pinned Amu revision. A mnemonic with no intrinsic is a gap; whether it needs a new intrinsic or a different design is a decision for JUN-598 to JUN-600.', '',
            '| mnemonic | intrinsic(s) | present | used in |', '|---|---|---|---|']
    for row in r['matrix']:
        uses = sorted(set(row['uses']))
        shown = ', '.join(f'`{u}`' for u in uses[:6]) + (f' and {len(uses) - 6} more' if len(uses) > 6 else '')
        out.append(f"| `{row['mnemonic']}` | {', '.join(f'`{x}`' for x in row['intrinsics']) or '(none)'} | {'yes' if row['present'] else '**no**'} | {shown} |")
    out += ['', '## Asm entry symbols', '', '| file | symbol | lines | mnemonics |', '|---|---|---|---|']
    for e in r['entries']:
        if e['kind'] == 'asm':
            ms = [m for m in e['mnemonics'] if m not in ORDINARY]
            out.append(f"| `{e['file']}` | `{e['name']}` | {e['first']}-{e['last']} | {', '.join(f'`{m}`' for m in ms) or '(ordinary only)'} |")
    out += ['', '## Functions', '']
    for f in r['files']:
        es = [e for e in r['entries'] if e['file'] == f['file'] and e['kind'] == 'c']
        if not es:
            continue
        out += [f"### `{f['file']}` ({len(es)} functions)", '', '| function | lines | class | detail |', '|---|---|---|---|']
        for e in es:
            detail = []
            if e['kotoba_calls']:
                detail.append('Kotoba: ' + ', '.join(f'`{k}`' for k in e['kotoba_calls']))
            ms = [m for m in e['mnemonics'] if m not in ORDINARY]
            if ms:
                detail.append('asm: ' + ', '.join(f'`{m}`' for m in ms))
            if e['helper_calls']:
                detail.append('via: ' + ', '.join(f'`{h}`' for h in e['helper_calls'][:4]))
            if e.get('volatile_access') and not ms:
                detail.append('volatile access')
            out.append(f"| `{e['name']}` | {e['first']}-{e['last']} | {e['class']} | {'; '.join(detail)} |")
        out.append('')
    return '\n'.join(out)

if __name__ == '__main__':
    main()
