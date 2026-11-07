#!/usr/bin/env python3
"""dxrun.py BIN OFFSET INPUTS VERDICTS: run the guest over INPUTS (one case a line) in batches of <= int(os.environ.get("DX_BATCH", "200000")) bytes;
a batch that traps is rerun one case at a time. Writes '<fn> <verdict>' per input line to VERDICTS."""
import subprocess, sys, os
S = os.path.dirname(os.path.abspath(__file__))
binf, off, inputs, out = sys.argv[1:5]
lines = [l for l in open(inputs, newline='').read().split('\n') if l]
def run(text):
    p = subprocess.run([S + '/run-guest.sh', binf, off], input=text.encode(), capture_output=True)
    return p.returncode, [x for x in p.stdout.decode(errors='replace').split('\n') if x], p.stderr.decode(errors='replace')
verdicts = []
i = 0
while i < len(lines):
    batch, size = [], 0
    while i < len(lines) and size + len(lines[i].encode()) + 1 <= int(os.environ.get("DX_BATCH", "200000")):
        batch.append(lines[i]); size += len(lines[i].encode()) + 1; i += 1
    if not batch:  # one oversized case runs alone
        batch.append(lines[i]); i += 1
    rc, outl, err = run('\n'.join(batch) + '\n')
    if rc == 0 and len(outl) == len(batch):
        verdicts += outl
    else:
        for l in batch:
            rc, o, err = run(l + '\n')
            if rc == 0 and len(o) == 1: verdicts.append(o[0])
            else:
                t = [x for x in err.split('\n') if 'KEXE_TRAP' in x]
                verdicts.append('TRAP ' + (t[0].split(':signal')[-1].strip(' }') if t else str(rc)))
with open(out, 'w') as f:
    for l, v in zip(lines, verdicts):
        f.write(l.split(' ', 1)[0] + ' ' + v + '\n')
