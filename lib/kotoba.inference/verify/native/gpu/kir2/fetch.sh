#!/bin/sh
# verify/native/gpu/kir2/fetch.sh AMU-CLONE WORK STAGE
#
# Fetches Amu's KIR v2 GPU modules at artifacts.edn's :amu/commit, checks
# them with inference's native gate (kir2_artifacts.kotoba), and stages them
# in STAGE under the names the decode guests load. JUN-375; amu ADR 0374
# option D. Nothing here runs a GPU.
#
# AMU-CLONE  a clone of kotoba-lang/amu that has :amu/commit (read with git archive)
# WORK       a new directory for Amu's tree, its build and the gate's runs
# STAGE      an empty or new directory; it receives the modules only when
#            every step below is green
#
# 1. refs (this host): Amu's glslang modules of the kernels' copies in
#    tools/gpu_kernel_refs (glslangValidator). Amu's build checks them with
#    the Kotoba checker.
# 2. build (arm64 Linux container): Amu selfhost writes the KIR v2 modules,
#    using the pinned root seed/bootstrap/aarch64-linux-static-root.elf.
# 3. oracle (this host): Amu's spirv-val and spirv-dis over every module.
#    Then inference's oracle (glslangValidator): glslang of each artifact's
#    :replaces must be byte-identical to Amu's glslang module :ref. It ties the
#    name the guests load to the kernel Amu ran (see the gate's GPU pair and
#    refs.json checks). Its control: the first artifact with a define, built
#    without it, must differ from its :ref.
# 4. gate (the same container): the same root compiles kir2_artifacts.kotoba
#    to a static image. Five negative controls must each fail by name:
#    * one byte of a module changed;
#    * one hex digit of a module's pin changed;
#    * one hex digit of the receipt's pin changed;
#    * an artifact pointing at its neighbour's module, with that module's pin;
#    * an artifact naming its neighbour's glslang reference.
#    Then the gate checks every artifact and stages them, inside WORK.
#
# glslang and spirv-val run only as oracles. The staged modules are Amu's
# KIR v2 bytes. CONTAINER (default podman) selects the container runtime.
set -eu

ROOT=/amu/seed/bootstrap/aarch64-linux-static-root.elf
TABLE=/inference/verify/native/gpu/kir2/artifacts.edn
# python:3.12-alpine for linux/arm64, 2026-10-21
IMAGE=docker.io/library/python@sha256:57f679a3910bed1eb16ad722b904a118bca8586ec8ad39d98dd13350e7062cb2

# ---- step 4, inside the container ----
if [ "${1:-}" = "--gate" ]; then
  gate() {
    env -i PATH=/usr/bin:/bin KEXE_ALLOW=3,35,37,38,39 KEXE_CAP_RESOURCES_35=/inference:/amu:/out:/gate \
      KEXE_FUEL=4000000000 KEXE_STRUCTURED_REPORT=1 /gate/kir2_artifacts.elf "$@"
  }
  # one FAIL line and result 1, the line starting with $2
  red_as() {
    [ "$(grep -c '^FAIL ' "$1")" = 1 ] && grep -q "^FAIL $2" "$1" && grep -q '^{:status :ok :result 1 ' "$1"
  }
  # the table with the first digit after the first occurrence of $1 changed
  flip() {
    awk -v k="$1" 'd == 0 && index($0, k) { i = index($0, k) + length(k); c = substr($0, i, 1); $0 = substr($0, 1, i - 1) (c == "0" ? "1" : "0") substr($0, i + 1); d = 1 } { print }' "$TABLE"
  }
  # the value of key $1 in artifact line $2
  value() { sed -n 's/^.*'"$1"' "\{0,1\}\([^" ]*\)"\{0,1\} .*$/\1/p' "$2"; }

  env -i PATH=/usr/bin:/bin KEXE_CAP_RESOURCES_35=/gate "$ROOT" compile /gate/kir2_artifacts.kotoba \
    --target aarch64-linux --output /gate/kir2_artifacts.elf --format static
  chmod 700 /gate/kir2_artifacts.elf
  grep '{:spv "' "$TABLE" | sed -n 1p > /gate/first.line
  grep '{:spv "' "$TABLE" | sed -n 2p > /gate/second.line
  spv=$(value '{:spv' /gate/first.line)
  amu=$(value ':amu' /gate/first.line)

  # control 1: byte 100 of the first artifact's module, plus one. The gate's
  # digest of the changed file must be sha256sum's
  mkdir /gate/ctl-out
  cp -R /out/spv /out/refs /gate/ctl-out/
  m=/gate/ctl-out/spv/$amu
  b=$(dd if="$m" bs=1 skip=100 count=1 2>/dev/null | od -An -tu1 | tr -d ' ')
  printf "\\$(printf '%03o' $(( (b + 1) % 256 )))" | dd of="$m" bs=1 seek=100 conv=notrunc 2>/dev/null
  gate "$TABLE" /amu /gate/ctl-out - > /gate/ctl-module.out 2>&1 || true
  red_as /gate/ctl-module.out "sha256 $spv: $amu is $(wc -c < "$m" | tr -d ' ') $(sha256sum "$m" | cut -d' ' -f1)\$" \
    || { cat /gate/ctl-module.out; echo "RED: control 1 (a changed module) did not fail by name"; exit 1; }

  # control 2: the first hex digit of the first artifact's pin, changed
  flip ':sha256 "' > /gate/ctl-artifacts.edn
  gate /gate/ctl-artifacts.edn /amu /out - > /gate/ctl-pin.out 2>&1 || true
  red_as /gate/ctl-pin.out "receipt $spv:" || { cat /gate/ctl-pin.out; echo "RED: control 2 (a changed pin) did not fail by name"; exit 1; }

  # control 3: the first hex digit of the receipt's pin, changed
  flip ':amu/receipt-sha256 "' > /gate/ctl-receipt.edn
  gate /gate/ctl-receipt.edn /amu /out - > /gate/ctl-receipt.out 2>&1 || true
  red_as /gate/ctl-receipt.out "receipt sha256 " || { cat /gate/ctl-receipt.out; echo "RED: control 3 (a changed receipt pin) did not fail by name"; exit 1; }

  # control 4: the first artifact names the second's module, bytes and pin;
  # its GPU pair still names its own kernel
  awk -v a="$(value ':amu' /gate/second.line)" -v n="$(value ':bytes' /gate/second.line)" -v h="$(value ':sha256' /gate/second.line)" \
    'd == 0 && index($0, "{:spv \"") { sub(/:amu "[^"]*"/, ":amu \"" a "\""); sub(/:bytes [0-9]+/, ":bytes " n); sub(/:sha256 "[0-9a-f]*"/, ":sha256 \"" h "\""); d = 1 } { print }' \
    "$TABLE" > /gate/ctl-pair.edn
  gate /gate/ctl-pair.edn /amu /out - > /gate/ctl-pair.out 2>&1 || true
  red_as /gate/ctl-pair.out "pair $spv: the GPU pair v2-" || { cat /gate/ctl-pair.out; echo "RED: control 4 (a module swapped in) did not fail by name"; exit 1; }

  # control 5: the first artifact names the second's glslang reference
  awk -v r="$(value ':ref' /gate/second.line)" 'd == 0 && index($0, "{:spv \"") { sub(/:ref "[^"]*"/, ":ref \"" r "\""); d = 1 } { print }' \
    "$TABLE" > /gate/ctl-ref.edn
  gate /gate/ctl-ref.edn /amu /out - > /gate/ctl-ref.out 2>&1 || true
  red_as /gate/ctl-ref.out "pair $spv: the GPU pair ref-" || { cat /gate/ctl-ref.out; echo "RED: control 5 (a reference swapped in) did not fail by name"; exit 1; }

  # the run: check, then stage inside WORK
  mkdir /gate/stage
  gate "$TABLE" /amu /out /gate/stage > /gate/run.out 2>&1 || true
  cat /gate/run.out
  n=$(grep -c ':sha256 "' "$TABLE")
  if grep -q '^FAIL ' /gate/run.out || ! grep -q '^FAILED 0$' /gate/run.out || ! grep -q "^ARTIFACTS $n\$" /gate/run.out \
     || ! grep -q '^{:status :ok :result 0 ' /gate/run.out || [ "$(ls /gate/stage | wc -l | tr -d ' ')" != "$n" ]; then
    echo "RED: the gate failed"; exit 1
  fi

  echo "{:fetch :kotoba-inference.kir2-fetch/v1 :root {:sha256 \"$(sha256sum "$ROOT" | cut -d' ' -f1)\"}" \
    ":gate {:source {:sha256 \"$(sha256sum /gate/kir2_artifacts.kotoba | cut -d' ' -f1)\"} :image {:sha256 \"$(sha256sum /gate/kir2_artifacts.elf | cut -d' ' -f1)\"}}" \
    ":fetch-sh {:sha256 \"$(sha256sum /inference/verify/native/gpu/kir2/fetch.sh | cut -d' ' -f1)\"} :container \"$IMAGE\"" \
    ":run :green :artifacts $n :controls {:module-byte :red-by-name :pin-digit :red-by-name :receipt-digit :red-by-name :pair-swap :red-by-name :ref-swap :red-by-name}}"
  exit 0
fi

# ---- steps 1-4, on the developer host ----
[ $# -eq 3 ] || { echo "usage: $0 AMU-CLONE WORK STAGE" >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd -P)
INF=$(cd "$HERE/../../../.." && pwd -P)
CONTAINER=${CONTAINER:-podman}
COMMIT=$(sed -n 's/^{:amu\/commit "\([0-9a-f]\{40\}\)"$/\1/p' "$HERE/artifacts.edn")
[ -n "$COMMIT" ] || { echo "no :amu/commit in artifacts.edn" >&2; exit 1; }
git -C "$1" cat-file -e "$COMMIT^{commit}" || { echo "$1 has no commit $COMMIT" >&2; exit 1; }
mkdir "$2"
mkdir -p "$3"
[ -z "$(ls -A "$3")" ] || { echo "STAGE $3 is not empty" >&2; exit 1; }
WORK=$(cd "$2" && pwd -P)
STAGE=$(cd "$3" && pwd -P)
mkdir "$WORK/amu" "$WORK/out" "$WORK/gate" "$WORK/oracle"
git -C "$1" archive -o "$WORK/amu.tar" "$COMMIT"
tar -x -C "$WORK/amu" -f "$WORK/amu.tar"

python3 -I "$WORK/amu/scripts/seed/check-gpu-kernel-spirv.py" refs --suite kir2 --output "$WORK/out"
"$CONTAINER" run --rm --platform linux/arm64 -v "$WORK/amu:/amu:ro" -v "$WORK/out:/out" "$IMAGE" \
  python3 -I /amu/scripts/seed/check-gpu-kernel-spirv.py build --suite kir2 --compiler "$ROOT" --output /out
python3 -I "$WORK/amu/scripts/seed/check-gpu-kernel-spirv.py" oracle --suite kir2 --output "$WORK/out"

grep '{:spv "' "$HERE/artifacts.edn" > "$WORK/oracle/artifacts.lines"
while IFS= read -r line; do
  spv=$(printf '%s\n' "$line" | sed 's/^.*{:spv "\([^"]*\)".*$/\1/')
  ref=$(printf '%s\n' "$line" | sed 's/^.* :ref "\([^"]*\)".*$/\1/')
  rep=$(printf '%s\n' "$line" | sed 's/^.* :replaces "\([^"]*\)".*$/\1/')
  src=${rep%% *}
  defs=${rep#"$src"}
  # shellcheck disable=SC2086 # the defines are separate words
  glslangValidator -V --target-env vulkan1.1 $defs "$INF/$src" -o "$WORK/oracle/$spv" > "$WORK/oracle/$spv.log" 2>&1 \
    || { cat "$WORK/oracle/$spv.log" >&2; echo "RED: glslang failed on $rep" >&2; exit 1; }
  cmp -s "$WORK/oracle/$spv" "$WORK/out/refs/$ref" || { echo "RED: glslang of $rep is not Amu's $ref" >&2; exit 1; }
  echo "ORACLE $spv: glslang of $rep = Amu's $ref"
done < "$WORK/oracle/artifacts.lines"
# the oracle's control: without its defines, the first such artifact's source is not its :ref
line=$(grep ' -D' "$WORK/oracle/artifacts.lines" | sed -n 1p)
ref=$(printf '%s\n' "$line" | sed 's/^.* :ref "\([^"]*\)".*$/\1/')
rep=$(printf '%s\n' "$line" | sed 's/^.* :replaces "\([^"]*\)".*$/\1/')
glslangValidator -V --target-env vulkan1.1 "$INF/${rep%% *}" -o "$WORK/oracle/control.spv" > "$WORK/oracle/control.log" 2>&1
if cmp -s "$WORK/oracle/control.spv" "$WORK/out/refs/$ref"; then
  echo "RED: the oracle's control (${rep%% *} without its defines) matched $ref" >&2; exit 1
fi
echo "ORACLE-CONTROL ${rep%% *} without ${rep#* } is not Amu's $ref, as required"

cp "$HERE/kir2_artifacts.kotoba" "$WORK/gate/"
"$CONTAINER" run --rm --platform linux/arm64 -v "$WORK/amu:/amu:ro" -v "$INF:/inference:ro" -v "$WORK/out:/out:ro" \
  -v "$WORK/gate:/gate" "$IMAGE" sh /inference/verify/native/gpu/kir2/fetch.sh --gate \
  > "$WORK/gate/fetch.out" 2>&1 && status=0 || status=$?
cat "$WORK/gate/fetch.out"
[ "$status" = 0 ] || exit "$status"
cp "$WORK/gate/stage/"*.spv "$STAGE/"
echo "STAGE $STAGE: $(ls "$STAGE" | wc -l | tr -d ' ') modules"
