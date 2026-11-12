#!/bin/zsh
H=$(cd "$(dirname "$0")" && pwd)
# j.sh 'FORMS' : evaluate in the persistent JVM; prints the results
{ printf '%s\n' "$1"; printf ':repl/quit\n'; } | nc -q 1 localhost 5791 2>/dev/null || { printf '%s\n:repl/quit\n' "$1" | nc localhost 5791; }
