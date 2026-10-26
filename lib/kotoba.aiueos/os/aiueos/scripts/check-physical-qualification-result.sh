#!/bin/sh
set -eu

volume=${1:-}
if [ -z "$volume" ]; then
  for candidate in /Volumes/AIUEOS\ RSLT*; do
    if [ -f "$candidate/AIUEOS.ID" ] &&
       grep -F "AIUEOS_K16_RESULT_VOLUME_V4" "$candidate/AIUEOS.ID" >/dev/null 2>&1; then
      volume=$candidate
      break
    fi
  done
fi
[ -n "$volume" ] || {
  echo "error: AIUEOS result volume is not mounted" >&2
  exit 2
}

result="$volume/RESULT.LOG"
probe="$volume/PROBE.LOG"
if [ ! -f "$result" ] || [ ! -f "$probe" ]; then
  # Historical v2 images kept both files on an ESP.  Retain explicit-path
  # compatibility, but automatic discovery above accepts only the v4 data
  # volume so it cannot mistake an unrelated mounted filesystem for a result.
  result="$volume/EFI/AIUEOS/RESULT.LOG"
  probe="$volume/EFI/AIUEOS/PROBE.LOG"
fi
[ -f "$result" ] || { echo "error: RESULT.LOG is absent" >&2; exit 2; }
[ -f "$probe" ] || { echo "error: PROBE.LOG is absent" >&2; exit 2; }

result_text=$(LC_ALL=C tr -d '\000\r' < "$result")
probe_text=$(LC_ALL=C tr -d '\000\r' < "$probe")

if printf '%s\n' "$result_text" | grep -Fx "AIUEOS_K16_RESULT_V4" >/dev/null; then
  result_format=AIUEOS_K16_RESULT_V4
  write_scope="usb_log_writes=same-usb-result-partition-only"
  require_dbc=yes
elif printf '%s\n' "$result_text" | grep -Fx "AIUEOS_K16_RESULT_V2" >/dev/null; then
  result_format=AIUEOS_K16_RESULT_V2
  write_scope="usb_log_writes=self-only"
  require_dbc=no
else
  echo "error: RESULT.LOG has no recognized result format" >&2
  exit 3
fi

for marker in \
  "$result_format" \
  "internal_ssd_writes=none" \
  "$write_scope" \
  "qualification_variable_cleared=yes"; do
  printf '%s\n' "$result_text" | grep -Fx "$marker" >/dev/null || {
    echo "error: RESULT.LOG missing marker: $marker" >&2
    exit 3
  }
done

state=$(printf '%s\n' "$result_text" | sed -n 's/^state=//p' | head -1)
code=$(printf '%s\n' "$result_text" | sed -n 's/^code=//p' | head -1)
case "$state" in
  incomplete)
    reason=terminal-marker-not-reached
    if [ "$code" != 0 ]; then
      reason=loader-hang-progress
      case "$code" in
        224|240|241|242|243|244|26[0-7]|27[0-7]|28[0-7]|30[0-7]|31[0-7]|3[2-9][0-9]|4[0-9][0-9]|50[0-9]|51[01])
          reason=paging-handoff-progress ;;
        220|221|222|223|225|226|227|228|229|299)
          reason=kernel-hang-progress ;;
      esac
    fi
    if printf '%s\n' "$probe_text" | grep -F "AIUEOS_HW_PROBE_GOP capability=absent" >/dev/null; then
      reason=gop-absent
    fi
    printf 'AIUEOS_K16_PHYSICAL_RESULT_INCOMPLETE code=%s reason=%s internal-ssd-writes=none\n' \
      "$code" "$reason" >&2
    exit 5
    ;;
  failure)
    printf 'AIUEOS_K16_PHYSICAL_RESULT_FAIL state=failure code=%s internal-ssd-writes=none\n' "$code" >&2
    exit 4
    ;;
  success) ;;
  *)
    echo "error: unknown qualification state" >&2
    exit 3
    ;;
esac

for marker in \
  "AIUEOS_HW_PROBE_CPU vendor=" \
  "AIUEOS_HW_PROBE_GOP capability=present" \
  "AIUEOS_HW_PROBE_MEMORY capability=present" \
  "AIUEOS_HW_PROBE_ACPI rsdp=present" \
  "AIUEOS_HW_PROBE_PCI capability=present" \
  "AIUEOS_HW_PROBE_BLOCK capability=present" \
  "AIUEOS_HW_PROBE_DONE exit_boot_services=no internal_disk_writes=none"; do
  printf '%s\n' "$probe_text" | grep -F "$marker" >/dev/null || {
    echo "error: PROBE.LOG missing marker: $marker" >&2
    exit 3
  }
done

if [ "$require_dbc" = yes ] &&
   ! printf '%s\n' "$probe_text" | grep -F "AIUEOS_HW_PROBE_XHCI_DBC_SUMMARY" >/dev/null; then
  echo "error: PROBE.LOG missing marker: AIUEOS_HW_PROBE_XHCI_DBC_SUMMARY" >&2
  exit 3
fi

[ "$code" = 0 ] || { echo "error: success result has code=$code" >&2; exit 3; }
printf 'AIUEOS_K16_PHYSICAL_RESULT_OK state=success code=0 internal-ssd-writes=none\n'
