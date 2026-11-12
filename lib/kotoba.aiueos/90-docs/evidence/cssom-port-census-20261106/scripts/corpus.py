#!/usr/bin/env python3
"""Numeric-literal census over CSS text in the conformance corpus and tests. usage: corpus.py OUT.json"""
import os, re, sys, json, collections
ROOT=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../..')) + '/' + 'kotoba.cssom/'
SRC=[ROOT+'conformance/cases.edn', ROOT+'test/cssom/layout_test.cljk', ROOT+'test/cssom/core_test.cljk']
NUM=re.compile(r'(?<![\w#.-])([+-]?(?:\d+\.\d+|\.\d+|\d+))(px|em|rem|%|deg|rad|grad|turn|fr|vw|vh|ex|ch|pt|s|ms)?(?![\w.])')
# restrict to inside declarations: text after ':' up to ';' or '}' or quote
DECL=re.compile(r':\s*([^;{}"\\]*[0-9][^;{}"\\]*)')
out={}
for p in SRC:
    txt=open(p,encoding='utf-8').read()
    stats=collections.defaultdict(lambda: {'n':0,'maxabs':0.0,'frac_digits':collections.Counter(),'neg':0})
    for m in DECL.finditer(txt):
        v=m.group(1)
        for n in NUM.finditer(v):
            num,unit=n.group(1),n.group(2) or 'number'
            f=float(num); s=stats[unit]
            s['n']+=1; s['maxabs']=max(s['maxabs'],abs(f)); s['neg']+= f<0
            fd=len(num.split('.')[1]) if '.' in num else 0
            s['frac_digits'][fd]+=1
    out[p.replace(ROOT,'')]={u:{'n':s['n'],'maxabs':s['maxabs'],'neg':s['neg'],'frac_digits':dict(sorted(s['frac_digits'].items()))} for u,s in sorted(stats.items())}
json.dump(out,open(sys.argv[1],'w'),indent=1)
for p,d in out.items():
    print(p)
    for u,s in d.items(): print('  %-7s n=%-5d maxabs=%-10g neg=%-4d frac=%s'%(u,s['n'],s['maxabs'],s['neg'],s['frac_digits']))
