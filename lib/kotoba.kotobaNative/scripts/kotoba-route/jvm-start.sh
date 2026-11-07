#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# persistent JVM (host reading, AOT classes of the native-image work dir) with a socket REPL on 5791.
# ${KR_WORK:-/tmp/kotoba-route}/jvm/src goes FIRST on the classpath: fresh host-reading copies (.cljc) of modules we edit.
ulimit -s 65500
exec java -Xss1g -Xmx8g -Dclojure.server.repl="{:port 5791 :accept clojure.core.server/repl}" -cp "${KR_WORK:-/tmp/kotoba-route}/jvm/src:/private/tmp/wt-A-amu-measure/build/native-image/work/classes:$(cat /private/tmp/wt-A-amu-measure/build/native-image/work/classpath.txt)" clojure.main -e '(do (println :ready) @(promise))'
