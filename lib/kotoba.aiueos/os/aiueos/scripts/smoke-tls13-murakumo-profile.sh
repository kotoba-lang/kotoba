#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-tls13-murakumo.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

openssl_prefix=${OPENSSL_PREFIX:-}
if [ -z "$openssl_prefix" ] && command -v brew >/dev/null 2>&1; then
  openssl_prefix=$(brew --prefix openssl@3)
fi

cflags=
ldflags=
if [ -n "$openssl_prefix" ]; then
  cflags="-I$openssl_prefix/include"
  ldflags="-L$openssl_prefix/lib"
fi

# shellcheck disable=SC2086
cc -O2 -Werror -Wno-deprecated-declarations -DAIUEOS_TLS13_HOST_PROBE \
  $cflags \
  "$repo/os/aiueos/kernel/tls13.c" \
  "$repo/os/aiueos/kernel/tls_aes_gcm.c" \
  "$repo/os/aiueos/kernel/tls13_host_probe.c" \
  $ldflags -lcrypto -o "$work/probe"

"$work/probe" --inspect api.murakumo.cloud /infer/queue

if [ "${AIUEOS_TLS13_LIVE:-0}" = 1 ]; then
  "$work/probe" api.murakumo.cloud /infer/queue
fi

echo "AIUEOS_TLS13_MURAKUMO_PROFILE_OK sni=api.murakumo.cloud path=/infer/queue trust=transport-only physical-k16=unverified"
