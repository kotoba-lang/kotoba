#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# chk.sh FILE [extra source path...]: native checker with our scratch overlay first
f=$1; shift
K=/private/tmp/wt-K-kotoba-lang
CPF=${MI_CP:-/private/tmp/wall-cp-15.txt}
CP=$(cat $CPF)
SP=""
for p in "$@"; do SP="$SP --source-path $p"; done
SP="$SP $(echo "$CP" | tr ':' '\n' | grep '/src$' | sed 's/^/--source-path /' | tr '\n' ' ') --source-path /private/tmp/wt-A-amu-measure/src --source-path $K/lang/compat"
ulimit -s 65500 2>/dev/null
/private/tmp/wt-A-amu-measure/build/native-image/amu-native check $f --policy $K/lang/selfhost-compiler-grant.edn ${=SP} --json --no-definitions 2>&1 | head -c ${MI_HEAD:-1500}
echo
