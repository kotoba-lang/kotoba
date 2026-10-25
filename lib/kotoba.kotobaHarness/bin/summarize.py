#!/usr/bin/env python3
"""Summarize bench receipts into a markdown table and evidence JSON (no local paths)."""
import json, glob, statistics as st, sys, os
src = sys.argv[1] if len(sys.argv) > 1 else 'runs/bench'
out = sys.argv[2] if len(sys.argv) > 2 else None
rows = [json.load(open(f)) for f in sorted(glob.glob(f'{src}/*/receipt.json'))]
keep = ['project','method','escalate','date','status','error','wall-seconds','api-usd','input-tokens','output-tokens','bodies','source']
evidence = []
for r in rows:
    e = {k: r.get(k) for k in keep}
    e['decisions'] = sum(1 for d in r['decisions'] if d.get('choice'))
    e['escalations'] = sum(1 for d in r['decisions'] if d.get('event') == 'stop-escalation')
    e['verification-failures'] = sum(1 for d in r['decisions'] if d.get('event') == 'verification-failed')
    e['attempts'] = [{'stage': a['stage'], 'bodies': a['bodies'], 'failures': a['verification'].get('failures')} for a in r['attempts']]
    e['choices'] = [d.get('choice') or d.get('event') for d in r['decisions']]
    evidence.append(e)
print('| Wording | Escalation | Project | Passed | Median s | Median API USD | Median in/out tokens | Escalations per run |')
print('|---|---|---|---|--:|--:|--:|---|')
for plain in (False, True):
    for esc in (True, False):
        for p in ('kotoba', 'itonami', 'murakumo'):
            R = [e for e in evidence if e['project'] == (p + '-plain' if plain else p) and e['escalate'] == esc]
            if not R: continue
            ok = sum(e['status'] == 'verified' for e in R)
            med = lambda k: st.median(e[k] for e in R)
            print(f"| {'plain' if plain else 'guided'} | {'on' if esc else 'off'} | {p} | {ok}/{len(R)} | {med('wall-seconds'):.1f} | {med('api-usd'):.6f} | {med('input-tokens'):.0f} / {med('output-tokens'):.0f} | {', '.join(str(e['escalations']) for e in R)} |")
print('\ntotal API USD', round(sum(e['api-usd'] for e in evidence), 9), 'runs', len(evidence))
if out:
    json.dump({'schema': 'kotoba-harness.bench/v1', 'runs': evidence}, open(out, 'w'), indent=2)
