#!/usr/bin/env bash
set -euo pipefail

java_major="$(java -version 2>&1 | sed -n '1s/.*version "\([0-9]*\).*/\1/p')"
if [[ -z "${java_major}" || "${java_major}" -lt 21 ]]; then
  echo "PostgreSQL matrix requires JDK 21+ (javax.crypto.KEM authority)" >&2
  exit 2
fi

for major in 14 15 17; do
  prefix="/opt/homebrew/opt/postgresql@${major}/bin"
  if [[ ! -x "${prefix}/postgres" ]]; then
    echo "missing required PostgreSQL ${major}: ${prefix}/postgres" >&2
    exit 3
  fi
  echo "matrix cell: JDK ${java_major}, $(${prefix}/postgres --version)"
  PATH="${prefix}:${PATH}" kbb -M:postgresql-interop
done

echo "PostgreSQL local matrix: PASS"
