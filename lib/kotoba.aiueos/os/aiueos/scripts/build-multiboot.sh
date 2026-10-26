#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
mb="$out/multiboot"
kernel64="$mb/MULTIBOOT.x86_64.ELF"
kernel="$mb/MULTIBOOT.ELF"
probe=${AIUEOS_KOTOBA_KERNEL_OBJECT:-"$aiueos/kotoba/kernel-probe.o"}
# kernel/apic.c is reused verbatim below and no longer carries its own rdmsr /
# wrmsr, so this path needs the same two MSR objects the UEFI path links. They
# are the first Kotoba objects other than the probe to reach the Multiboot
# kernel; without them apic.o has two undefined symbols and the link fails.
kotoba_msr_read_object=${AIUEOS_KOTOBA_MSR_READ_OBJECT:-"$aiueos/kotoba/msr-read.o"}
kotoba_msr_write_object=${AIUEOS_KOTOBA_MSR_WRITE_OBJECT:-"$aiueos/kotoba/msr-write.o"}
# kernel/acpi.c is reused verbatim here too, and its checksum and header checks
# have been Kotoba objects since ADR-0024 -- but this script was never taught
# about them, so this link has been failing with two undefined symbols
# (kotoba_aiueos_acpi_checksum_ok, kotoba_aiueos_acpi_table_valid) since then.
# Same shape as the apic.c/MSR omission the comment above records.
kotoba_acpi_checksum_object=${AIUEOS_KOTOBA_ACPI_CHECKSUM_OBJECT:-"$aiueos/kotoba/acpi-checksum-ok.o"}
kotoba_acpi_table_valid_object=${AIUEOS_KOTOBA_ACPI_TABLE_VALID_OBJECT:-"$aiueos/kotoba/acpi-table-valid.o"}
# multiboot/main.c's `legacy_pic_disable` is now a call into this object rather
# than ten `out8`s -- the same object kernel/main.c calls on the UEFI path, which
# is the point: ADR-0028's fix existed only here, and the UEFI path had the same
# latent gap. Without it this link has one undefined symbol
# (kotoba_aiueos_pic_disable). Same shape as the apic.c/MSR and acpi.c omissions
# the two comments above record, which is why it is listed at the same time as
# the C that needs it rather than after.
kotoba_pic_disable_object=${AIUEOS_KOTOBA_PIC_DISABLE_OBJECT:-"$aiueos/kotoba/pic-disable.o"}
# NOT linked here on purpose: kotoba/cpu-feature-nx.o, cpu-feature-syscall.o and
# cpu-apic-id.o. Unlike the four omissions recorded above and below -- each of
# which was a real missing link that broke this script -- this one is checked
# rather than assumed: the three objects replace `cpuid` sites in kernel/paging.c
# (NX), kernel/process.c (SYSCALL) and kernel/pci.c (MSI-X destination), and this
# path compiles NONE of those three files. It builds multiboot/entry.S,
# multiboot/main.c and reuses only kernel/acpi.c and kernel/apic.c, none of which
# ever contained a `cpuid`. Verified by linking: this script's output has no
# undefined kotoba_aiueos_cpu_* symbol. If this path ever reuses paging.c,
# process.c or pci.c the corresponding object must be added here, exactly as the
# MSR, ACPI and PIC omissions above had to be.
#
# NOT linked here on purpose: kotoba/kernel-context-build.o (and its ring-3
# twin kotoba/user-context-build.o, which this path has never linked either).
# Checked the same way rather than assumed: both are called only from
# kernel/scheduler.c -- `initial_context` and `initial_user_context` -- and the
# C this script compiles is multiboot/entry.S, multiboot/main.c, kernel/acpi.c
# and kernel/apic.c. scheduler.c is not among them, so there is no task
# scheduling on this path at all and no reference to either symbol. Verified by
# linking: this script's output has no undefined kotoba_aiueos_*_context_build.
# If this path ever compiles scheduler.c, BOTH objects must be added here.
#
# NOT linked here on purpose: kotoba/idt-gate-build.o. This path does not
# include kernel/main.c -- it has its own multiboot/main.c, which keeps a
# second copy of the same descriptor packing in C.
#
# The fuel objection to converting that copy is GONE. It used to be that
# install_idt_and_time_lapic's 257 gates (all 256 vectors, then vector 32
# again) would spend 257 of an unreplenished 512 across the whole boot, against
# 7 on the kernel path, so the conversion waited on a fuel-tier decision in
# kotoba-native's `bounded-memory?`. That predicate no longer exists: every
# kernel object now replenishes on every call, so idt-gate-build gets 1024 per
# call and costs a measured 1, and 257 gates cost 1 fuel each rather than 257
# out of a single lifetime budget. Converting the copy is now an ordinary piece
# of work, blocked by nothing here.

command -v zig >/dev/null 2>&1 || {
  echo "error: Zig is required to build the Multiboot kernel" >&2
  exit 1
}
mkdir -p "$mb"

# The compiler-emitted Kotoba probe object is admitted by the same fail-closed
# verifier the UEFI path uses; a hosted or import-bearing object is rejected.
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$probe" \
  3f7409bff00efaa79ec2e260b6734f740e9d7da002a9eb22a747344591e5d327
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_msr_read_object" \
  da3add0a82de4562a8da117105e9a40a67e87c8086ca9b71851c4a9d9e673e0c \
  kotoba_aiueos_msr_read
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_msr_write_object" \
  a6ae6efbe7c3a7543b391b01a9203906532b3c4328fb38bafb2d093b37bfe20d \
  kotoba_aiueos_msr_write
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_acpi_checksum_object" \
  f92dd1922a7d4dd2bb30614d3f8058da671b5f154bd9b5c452174ae8a17a5978 \
  kotoba_aiueos_acpi_checksum_ok
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_acpi_table_valid_object" \
  66e621af0bbd4f7436a03a52e945d10f99a87b2608554aa1f9e997b36b1de1f6 \
  kotoba_aiueos_acpi_table_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_pic_disable_object" \
  c88ff01d1eb89f9cf549f4c0ca24f34928f948cab4a96cad82a8ab518bf7fad1 \
  kotoba_aiueos_pic_disable

zig cc -target x86_64-freestanding-none \
  -c -o "$mb/entry.o" "$aiueos/multiboot/entry.S"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$mb/main.o" "$aiueos/multiboot/main.c"
# Reuse the kernel's validated ACPI parser and Local APIC timer verbatim (no
# other kernel globals; apic.c does now depend on the two MSR objects linked
# below) so the Multiboot path uses the same checks and interrupt bring-up.
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$mb/acpi.o" "$aiueos/kernel/acpi.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$mb/apic.o" "$aiueos/kernel/apic.c"
zig ld.lld -T "$aiueos/multiboot/linker.ld" -o "$kernel64" \
  "$mb/entry.o" "$mb/main.o" "$mb/acpi.o" "$mb/apic.o" "$probe" \
  "$kotoba_msr_read_object" "$kotoba_msr_write_object" \
  "$kotoba_acpi_checksum_object" "$kotoba_acpi_table_valid_object" \
  "$kotoba_pic_disable_object"

# QEMU's Multiboot loader wants an ELFCLASS32/EM_386 container; wrap the linked
# x86_64 load image verbatim (the trampoline switches to long mode itself).
python3 "$aiueos/scripts/wrap-multiboot32.py" "$kernel64" "$kernel"

[ "$(dd if="$kernel" bs=1 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')" = 7f454c46 ] || {
  echo "error: $kernel is not an ELF image" >&2
  exit 1
}
[ "$(dd if="$kernel" bs=1 skip=4 count=1 2>/dev/null | od -An -tu1 | tr -d ' \n')" = 1 ] || {
  echo "error: $kernel is not a 32-bit ELF container" >&2
  exit 1
}
python3 - "$kernel" <<'PY'
import struct, sys
data = open(sys.argv[1], "rb").read()
window = data[:8192]
magic = struct.pack("<I", 0x1BADB002)
index = window.find(magic)
if index < 0 or index % 4 != 0:
    raise SystemExit("multiboot header not found aligned within first 8 KiB")
flags, checksum = struct.unpack_from("<II", window, index + 4)
if (0x1BADB002 + flags + checksum) & 0xFFFFFFFF != 0:
    raise SystemExit("multiboot header checksum is invalid")
print("multiboot header at file offset %d flags=0x%x" % (index, flags))
PY
echo "$kernel"
