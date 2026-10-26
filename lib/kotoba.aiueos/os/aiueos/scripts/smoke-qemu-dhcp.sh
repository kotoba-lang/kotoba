#!/bin/sh
set -eu

# DHCPv4 evidence, in both directions (ADR-0076).
#
# QEMU's user-mode network carries a real DHCP server -- gateway 10.0.2.2, DNS
# 10.0.2.3, leases from 10.0.2.15 -- so the guest talks to something that
# answers rather than to a simulation of one it wrote itself. No host network
# access is involved.
#
# FOUR BOOTS. One unmodified, which must configure an address; and three in
# which the received reply is broken in exactly ONE named way each, which must
# each be refused with the reason code that names what was broken. A run that
# goes red for a different reason than the one that was broken is not a
# demonstration, so each case asserts its own reason and rejects the others.
#
#   1  the transaction id becomes somebody else's       -> reason 5
#   2  the OFFER's message type becomes an ACK          -> reason 9
#   3  an option claims 255 bytes past the end of the
#      datagram                                          -> reason 8
#
# The tampering lives behind -DAIUEOS_DHCP_TAMPER in kernel/pci.c and is
# compiled out of every other build. It recomputes the UDP checksum afterwards,
# so the datagram stays well-formed in every respect except the one defect --
# otherwise the object would refuse at the checksum and the run would be red for
# a reason nobody chose.
#
# Nothing here hardcodes a passing status: each case reads the marker the kernel
# printed and fails if it is absent, if it is the wrong shape, or if the
# tampering could not be applied at all.

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-dhcp"}

# SLIRP's fixed topology. Asserted rather than merely printed, because a marker
# that says an address was configured without saying which one cannot be wrong.
expect_prefix="AIUEOS_DHCP_OK offer-ack kotoba-admitted address=10.0.2.15 mask=255.255.255.0 router=10.0.2.2 server=10.0.2.2 lease="

run_case() {
  mode=$1
  label=$2
  case_out="$out/case-$mode"
  rm -rf "$case_out"
  mkdir -p "$case_out"
  # Progress goes to stderr: this function's STDOUT is the marker line its
  # callers capture, and anything else on it is read as the marker. Measured --
  # the first version of this gate put the header on stdout and reported the
  # unmodified boot as having printed the wrong address, while the boot had in
  # fact printed exactly the right one.
  echo "--- dhcp case $mode ($label) ---" >&2
  # AIUEOS_SMOKE_FINAL_PROBE=1 arms the end-of-boot probe that the persistent desktop loop disarmed in the default build (aiueos#436,
  # kernel/main.c): the terminal evidence smoke-qemu-uefi.sh's normal path asserts. Without it this suite stalls at the loop (JUN-363).
  # A tampered boot still has to reach the DHCP stage, so the rest of the suite
  # runs unchanged and its exit status is still checked by smoke-qemu-uefi.sh.
  if [ "$mode" = 0 ]; then
    AIUEOS_OUT="$case_out" AIUEOS_TEST_NET=1 AIUEOS_SMOKE_FINAL_PROBE=1 "$aiueos/scripts/smoke-qemu-uefi.sh" >/dev/null
  else
    AIUEOS_OUT="$case_out" AIUEOS_TEST_NET=1 AIUEOS_SMOKE_FINAL_PROBE=1 AIUEOS_DHCP_TAMPER="$mode" \
      "$aiueos/scripts/smoke-qemu-uefi.sh" >/dev/null
  fi
  serial="$case_out/kernel-serial.log"
  [ -f "$serial" ] || { echo "error: case $mode produced no serial log" >&2; exit 1; }
  # The DHCP marker, whichever it is, with the CR stripped.
  line=$(sed 's/\r$//' "$serial" | grep -E '^AIUEOS_DHCP_(OK|FAIL) ' || true)
  [ -n "$line" ] || {
    echo "error: case $mode printed no AIUEOS_DHCP_ marker at all" >&2
    echo "       (a boot that never reached the DHCP stage is not a refusal)" >&2
    sed 's/\r$//' "$serial" | tail -20 >&2
    exit 1
  }
  echo "$line"
}

# --- the unmodified run -----------------------------------------------------
line=$(run_case 0 "unmodified")
case "$line" in
  "$expect_prefix"*) ;;
  *)
    echo "error: unmodified boot did not configure the address SLIRP hands out" >&2
    echo "       expected prefix: $expect_prefix<seconds>" >&2
    echo "       got:             $line" >&2
    exit 1
    ;;
esac
# The lease is a number the server chose, so it is checked for being one rather
# than for being a particular one -- the object already refused anything outside
# 60..2592000, so a marker at all means the range held.
lease=${line##*lease=}
case "$lease" in
  ''|*[!0-9]*)
    echo "error: unmodified boot printed a non-numeric lease: '$lease'" >&2
    exit 1
    ;;
esac
echo "AIUEOS_DHCP_GATE_CASE_OK unmodified lease=${lease}s"

# --- the three refusals -----------------------------------------------------
check_refusal() {
  mode=$1
  expect_reason=$2
  expect_name=$3
  label=$4
  line=$(run_case "$mode" "$label")
  case "$line" in
    AIUEOS_DHCP_OK*)
      echo "error: case $mode was admitted; the object did not refuse $label" >&2
      echo "       got: $line" >&2
      exit 1
      ;;
  esac
  # The stage AND the reason. The stage says which round trip stopped; the
  # reason says which clause of the admission refused. Asserting only the stage
  # would pass on a refusal for an unrelated reason, which is exactly the
  # failure this gate exists to rule out.
  expected="AIUEOS_DHCP_FAIL no-admitted-offer reason=${expect_reason} ${expect_name}"
  [ "$line" = "$expected" ] || {
    echo "error: case $mode refused for the wrong reason" >&2
    echo "       broke:    $label" >&2
    echo "       expected: $expected" >&2
    echo "       got:      $line" >&2
    exit 1
  }
  echo "AIUEOS_DHCP_GATE_CASE_OK $label refused=${expect_reason} ${expect_name}"
}

check_refusal 1 5 foreign-transaction-id  "transaction id"
check_refusal 2 9 message-type            "message type"
check_refusal 3 8 options-overrun         "option length past the end of the frame"

echo "AIUEOS_DHCP_SMOKE_OK admitted=1 refused=3 distinct-reasons=5,9,8"
