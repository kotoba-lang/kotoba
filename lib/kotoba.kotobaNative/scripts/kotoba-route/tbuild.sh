#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# tbuild.sh: build with reject! as a trap (no throw anywhere), so a type error the abort
# inference swallows ("neither catches it nor aborts") is reported with its span; prints the line.
S=${KR_WORK:-/tmp/kotoba-route}; H=$(cd "$(dirname "$0")" && pwd)
cp $S/twins/machine_ir.cljk $S/twins.bak
python3 - <<'P'
import os; p=os.environ.get('KR_WORK','/tmp/kotoba-route')+'/twins/machine_ir.cljk'
s=open(p).read()
s=s.replace('''  (throw (ex-info (string-concat "machine IR rejected: " (keyword-name problem))
                  {:phase phase :problem problem})))''','''  (trap!))''')
open(p,'w').write(s)
P
r=$($H/build.sh)
cp $S/twins.bak $S/twins/machine_ir.cljk
echo "$r"
l=$(echo "$r" | grep -o ':line [0-9]*' | grep -o '[0-9]*')
[ -n "$l" ] && sed -n "$((l-3)),$((l+3))p" $S/ov/src/kotoba/native/machine_ir.cljk
