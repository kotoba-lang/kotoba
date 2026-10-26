#!/bin/sh
set -eu

aiueos=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compiler=${1:?usage: reproduce-kotoba-kernel-object.sh /path/to/compiler}
# The compiler that reproduces the committed objects. Advanced 2026-08-17 from
# 0b16d9b6, which could not: with that revision every one of the objects below
# either failed to compile (12 of them) or produced different bytes (25), so
# this script had not passed in some time and nothing was running it to notice.
#
# 8ff1030 reproduced all 37 byte-for-byte, checked one at a time before this
# line was changed. It is not the tip of the compiler's main and it is pinned
# here because it is the revision the check was actually run against. Pinning
# the tip would put an unverified number in a file whose whole purpose is to
# state a verified one.
#
# Advanced 2026-08-22 from 8ff1030 to 9cf3a0a, which is 8ff1030 with ONE line
# changed: its kotoba-native dependency moves from 15b4a0e2 to a60da444, and
# a60da444 is 15b4a0e2 plus two entries in `kernel-object-entries` and nothing
# else. Codegen is untouched, which is the point -- the two DHCP objects
# (ADR-0076) could not be compiled at all without those entries, and every
# object above them still had to reproduce.
#
# THE FULL ADVANCE WAS MEASURED AND NOT TAKEN. The sample below has since
# been replaced by the whole inventory -- ADR-0129 and
# qualification/object-producer-measurement.edn: of 66 objects, 4 reproduce,
# 58 differ (all smaller), and 4 fail with an internal compiler error, which
# the five-object sample could not have shown.
# amu's tip is 250 commits ahead
# and pins kotoba-native main, which is 121 commits ahead of 15b4a0e2 and moves
# 2,076 lines of machine_ir.cljc and 281 of x86_64.cljc. Five objects were
# compiled there and compared against the checked-in bytes:
# net-arp-reply-valid, ipv4-checksum, ipv4-icmp-reply-valid, tcp-segment-valid
# and sha256 -- ALL FIVE DIFFER. Taking that advance means regenerating every
# object in this script and every pinned digest in build-uefi.sh, which is a
# change to the shipped kernel and not a side effect of adding DHCP.
#
# 2026-09-02: `sha256.kotoba` and `digest-equal.kotoba` MOVED to
# `kotoba/aiueos/sha256.kotoba` and `kotoba/aiueos/digest_equal.kotoba` and
# gained an `(:export ...)` vector, because a project module must declare one
# and both are now imported by `cid-v1-admit` / `value-runtime-cas-verify`
# instead of being copied into them. THE OBJECTS DID NOT MOVE AND DID NOT
# CHANGE: compiled at this same pin with and without the export vector, both
# produce af378b06... and 6156db8b... -- the committed bytes -- so the two
# `cmp`s below still compare what they always did.
expected=9cf3a0ac07a1fb0d735a460230a7e5e9c97bc6a7
actual=$(git -C "$compiler" rev-parse HEAD)

[ "$actual" = "$expected" ] || {
  echo "error: compiler HEAD is $actual; expected $expected" >&2
  exit 1
}

tmp=${TMPDIR:-/tmp}/aiueos-kotoba-kernel-probe.$$
journal_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-journal-plan.$$
fnv_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-fnv1a.$$
journal_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-journal-valid.$$
transaction_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-transaction-valid.$$
transaction_route_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-transaction-route.$$
mutable_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-mutable-valid.$$
superblock_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-superblock-valid.$$
journal_build_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-journal-build.$$
mutable_build_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-mutable-build.$$
cap_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-cap-valid.$$
extent_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-extent-valid.$$
region_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-region-valid.$$
syscall_range_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-syscall-range.$$
copy_in_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-copy-in.$$
capability_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-capability.$$
capability_mutation_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-capability-mutation.$$
service_lifecycle_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-service-lifecycle.$$
service_registry_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-service-registry.$$
service_registry_state_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-service-registry-state.$$
user_object_journal_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-user-object-journal.$$
user_object_journal_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-user-object-journal-valid.$$
user_object_journal_value_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-user-object-journal-value.$$
sha256_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-sha256.$$
digest_equal_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-digest-equal.$$
catalog_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-app-catalog-valid.$$
app_lookup_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-app-lookup-plan.$$
user_elf_valid_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-user-elf-valid.$$
user_context_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-user-context.$$
mapping_plan_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-mapping-plan.$$
process_plan_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-process-plan.$$
teardown_plan_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-teardown-plan.$$
task_plan_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-task-plan.$$
dispatch_plan_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-dispatch-plan.$$
exit_route_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-exit-route.$$
service_task_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-service-task.$$
rsa2048_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-rsa2048.$$
dhcp_reply_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-dhcp-reply.$$
dhcp_option_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-dhcp-option.$$
ecdsa_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-ecdsa-p256.$$
ime_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-ime-romaji.$$
wm_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-wm-hit.$$
scanout_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-scanout-bind.$$
broker_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-broker-admit.$$
session_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-session-restore.$$
user_elf_tmp=${TMPDIR:-/tmp}/aiueos-kotoba-user-smoke.$$
trap 'rm -f "$dhcp_reply_tmp" "$dhcp_option_tmp" "$ecdsa_tmp" "$ime_tmp" "$wm_tmp" "$scanout_tmp" "$broker_tmp" "$session_tmp" "$tmp" "$journal_tmp" "$fnv_tmp" "$journal_valid_tmp" "$transaction_valid_tmp" "$transaction_route_tmp" "$mutable_valid_tmp" "$superblock_valid_tmp" "$journal_build_tmp" "$mutable_build_tmp" "$cap_valid_tmp" "$extent_valid_tmp" "$region_valid_tmp" "$syscall_range_tmp" "$copy_in_tmp" "$capability_tmp" "$capability_mutation_tmp" "$service_lifecycle_tmp" "$service_registry_tmp" "$service_registry_state_tmp" "$user_object_journal_tmp" "$user_object_journal_valid_tmp" "$user_object_journal_value_tmp" "$sha256_tmp" "$digest_equal_tmp" "$catalog_valid_tmp" "$app_lookup_tmp" "$user_elf_valid_tmp" "$user_context_tmp" "$mapping_plan_tmp" "$process_plan_tmp" "$teardown_plan_tmp" "$task_plan_tmp" "$dispatch_plan_tmp" "$exit_route_tmp" "$service_task_tmp" "$rsa2048_tmp" "$user_elf_tmp"' EXIT HUP INT TERM
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/kernel-probe.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$tmp"
cmp "$aiueos/kotoba/kernel-probe.o" "$tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$tmp" \
  e230c792ebe8e983bb68a86b913f121afeb50e834032ff499f5f35e4a7a01002
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/journal-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$journal_tmp"
cmp "$aiueos/kotoba/journal-plan.o" "$journal_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$journal_tmp" \
  6983847499117a5bfeb2194490290794eed792e405a8b3b52b5f808c1a2461d3 \
  kotoba_aiueos_journal_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/fnv1a.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$fnv_tmp"
cmp "$aiueos/kotoba/fnv1a.o" "$fnv_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$fnv_tmp" \
  bd1ea7d065ab9c306de56074606ab66d8a409fc5d99e36cae2b77b99f5f16ce0 \
  kotoba_aiueos_fnv1a
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/journal-record-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$journal_valid_tmp"
cmp "$aiueos/kotoba/journal-record-valid.o" "$journal_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$journal_valid_tmp" \
  c6dfb5f85029fd1f32a9fb84e6060f0d6287e3b018c24aa1cdf666870e417d62 \
  kotoba_aiueos_journal_record_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/object-transaction-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$transaction_valid_tmp"
cmp "$aiueos/kotoba/object-transaction-valid.o" "$transaction_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$transaction_valid_tmp" \
  503260e5548a48ede216ac6413a99dd4a26d7db2a32a2109cdfae7b93a05cc4c \
  kotoba_aiueos_object_transaction_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/object-transaction-route.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$transaction_route_tmp"
cmp "$aiueos/kotoba/object-transaction-route.o" "$transaction_route_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$transaction_route_tmp" \
  913ac071a4e19423c89fa7d0da20fbba0a0861d41e49ebe23e8397f2a08856ed \
  kotoba_aiueos_object_transaction_route
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/mutable-object-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$mutable_valid_tmp"
cmp "$aiueos/kotoba/mutable-object-valid.o" "$mutable_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$mutable_valid_tmp" \
  22fc8573f63decf753f4bc042d5e1253442a690842ab9923ca6b0a9020c0122e \
  kotoba_aiueos_mutable_object_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/superblock-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$superblock_valid_tmp"
cmp "$aiueos/kotoba/superblock-valid.o" "$superblock_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$superblock_valid_tmp" \
  41c5efc78b799b3121978f184959f8c02ffd1a3d6a65ac1f661684d1f050feb6 \
  kotoba_aiueos_superblock_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/journal-record-build.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$journal_build_tmp"
cmp "$aiueos/kotoba/journal-record-build.o" "$journal_build_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$journal_build_tmp" \
  d34637fe845cede481ee5bdd23fc6297d9a4933191fefba4bb6e8c26df7d1b7a \
  kotoba_aiueos_journal_record_build
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/mutable-object-build.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$mutable_build_tmp"
cmp "$aiueos/kotoba/mutable-object-build.o" "$mutable_build_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$mutable_build_tmp" \
  a9cbcc5ebefbe8615de9d291d6bffd95119b591540acdcb9041e43e4ebbd595f \
  kotoba_aiueos_mutable_object_build
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/virtio-cap-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$cap_valid_tmp"
cmp "$aiueos/kotoba/virtio-cap-valid.o" "$cap_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$cap_valid_tmp" \
  c13ec58990659e864cc2a347bc79b3644e40807c7545dbb49852c397bf5d52e0 \
  kotoba_aiueos_virtio_cap_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/pci-extent-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$extent_valid_tmp"
cmp "$aiueos/kotoba/pci-extent-valid.o" "$extent_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$extent_valid_tmp" \
  a2666dfadf05361a7e0ad06cd4d24d55dc75b0e06f9323ae86f1ac8a29a695c5 \
  kotoba_aiueos_pci_extent_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/pci-region-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$region_valid_tmp"
cmp "$aiueos/kotoba/pci-region-valid.o" "$region_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$region_valid_tmp" \
  a96c6589752121b11e915728a33ca0d78805d0bdf3c80852a35d288d12b22bb6 \
  kotoba_aiueos_pci_region_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/syscall-range-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$syscall_range_tmp"
cmp "$aiueos/kotoba/syscall-range-valid.o" "$syscall_range_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$syscall_range_tmp" \
  1a25f96061a6990bbdf3564b2afe8c27644bdb86b2517fddd231baf0af9c5d81 \
  kotoba_aiueos_syscall_range_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/copy-in.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$copy_in_tmp"
cmp "$aiueos/kotoba/copy-in.o" "$copy_in_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$copy_in_tmp" \
  2e3f0cc18348d8748edcd879979a6ebcf7a706b0044e8264d18abe2f424715b3 \
  kotoba_aiueos_copy_in
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/capability-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$capability_tmp"
cmp "$aiueos/kotoba/capability-plan.o" "$capability_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$capability_tmp" \
  0f2b8f694bc9c79b2c6ea155c81d5d6855a1f346beb89c903dc90528b1c6d222 \
  kotoba_aiueos_capability_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/capability-mutation-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$capability_mutation_tmp"
cmp "$aiueos/kotoba/capability-mutation-plan.o" "$capability_mutation_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$capability_mutation_tmp" \
  ef16ab4b0720cbbb1a28071499e28aebf6c30accec7ff457b697d430514c6459 \
  kotoba_aiueos_capability_mutation_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/service-lifecycle.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$service_lifecycle_tmp"
cmp "$aiueos/kotoba/service-lifecycle.o" "$service_lifecycle_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$service_lifecycle_tmp" \
  ca63a6fe25c3373741057d9f17bf9ff184d19a92da61e9f5c1a3677915a5eaae \
  kotoba_aiueos_service_lifecycle
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/service-registry-build.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$service_registry_tmp"
cmp "$aiueos/kotoba/service-registry-build.o" "$service_registry_tmp"
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/service-registry-state.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$service_registry_state_tmp"
cmp "$aiueos/kotoba/service-registry-state.o" "$service_registry_state_tmp"
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/user-object-journal-build.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$user_object_journal_tmp"
cmp "$aiueos/kotoba/user-object-journal-build.o" "$user_object_journal_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$user_object_journal_tmp" \
  9cec3d6655c9b2876585fea896ae5f5f07fd6a1b111e533ed18534fbb8698712 \
  kotoba_aiueos_user_object_journal_build
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/user-object-journal-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$user_object_journal_valid_tmp"
cmp "$aiueos/kotoba/user-object-journal-valid.o" "$user_object_journal_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$user_object_journal_valid_tmp" \
  d1faea1e1446651bfa7cbf1927b6b2add539dd6fde47b781f8bab7a933f0e30d \
  kotoba_aiueos_user_object_journal_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/user-object-journal-value.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$user_object_journal_value_tmp"
cmp "$aiueos/kotoba/user-object-journal-value.o" "$user_object_journal_value_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$user_object_journal_value_tmp" \
  d96960555b01642a1b2204b2e2b73a0d33de522ce01293ba5fca64c4338994a6 \
  kotoba_aiueos_user_object_journal_value
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/aiueos/sha256.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$sha256_tmp"
cmp "$aiueos/kotoba/sha256.o" "$sha256_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$sha256_tmp" \
  af378b061725473bf4aa66d02d276973ffc5c7cef4b0ed1f4a0e01fc754a7753 \
  kotoba_aiueos_sha256
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/aiueos/digest_equal.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$digest_equal_tmp"
cmp "$aiueos/kotoba/digest-equal.o" "$digest_equal_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$digest_equal_tmp" \
  6156db8b78f883610521ac4eb458cb98df655b26087e7d6808279c8b9d927b78 \
  kotoba_aiueos_digest_equal
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/app-catalog-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$catalog_valid_tmp"
cmp "$aiueos/kotoba/app-catalog-valid.o" "$catalog_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$catalog_valid_tmp" \
  cc965586258815beeac08c6cf2ca4debcd5fa7ea99f9d230452fe6eab962e7d6 \
  kotoba_aiueos_app_catalog_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/app-lookup-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$app_lookup_tmp"
cmp "$aiueos/kotoba/app-lookup-plan.o" "$app_lookup_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$app_lookup_tmp" \
  ca8a261b5a967237c602912c1f945404baa5b6e9aba678fe37450633dcd587d9 \
  kotoba_aiueos_app_lookup_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/user-elf-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$user_elf_valid_tmp"
cmp "$aiueos/kotoba/user-elf-valid.o" "$user_elf_valid_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$user_elf_valid_tmp" \
  d79cc375b46a6bc7c482e05c9f2e859f62c7a6ce186a8762b5161c2f2a426534 \
  kotoba_aiueos_user_elf_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/user-context-build.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$user_context_tmp"
cmp "$aiueos/kotoba/user-context-build.o" "$user_context_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$user_context_tmp" \
  66955e000a4b5f8a80ab97c031522e32e427cc141c6f9702f956aabce66d657f \
  kotoba_aiueos_user_context_build
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/page-mapping-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$mapping_plan_tmp"
cmp "$aiueos/kotoba/page-mapping-plan.o" "$mapping_plan_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$mapping_plan_tmp" \
  34de7a17f3bd3d1314815bc2ebab86d668001707b74164cbaaacef966b8d5ef1 \
  kotoba_aiueos_page_mapping_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/process-create-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$process_plan_tmp"
cmp "$aiueos/kotoba/process-create-plan.o" "$process_plan_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$process_plan_tmp" \
  d9fcc49f43351e666636f0145bd15e67e8054f1bb2a453c687e6d5dc9a0c42ce \
  kotoba_aiueos_process_create_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/process-teardown-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$teardown_plan_tmp"
cmp "$aiueos/kotoba/process-teardown-plan.o" "$teardown_plan_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$teardown_plan_tmp" \
  bd3e12cd46665caedb36ee6e836644309874fdbf67a8d7702e206833cb46f6e7 \
  kotoba_aiueos_process_teardown_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/task-slot-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$task_plan_tmp"
cmp "$aiueos/kotoba/task-slot-plan.o" "$task_plan_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$task_plan_tmp" \
  df56b4eb01d25d512da5d9db8352299f66d2dd8c6e794129d3e40dfb88a23cb5 \
  kotoba_aiueos_task_slot_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/scheduler-dispatch-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$dispatch_plan_tmp"
cmp "$aiueos/kotoba/scheduler-dispatch-plan.o" "$dispatch_plan_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$dispatch_plan_tmp" \
  fb74d5e17d67d6e494601bc523a616e498e80c09d5f76bf802a268b418f3fd14 \
  kotoba_aiueos_scheduler_dispatch_plan
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/task-exit-route.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$exit_route_tmp"
cmp "$aiueos/kotoba/task-exit-route.o" "$exit_route_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$exit_route_tmp" \
  db3c7e138fec3f34593d717ecd250ca9297f5eb5d653622565bb74d3ccd595a9 \
  kotoba_aiueos_task_exit_route
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/service-task-transition.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$service_task_tmp"
cmp "$aiueos/kotoba/service-task-transition.o" "$service_task_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$service_task_tmp" \
  8b2794d08387dfb55c739ccf8e7082425282fb0975b31b14090cc57e4dcac854 \
  kotoba_aiueos_service_task_transition
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/rsa2048.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$rsa2048_tmp"
cmp "$aiueos/kotoba/rsa2048.o" "$rsa2048_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$rsa2048_tmp" \
  b48dc4edec96fc109d89570bbd872d0dc525a1b536ee84dc90c1c1671c6d15e9 \
  kotoba_aiueos_rsa2048_sha256_verify
# DHCPv4 (ADR-0076). Placed before the known-failing entry below so that a
# `set -e` exit there cannot be mistaken for these not having been checked.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/dhcp-reply-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$dhcp_reply_tmp"
cmp "$aiueos/kotoba/dhcp-reply-valid.o" "$dhcp_reply_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$dhcp_reply_tmp" \
  ceecb05c3400535ccff22509d2fc1426eb9166c2d79a93ae952377a0f4bc5951 \
  kotoba_aiueos_dhcp_reply_valid
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/dhcp-option-u32.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$dhcp_option_tmp"
cmp "$aiueos/kotoba/dhcp-option-u32.o" "$dhcp_option_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$dhcp_option_tmp" \
  0b5341000376104c6a23d2e6ef89c05c08fd03e91d2c2aa905643c65604741a0 \
  kotoba_aiueos_dhcp_option_u32
# ECDSA P-256 / SHA-256 (ADR-0087). Compiled at this same 9cf3a0a pin
# with the native allow-list + imm32 fuel that later landed as
# kotoba-native e570d78. Same DHCP pattern: do not wholesale-advance amu.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/ecdsa-p256.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$ecdsa_tmp"
cmp "$aiueos/kotoba/ecdsa-p256.o" "$ecdsa_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$ecdsa_tmp" \
  5026b4346bdb02ba689fad3afe67f21e556ca028b03338764140079f0308dc29 \
  kotoba_aiueos_ecdsa_p256_sha256_verify
# Guest IME (ADR-0090). Compiled at this same 9cf3a0a pin with the native
# allow-list that later lands as kotoba-native + `aiueos-ime-commit`.
# Same DHCP/ECDSA pattern: do not wholesale-advance amu.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/ime-romaji.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$ime_tmp"
cmp "$aiueos/kotoba/ime-romaji.o" "$ime_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$ime_tmp" \
  ee11f50c9dfb30d03c820bead466b2f1bf18e4e64f3a2bfda98f5a5dd5d4ca34 \
  kotoba_aiueos_ime_commit
# Guest WM (ADR-0091). Same 9cf3a0a pin + native allow-list `aiueos-wm-hit`.
# Do not wholesale-advance amu.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/wm-hit.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$wm_tmp"
cmp "$aiueos/kotoba/wm-hit.o" "$wm_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$wm_tmp" \
  70fac07783c5b2841b76d9d599c03a97a44d290a8ad977f48aa5af39b21efc7f \
  kotoba_aiueos_wm_hit
# Guest scanout-two (ADR-0095). Same 9cf3a0a pin + native allow-list
# `aiueos-scanout-bind`. JVM loads elf64.clj over elf64.cljc; the row
# must exist in the .clj file. Do not wholesale-advance amu.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/scanout-bind.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$scanout_tmp"
cmp "$aiueos/kotoba/scanout-bind.o" "$scanout_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$scanout_tmp" \
  5ca924dff9fe42620f2313d16f8f62018d9bfbf588c7b142383066cce65d8305 \
  kotoba_aiueos_scanout_bind
# Guest permission broker (ADR-0096). Same 9cf3a0a pin + native allow-list
# `aiueos-broker-admit`. JVM loads elf64.clj over elf64.cljc; the row
# must exist in the .clj file. Do not wholesale-advance amu.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/broker-admit.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$broker_tmp"
cmp "$aiueos/kotoba/broker-admit.o" "$broker_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$broker_tmp" \
  713bdc8e4c3d41ea9602fe9184741c15bd7a7b71d6f1b688a766a2d83714a48f \
  kotoba_aiueos_broker_admit
# Guest session restore (ADR-0098). Same 9cf3a0a pin + native allow-list
# `aiueos-session-restore`. JVM loads elf64.clj over elf64.cljc; the row
# must exist in the .clj file. Do not wholesale-advance amu.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/session-restore.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$session_tmp"
cmp "$aiueos/kotoba/session-restore.o" "$session_tmp"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$session_tmp" \
  1983e5fa9026b2a356a4c43f6fa84630f6261ebd50c9939c4d657a326659048b \
  kotoba_aiueos_session_restore
# NOT REPRODUCIBLE at the pinned revision, and the only one left that is not.
#
# Both files are 8560 bytes and 541 of them differ. The segment size field at
# offset 0x60 reads 0x244 in the committed ELF and 0x2f2 in a fresh build, so
# the pinned compiler emits 754 bytes of code where the committed artifact
# carries 580; the file size matches only because padding absorbs it.
#
# That runs OPPOSITE to every kernel object above. Those were committed by
# something that emitted MORE code than the old pin, which is why advancing the
# pin fixed them. This one was committed by something that emitted LESS. The
# artifacts were not all built by the same compiler revision, and no single
# revision has been found that reproduces all of them.
#
# It is also the only entry here on a different target
# (x86_64-aiueos-user-v1) and the only one that takes a policy file.
#
# Left failing rather than removed or re-pinned. Removing it makes the script
# pass while checking less; re-pinning the digest records a number nobody has
# justified.
"$compiler/bin/kotoba-compiler" compile "$aiueos/kotoba/user-smoke.kotoba" \
  --target x86_64-aiueos-user-v1 --policy "$aiueos/kotoba/user-runtime-policy.edn" \
  --output "$user_elf_tmp"
cmp "$aiueos/kotoba/user-smoke.elf" "$user_elf_tmp"
python3 "$aiueos/scripts/verify-kotoba-user-elf.py" "$user_elf_tmp" \
  1f0e5897831d0de6bbcb15eec82a6e0c4b402b436689cec051bc6de3b5c4e905
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$service_registry_tmp" \
  b0e9c90aaef5477fb5ababd6dd3067dd95a7eba93f3bb262cc49bace7e5a44ce \
  kotoba_aiueos_service_registry_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$service_registry_state_tmp" \
  d73f13de0d86a4af46e33516b8b0f6358b5d477307c61d40624b971f34c15f3e \
  kotoba_aiueos_service_registry_state
echo "AIUEOS_KOTOBA_REPRODUCIBLE_OK compiler=$actual"
