#!/usr/bin/env python3
"""IEEE-754 double vs exact-rational floor for the `(long (* m font-size))` pattern (layout.cljk resolve-line-height 4817-4818,
glyph-advance 527, ua `(long (* 1.2 font-size))` 4835). Python float == Java/JS double for * and /."""
import math, json
out={}
# 1) line-height multiplier m = k/100 (as parsed by Double/parseDouble of the 2-decimal text) times integer font size
bad=[];n=0
for k in range(0,501):
    m=float(k)/100.0           # == parseDouble("%.2f") (correct rounding of the same rational)
    for fs in range(1,257):
        n+=1
        if int(math.floor(m*fs))!=(k*fs)//100: bad.append((k/100,fs,m*fs,(k*fs)//100))
out['line_height_multiplier_2dp']={'pairs':n,'mismatch':len(bad),'examples':[(a,b,repr(c),d) for a,b,c,d in bad[:6]]}
# 2) the constant 0.6 and 1.2 multipliers for integer font sizes
for name,m,kk in (('glyph_advance_0.6',0.6,6),('normal_line_height_1.2',1.2,12)):
    bad=[(fs,repr(m*fs),(kk*fs)//10) for fs in range(1,4097) if int(math.floor(m*fs))!=(kk*fs)//10]
    out[name]={'pairs':4096,'mismatch':len(bad),'examples':bad[:6]}
# 3) percentage-of as in layout.cljk 3939: round-half-up(basis*(pct/100.0)); pct from 2-decimal text
bad=0;n=0;ex=[]
for H in range(0,30001,1):
    pct=H/100.0
    for b in range(0,513):
        n+=1
        x=b*(pct/100.0); r=math.floor(x+0.5) if x-math.floor(x)!=0.5 else math.floor(x)+1
        if r!=(H*b+5000)//10000:
            bad+=1
            if len(ex)<4: ex.append((H/100,b,repr(x),(H*b+5000)//10000))
out['percentage_of_python_check_basis0..512']={'pairs':n,'mismatch':bad,'examples':ex}
json.dump(out,open('trunc-oracle.json','w'),indent=1)
for k,v in out.items(): print(k,v['pairs'],v['mismatch'],v['examples'][:3])
