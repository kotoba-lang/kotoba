#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
esp="$out/esp"
efi="$esp/EFI/BOOT/BOOTX64.EFI"
object="$out/uefi-main.obj"
model_slots_object="$out/uefi-model-slots.obj"
identity_source="$out/kernel-identity.c"
identity_object="$out/kernel-identity.obj"
model_identity_header="$out/aiueos-model-identity.h"
build_identity_header="$out/aiueos-build-identity.h"
embedded_source="$out/embedded-release.S"
embedded_object="$out/embedded-release.obj"
kernel_dir="$esp/EFI/AIUEOS"
kernel="$kernel_dir/KERNEL.ELF"
kernel_object="$out/kernel-main.o"
kernel_entry_object="$out/kernel-entry.o"
kernel_paging_object="$out/kernel-paging.o"
kernel_acpi_object="$out/kernel-acpi.o"
kernel_vtd_object="$out/kernel-vtd.o"
kernel_apic_object="$out/kernel-apic.o"
kernel_memory_object="$out/kernel-memory.o"
kernel_pci_object="$out/kernel-pci.o"
kernel_rtl8125_object="$out/kernel-rtl8125.o"
kernel_micro_infer_object="$out/kernel-micro-infer.o"
kernel_inference_status_object="$out/kernel-inference-status.o"
kernel_device_result_object="$out/kernel-device-result.o"
kernel_device_worker_protocol_object="$out/kernel-device-worker-protocol.o"
kernel_model_handoff_object="$out/kernel-model-handoff.o"
# C-free wave 1 (ADR-0219): the decisions of inference_status.c,
# model_handoff.c and device_worker_protocol.c as flat-record objects. The
# C files still exist and are marshalling only -- they pack the struct into
# the record the object reads and call the symbol; kernel/main.c,
# framebuffer.c, paging.c and pci.c call the C as before.
kotoba_inference_status_valid_object=${AIUEOS_KOTOBA_INFERENCE_STATUS_VALID_OBJECT:-"$aiueos/kotoba/inference-status-valid.o"}
kotoba_inference_rate_object=${AIUEOS_KOTOBA_INFERENCE_RATE_OBJECT:-"$aiueos/kotoba/inference-milli-tokens-per-second.o"}
kotoba_model_mapping_plan_object=${AIUEOS_KOTOBA_MODEL_MAPPING_PLAN_OBJECT:-"$aiueos/kotoba/model-mapping-plan.o"}
kotoba_model_handoff_validate_object=${AIUEOS_KOTOBA_MODEL_HANDOFF_VALIDATE_OBJECT:-"$aiueos/kotoba/model-handoff-validate.o"}
kotoba_device_worker_poll_object=${AIUEOS_KOTOBA_DEVICE_WORKER_POLL_OBJECT:-"$aiueos/kotoba/device-worker-poll-response.o"}
# C-free wave 2 (ADR-0220): job_protocol.c's four wire lines behind one mode
# word, micro_infer.c's decision over the shared native.micro-infer table,
# and tls_aes_gcm.c's known-answer test over the shared AES-GCM core. The C
# files are marshalling only.
kotoba_job_protocol_object=${AIUEOS_KOTOBA_JOB_PROTOCOL_OBJECT:-"$aiueos/kotoba/job-protocol-dispatch.o"}
kotoba_micro_infer_next_object=${AIUEOS_KOTOBA_MICRO_INFER_NEXT_OBJECT:-"$aiueos/kotoba/micro-infer-next.o"}
kotoba_aes128_gcm_selftest_object=${AIUEOS_KOTOBA_AES128_GCM_SELFTEST_OBJECT:-"$aiueos/kotoba/aes128-gcm-selftest.o"}
kernel_qwen35_runtime_object="$out/kernel-qwen35-runtime.o"
kernel_qwen35_quant_object="$out/kernel-qwen35-quant.o"
kernel_qwen35_infer_object="$out/kernel-qwen35-infer.o"
kernel_kototama_runtime_object="$out/kernel-kototama-runtime.o"
kernel_job_protocol_object="$out/kernel-job-protocol.o"
kernel_tls_aes_object="$out/kernel-tls-aes-gcm.o"
kernel_tls13_object="$out/kernel-tls13.o"
kernel_scheduler_object="$out/kernel-scheduler.o"
kernel_syscall_object="$out/kernel-syscall.o"
kernel_process_object="$out/kernel-process.o"
kernel_loader_object="$out/kernel-loader.o"
kernel_smp_object="$out/kernel-smp.o"
kernel_trampoline_object="$out/kernel-ap-trampoline.o"
kernel_ioapic_object="$out/kernel-ioapic.o"
kernel_framebuffer_object="$out/kernel-framebuffer.o"
kernel_plc_runtime_object="$out/kernel-plc-runtime.o"
kernel_plc_embedded_object="$out/kernel-plc-embedded.o"
kernel_qualification_object="$out/kernel-qualification.o"
kernel_qualification_entry_object="$out/kernel-qualification-entry.o"
kotoba_kernel_object=${AIUEOS_KOTOBA_KERNEL_OBJECT:-"$aiueos/kotoba/kernel-probe.o"}
kotoba_journal_object=${AIUEOS_KOTOBA_JOURNAL_OBJECT:-"$aiueos/kotoba/journal-plan.o"}
kotoba_fnv_object=${AIUEOS_KOTOBA_FNV_OBJECT:-"$aiueos/kotoba/fnv1a.o"}
kotoba_journal_valid_object=${AIUEOS_KOTOBA_JOURNAL_VALID_OBJECT:-"$aiueos/kotoba/journal-record-valid.o"}
kotoba_transaction_valid_object=${AIUEOS_KOTOBA_TRANSACTION_VALID_OBJECT:-"$aiueos/kotoba/object-transaction-valid.o"}
kotoba_transaction_route_object=${AIUEOS_KOTOBA_TRANSACTION_ROUTE_OBJECT:-"$aiueos/kotoba/object-transaction-route.o"}
kotoba_mutable_valid_object=${AIUEOS_KOTOBA_MUTABLE_VALID_OBJECT:-"$aiueos/kotoba/mutable-object-valid.o"}
kotoba_superblock_valid_object=${AIUEOS_KOTOBA_SUPERBLOCK_VALID_OBJECT:-"$aiueos/kotoba/superblock-valid.o"}
kotoba_journal_build_object=${AIUEOS_KOTOBA_JOURNAL_BUILD_OBJECT:-"$aiueos/kotoba/journal-record-build.o"}
kotoba_mutable_build_object=${AIUEOS_KOTOBA_MUTABLE_BUILD_OBJECT:-"$aiueos/kotoba/mutable-object-build.o"}
kotoba_cap_valid_object=${AIUEOS_KOTOBA_CAP_VALID_OBJECT:-"$aiueos/kotoba/virtio-cap-valid.o"}
kotoba_extent_valid_object=${AIUEOS_KOTOBA_EXTENT_VALID_OBJECT:-"$aiueos/kotoba/pci-extent-valid.o"}
kotoba_region_valid_object=${AIUEOS_KOTOBA_REGION_VALID_OBJECT:-"$aiueos/kotoba/pci-region-valid.o"}
kotoba_pci_config_read_object=${AIUEOS_KOTOBA_PCI_CONFIG_READ_OBJECT:-"$aiueos/kotoba/pci-config-read.o"}
# The RTL8125 2.5GbE driver (ADR-0140). Six objects, always linked: the NIC is
# how a diskless PXE node reaches anything at all, and `kernel/rtl8125.c` is in
# every profile. `aiueos_rtl8125_kotoba_selftest` runs all six against a
# software model of the BAR on every boot, so an unlinked one is a link error
# rather than a silent absence.
kotoba_rtl8125_identify_object=${AIUEOS_KOTOBA_RTL8125_IDENTIFY_OBJECT:-"$aiueos/kotoba/rtl8125-identify.o"}
kotoba_rtl8125_link_up_object=${AIUEOS_KOTOBA_RTL8125_LINK_UP_OBJECT:-"$aiueos/kotoba/rtl8125-link-up.o"}
kotoba_rtl8125_ring_build_object=${AIUEOS_KOTOBA_RTL8125_RING_BUILD_OBJECT:-"$aiueos/kotoba/rtl8125-ring-build.o"}
kotoba_rtl8125_program_object=${AIUEOS_KOTOBA_RTL8125_PROGRAM_OBJECT:-"$aiueos/kotoba/rtl8125-program.o"}
kotoba_rtl8125_tx_submit_object=${AIUEOS_KOTOBA_RTL8125_TX_SUBMIT_OBJECT:-"$aiueos/kotoba/rtl8125-tx-submit.o"}
kotoba_rtl8125_rx_poll_object=${AIUEOS_KOTOBA_RTL8125_RX_POLL_OBJECT:-"$aiueos/kotoba/rtl8125-rx-poll.o"}
kotoba_pci_config_write_object=${AIUEOS_KOTOBA_PCI_CONFIG_WRITE_OBJECT:-"$aiueos/kotoba/pci-config-write.o"}
kotoba_mmio_map_admit_object=${AIUEOS_KOTOBA_MMIO_MAP_ADMIT_OBJECT:-"$aiueos/kotoba/mmio-map-admit.o"}
kotoba_acpi_checksum_object=${AIUEOS_KOTOBA_ACPI_CHECKSUM_OBJECT:-"$aiueos/kotoba/acpi-checksum-ok.o"}
kotoba_acpi_table_valid_object=${AIUEOS_KOTOBA_ACPI_TABLE_VALID_OBJECT:-"$aiueos/kotoba/acpi-table-valid.o"}
kotoba_vtd_admit_object=${AIUEOS_KOTOBA_VTD_ADMIT_OBJECT:-"$aiueos/kotoba/vtd-admit.o"}
kotoba_msr_read_object=${AIUEOS_KOTOBA_MSR_READ_OBJECT:-"$aiueos/kotoba/msr-read.o"}
kotoba_msr_write_object=${AIUEOS_KOTOBA_MSR_WRITE_OBJECT:-"$aiueos/kotoba/msr-write.o"}
kotoba_idt_gate_object=${AIUEOS_KOTOBA_IDT_GATE_OBJECT:-"$aiueos/kotoba/idt-gate-build.o"}
# kernel/main.c now quiets the legacy 8259 through this object before the first
# `sti`. Until now this path never masked the PIC at all and was green only
# because OVMF does it before handoff (ADR-0028 fixed the Multiboot path only).
kotoba_pic_disable_object=${AIUEOS_KOTOBA_PIC_DISABLE_OBJECT:-"$aiueos/kotoba/pic-disable.o"}
# The six hand-written `cpuid` sites in this kernel asked THREE questions, and
# only two were feature tests, so they become three objects rather than one
# generic accessor -- the knowledge of which leaf and which bit answers a
# question is the decision, and a `(leaf, bit)` parameter pair would have left
# it as magic numbers at the C call site. This path compiles all three of the C
# files involved (paging.c, process.c, pci.c below), so it links all three:
#   cpu-feature-nx       paging.c   leaf 0x80000001 EDX bit 20
#   cpu-feature-syscall  process.c  leaf 0x80000001 EDX bit 11
#   cpu-apic-id          pci.c      leaf 1 EBX 31:24 -- an ID, not a feature
# The Multiboot path compiles NONE of those three files and links none of these.
kotoba_cpu_feature_nx_object=${AIUEOS_KOTOBA_CPU_FEATURE_NX_OBJECT:-"$aiueos/kotoba/cpu-feature-nx.o"}
kotoba_cpu_feature_syscall_object=${AIUEOS_KOTOBA_CPU_FEATURE_SYSCALL_OBJECT:-"$aiueos/kotoba/cpu-feature-syscall.o"}
kotoba_cpu_apic_id_object=${AIUEOS_KOTOBA_CPU_APIC_ID_OBJECT:-"$aiueos/kotoba/cpu-apic-id.o"}
kotoba_syscall_range_object=${AIUEOS_KOTOBA_SYSCALL_RANGE_OBJECT:-"$aiueos/kotoba/syscall-range-valid.o"}
kotoba_copy_in_object=${AIUEOS_KOTOBA_COPY_IN_OBJECT:-"$aiueos/kotoba/copy-in.o"}
kotoba_allocator_plan_object=${AIUEOS_KOTOBA_ALLOCATOR_PLAN_OBJECT:-"$aiueos/kotoba/allocator-plan.o"}
kotoba_capability_object=${AIUEOS_KOTOBA_CAPABILITY_OBJECT:-"$aiueos/kotoba/capability-plan.o"}
kotoba_capability_mutation_object=${AIUEOS_KOTOBA_CAPABILITY_MUTATION_OBJECT:-"$aiueos/kotoba/capability-mutation-plan.o"}
kotoba_service_lifecycle_object=${AIUEOS_KOTOBA_SERVICE_LIFECYCLE_OBJECT:-"$aiueos/kotoba/service-lifecycle.o"}
kotoba_service_registry_object=${AIUEOS_KOTOBA_SERVICE_REGISTRY_OBJECT:-"$aiueos/kotoba/service-registry-build.o"}
kotoba_service_registry_state_object=${AIUEOS_KOTOBA_SERVICE_REGISTRY_STATE_OBJECT:-"$aiueos/kotoba/service-registry-state.o"}
kotoba_user_object_journal_object=${AIUEOS_KOTOBA_USER_OBJECT_JOURNAL_OBJECT:-"$aiueos/kotoba/user-object-journal-build.o"}
kotoba_user_object_journal_valid_object=${AIUEOS_KOTOBA_USER_OBJECT_JOURNAL_VALID_OBJECT:-"$aiueos/kotoba/user-object-journal-valid.o"}
kotoba_user_object_journal_value_object=${AIUEOS_KOTOBA_USER_OBJECT_JOURNAL_VALUE_OBJECT:-"$aiueos/kotoba/user-object-journal-value.o"}
kotoba_sha256_object=${AIUEOS_KOTOBA_SHA256_OBJECT:-"$aiueos/kotoba/sha256.o"}
# tokenizer: the three objects that turn a prompt into token ids and back
# (ADR-0135). They are in the image and NOTHING CALLS THEM YET -- kernel/
# qwen35_infer.c takes a single BOS id and has no tokenizer at all, so there is
# no C function here to replace. Linking them now makes wiring the prompt path
# a change to the C that calls them rather than a change to what the image
# contains, and keeps them under the same per-object export and relocation
# check as every other Kotoba object.
kotoba_qwen35_vocab_index_object=${AIUEOS_KOTOBA_QWEN35_VOCAB_INDEX_OBJECT:-"$aiueos/kotoba/qwen35-vocab-index-build.o"}
kotoba_qwen35_tokenize_object=${AIUEOS_KOTOBA_QWEN35_TOKENIZE_OBJECT:-"$aiueos/kotoba/qwen35-tokenize.o"}
kotoba_qwen35_detokenize_object=${AIUEOS_KOTOBA_QWEN35_DETOKENIZE_OBJECT:-"$aiueos/kotoba/qwen35-detokenize.o"}
kotoba_digest_equal_object=${AIUEOS_KOTOBA_DIGEST_EQUAL_OBJECT:-"$aiueos/kotoba/digest-equal.o"}
kotoba_catalog_valid_object=${AIUEOS_KOTOBA_CATALOG_VALID_OBJECT:-"$aiueos/kotoba/app-catalog-valid.o"}
kotoba_app_lookup_object=${AIUEOS_KOTOBA_APP_LOOKUP_OBJECT:-"$aiueos/kotoba/app-lookup-plan.o"}
kotoba_user_elf_valid_object=${AIUEOS_KOTOBA_USER_ELF_VALID_OBJECT:-"$aiueos/kotoba/user-elf-valid.o"}
# The rebuild (23dd642) replaced this object's bytes: the digest tracks the
# committed os/aiueos/kotoba/user-elf-valid.o (ab027deff...), not the
# pre-rebuild d79cc375... the PLC branch used to pin here. The PLC-RT-SMOKE
# override below still swaps in plc-user-elf-valid.o with its own digest.
kotoba_user_elf_valid_sha=941707062dcdd34c77c0bb1794126589cd83ff2d58d1b9c04eb066ba509ff8d2
kotoba_user_context_object=${AIUEOS_KOTOBA_USER_CONTEXT_OBJECT:-"$aiueos/kotoba/user-context-build.o"}
# The kernel-selector twin of the object above, for tasks `iret` enters at ring
# 0. Same 160-byte frame in the same bounded 4 KiB stack; CS 0x08 / SS 0x10 and
# an RSP that is the top of that very stack rather than a separate user stack,
# eight bytes lower than the ring-3 frame because `iret` lands in an ordinary C
# function and must reproduce the RSP % 16 == 8 that `call` would have left.
# Both twins are linked here because this path is the one that compiles
# kernel/scheduler.c, which owns both entry points.
kotoba_kernel_context_object=${AIUEOS_KOTOBA_KERNEL_CONTEXT_OBJECT:-"$aiueos/kotoba/kernel-context-build.o"}
kotoba_mapping_plan_object=${AIUEOS_KOTOBA_MAPPING_PLAN_OBJECT:-"$aiueos/kotoba/page-mapping-plan.o"}
kotoba_process_plan_object=${AIUEOS_KOTOBA_PROCESS_PLAN_OBJECT:-"$aiueos/kotoba/process-create-plan.o"}
kotoba_teardown_plan_object=${AIUEOS_KOTOBA_TEARDOWN_PLAN_OBJECT:-"$aiueos/kotoba/process-teardown-plan.o"}
kotoba_task_plan_object=${AIUEOS_KOTOBA_TASK_PLAN_OBJECT:-"$aiueos/kotoba/task-slot-plan.o"}
kotoba_dispatch_plan_object=${AIUEOS_KOTOBA_DISPATCH_PLAN_OBJECT:-"$aiueos/kotoba/scheduler-dispatch-plan.o"}
kotoba_rt_dispatch_plan_object=${AIUEOS_KOTOBA_RT_DISPATCH_PLAN_OBJECT:-"$aiueos/kotoba/rt-scheduler-dispatch-plan.o"}
kotoba_exit_route_object=${AIUEOS_KOTOBA_EXIT_ROUTE_OBJECT:-"$aiueos/kotoba/task-exit-route.o"}
kotoba_service_task_object=${AIUEOS_KOTOBA_SERVICE_TASK_OBJECT:-"$aiueos/kotoba/service-task-transition.o"}
kotoba_rsa2048_object=${AIUEOS_KOTOBA_RSA2048_OBJECT:-"$aiueos/kotoba/rsa2048.o"}
kotoba_x25519_object=${AIUEOS_KOTOBA_X25519_OBJECT:-"$aiueos/kotoba/x25519.o"}
kotoba_ecdsa_object=${AIUEOS_KOTOBA_ECDSA_OBJECT:-"$aiueos/kotoba/ecdsa-p256.o"}
# Qwen3.8-27B GGUF admission (ADR-0137). Three objects, linked only by the
# model-handoff profile because nothing else parses a model. They replace the
# whole of kernel/qwen35_runtime.c's parser: with
# -DAIUEOS_QWEN35_KOTOBA_ADMISSION that file compiles to buffer plumbing and a
# translation into struct aiueos_qwen35_model, and its C parser is not in the
# image at all.
kotoba_qwen35_header_object=${AIUEOS_KOTOBA_QWEN35_HEADER_OBJECT:-"$aiueos/kotoba/qwen35-gguf-header-valid.o"}
kotoba_qwen35_kv_object=${AIUEOS_KOTOBA_QWEN35_KV_OBJECT:-"$aiueos/kotoba/qwen35-gguf-kv-scan.o"}
kotoba_qwen35_tensor_object=${AIUEOS_KOTOBA_QWEN35_TENSOR_OBJECT:-"$aiueos/kotoba/qwen35-tensor-table-bind.o"}
# The TLS 1.3 AEAD and record layer (ADR-0132, ADR-0133). Both return a REASON
# CODE and zero is success -- the C they replaced returned 1 for success, so a
# transcribed `if (call(...))` accepts exactly what they refuse.
# `hkdf-sha256.o` is deliberately NOT here, but the reason has CHANGED. It used
# not to return on this machine (ADR-0134); ADR-0190 found why -- a reentry
# parameter's spill store spliced before the loop header -- and the 2026-09-03
# rebuild at amu 6c245f69 cleared it: `verify-loop-parameter-homes` reports
# BASELINE-CLEARED for hkdf-sha256.o, and its baseline entry is gone. What is
# left is the second half of the old reason and it still holds: nothing in the
# kernel calls `kotoba_aiueos_hkdf_sha256`, so linking it would put a 13 KiB
# artifact in the image to no end. Adding the call site is the TLS stream's
# stage 4; this line is not the blocker any more.
kotoba_aes128_gcm_object=${AIUEOS_KOTOBA_AES128_GCM_OBJECT:-"$aiueos/kotoba/aes128-gcm.o"}
kotoba_tls13_record_object=${AIUEOS_KOTOBA_TLS13_RECORD_OBJECT:-"$aiueos/kotoba/tls13-record.o"}
# The two project-route objects (ADR-0141). NOT LINKED, and that is a decision
# about the kernel rather than an omission: nothing in the kernel calls
# `kotoba_aiueos_cid_v1_admit` or `kotoba_aiueos_value_runtime_cas_verify` yet.
# They are verified here anyway, exactly as the qwen35 objects below are,
# because the digest is what ties the committed artifact to the source its
# contract graded -- and until amu#742 neither could be built at all.
kotoba_cid_v1_admit_object=${AIUEOS_KOTOBA_CID_V1_ADMIT_OBJECT:-"$aiueos/kotoba/cid-v1-admit.o"}
kotoba_value_runtime_cas_verify_object=${AIUEOS_KOTOBA_VALUE_RUNTIME_CAS_VERIFY_OBJECT:-"$aiueos/kotoba/value-runtime-cas-verify.o"}
# The Qwen3.5 forward pass, first tranche (ADR-0147). Linked ONLY with the
# model handoff, because that is the only build in which the C they are
# compared against (kernel/qwen35_infer.c, kernel/qwen35_quant.c) is compiled
# at all -- linking them into every image would carry 23 KiB nothing calls.
# All three return a REASON CODE and zero is success, except the dot product,
# whose answer IS the value; see the objects' contracts.
kotoba_qwen35_dot_object=${AIUEOS_KOTOBA_QWEN35_DOT_OBJECT:-"$aiueos/kotoba/qwen35-dot-f32.o"}
kotoba_qwen35_dequant_object=${AIUEOS_KOTOBA_QWEN35_DEQUANT_OBJECT:-"$aiueos/kotoba/qwen35-dequant-row.o"}
kotoba_qwen35_matvec_object=${AIUEOS_KOTOBA_QWEN35_MATVEC_OBJECT:-"$aiueos/kotoba/qwen35-matvec.o"}
# Second tranche (ADR-0148): the scalar functions between the matvecs.
kotoba_qwen35_activation_object=${AIUEOS_KOTOBA_QWEN35_ACTIVATION_OBJECT:-"$aiueos/kotoba/qwen35-activation.o"}
kotoba_qwen35_norm_object=${AIUEOS_KOTOBA_QWEN35_NORM_OBJECT:-"$aiueos/kotoba/qwen35-norm.o"}
kotoba_qwen35_attention_object=${AIUEOS_KOTOBA_QWEN35_ATTENTION_OBJECT:-"$aiueos/kotoba/qwen35-attention.o"}
kotoba_qwen35_recurrent_object=${AIUEOS_KOTOBA_QWEN35_RECURRENT_OBJECT:-"$aiueos/kotoba/qwen35-recurrent-step.o"}
kotoba_qwen35_rope_object=${AIUEOS_KOTOBA_QWEN35_ROPE_OBJECT:-"$aiueos/kotoba/qwen35-rope.o"}
qwen35_kotoba_link=
# device-client: the Murakumo device-P256 worker's signed canonical text,
# v2 and v3 (ADR-0137). Linked unconditionally, not behind
# AIUEOS_MURAKUMO_DEVICE_RESULT, because main.c's DEVCLIENT-PARITY boot
# self-test runs it on every UEFI profile -- the K16 profile is the only one
# that can send a request, and it is the one that cannot be booted here.
kotoba_device_worker_canonical_object=${AIUEOS_KOTOBA_DEVICE_WORKER_CANONICAL_OBJECT:-"$aiueos/kotoba/device-worker-canonical.o"}
# sha-stream: streaming SHA-256 (ADR-0155). Three objects over ONE shared module
# (`kotoba/aiueos/lib/sha256_stream.kotoba`), so the compression rounds exist
# once in source; three symbols because a fuel tier is a per-CALL budget and
# these three calls are not the same size.
#
# `sha256.o` above stays: it is the whole-message object that ten call sites
# in this kernel already use, and nothing here replaces it. What these add is
# the sizes it refuses: its ceiling is 12,288 bytes and `input-sha256` reaches 131,080.
#
# Linked unconditionally, like device-worker-canonical and for the same
# reason: main.c's SHA-STREAM-PARITY boot self-test runs all three on every
# UEFI profile.
kotoba_sha256_stream_object=${AIUEOS_KOTOBA_SHA256_STREAM_OBJECT:-"$aiueos/kotoba/sha256-stream.o"}
kotoba_sha256_region_object=${AIUEOS_KOTOBA_SHA256_REGION_OBJECT:-"$aiueos/kotoba/sha256-region.o"}
kotoba_device_worker_digest_object=${AIUEOS_KOTOBA_DEVICE_WORKER_DIGEST_OBJECT:-"$aiueos/kotoba/device-worker-digest.o"}
# ECDSA P-256 deterministic sign (ADR-0105). Linked ONLY when
# AIUEOS_ECDSA_SIGN_KAT=1 -- it is ~50 KiB and the kernel is near its 1 MiB
# ceiling, so it stays out of the default and the SSH-listener builds until the
# sshd needs it. Regenerate the object with
# scripts/reproduce-ecdsa-sign-object.clj (the pinned amu needs the
# kernel-object-entries + 250M fuel-tier patch that recipe applies).
kotoba_ecdsa_sign_object=${AIUEOS_KOTOBA_ECDSA_SIGN_OBJECT:-"$aiueos/kotoba/ecdsa-p256-sign.o"}
kotoba_ecdsa_public_object=${AIUEOS_KOTOBA_ECDSA_PUBLIC_OBJECT:-"$aiueos/kotoba/ecdsa-p256-public.o"}
ecdsa_sign_link=
ecdsa_public_link=
device_result_link=
# Linked for the sign KAT and, now, for the SSH listener build: net_ssh_kex
# signs the exchange hash H with it (ADR-0107). Listener+sign measured at
# 1,043,688 bytes -- under the 1 MiB ceiling, so ADR-0105's separation is
# lifted for the SSH build (the KAT keeps its own flag for the KAT code only).
# ADR-0270: the guest-browser build signs and verifies the lock's passkey ceremony, so it links the sign and public objects too.
if [ "${AIUEOS_ECDSA_SIGN_KAT:-0}" = 1 ] || [ "${AIUEOS_SSH_LISTEN:-0}" = 1 ] ||
   [ "${AIUEOS_GUEST_BROWSER:-0}" = 1 ] || [ "${AIUEOS_MURAKUMO_DEVICE_RESULT:-0}" = 1 ] ||
   [ "${AIUEOS_KERNEL_SIZE_BUILD:-0}" = 1 ] || [ "${AIUEOS_KERNEL_SIZE_DEFINE:-0}" = 1 ]; then
  ecdsa_sign_link="$kotoba_ecdsa_sign_object"
fi
if [ "${AIUEOS_MURAKUMO_DEVICE_RESULT:-0}" = 1 ] || [ "${AIUEOS_GUEST_BROWSER:-0}" = 1 ] ||
   [ "${AIUEOS_ECDSA_PUBLIC_KAT:-0}" = 1 ] || [ "${AIUEOS_KERNEL_SIZE_BUILD:-0}" = 1 ] ||
   [ "${AIUEOS_KERNEL_SIZE_DEFINE:-0}" = 1 ]; then
  ecdsa_public_link="$kotoba_ecdsa_public_object"
fi
if [ "${AIUEOS_MURAKUMO_DEVICE_RESULT:-0}" = 1 ]; then
  device_result_link="$kernel_device_result_object $kernel_device_worker_protocol_object $kotoba_device_worker_poll_object"
fi
physical_qualification_cflags=
physical_network_qualification_cflags=
physical_direct_https_qualification_cflags=
physical_relay_qualification_cflags=
physical_job_qualification_cflags=
murakumo_device_result_cflags=
persistent_boot_cflags=
qualification_link=
qualification_gc_link=
gop_discovery_cflags=
loader_failure_test_cflags=
loader_hang_test_cflags=
qualification_watchdog_cflags=
kernel_hang_test_cflags=
embedded_release_cflags=
netboot_qualification_cflags=
embedded_release_link=
if [ "${AIUEOS_PHYSICAL_QUALIFICATION:-0}" = 1 ]; then
  physical_qualification_cflags="-DAIUEOS_PHYSICAL_QUALIFICATION=1"
  qualification_link="$kernel_qualification_entry_object $kernel_qualification_object"
  qualification_gc_link="--gc-sections"
fi
if [ "${AIUEOS_PERSISTENT_BOOT:-0}" = 1 ]; then
  [ "${AIUEOS_PHYSICAL_QUALIFICATION:-0}" = 1 ] || {
    echo "error: persistent boot requires physical qualification" >&2
    exit 1
  }
  persistent_boot_cflags="-DAIUEOS_PERSISTENT_BOOT=1"
fi
if [ "${AIUEOS_PHYSICAL_NETWORK_QUALIFICATION:-0}" = 1 ]; then
  [ "${AIUEOS_PHYSICAL_QUALIFICATION:-0}" = 1 ] || {
    echo "error: physical network qualification requires physical qualification" >&2
    exit 1
  }
  physical_network_qualification_cflags="-DAIUEOS_PHYSICAL_NETWORK_QUALIFICATION=1"
fi
if [ "${AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION:-0}" = 1 ]; then
  [ "${AIUEOS_PHYSICAL_NETWORK_QUALIFICATION:-0}" = 1 ] || {
    echo "error: physical direct HTTPS qualification requires physical network qualification" >&2
    exit 1
  }
  physical_direct_https_qualification_cflags="-DAIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=1"
fi
if [ -n "$device_result_link" ]; then
  [ "${AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION:-0}" = 1 ] || {
    echo "error: Murakumo device result requires physical direct HTTPS" >&2
    exit 1
  }
  [ "${AIUEOS_QWEN38_MODEL_HANDOFF:-0}" = 1 ] || {
    echo "error: Murakumo device result requires the exact Qwen3.8 model handoff" >&2
    exit 1
  }
  [ "${AIUEOS_MODEL_TEST_FIXTURE:-0}" != 1 ] || {
    echo "error: Murakumo device result refuses a model test fixture" >&2
    exit 1
  }
  murakumo_device_result_cflags="-DAIUEOS_MURAKUMO_DEVICE_RESULT=1"
fi
if [ "${AIUEOS_PHYSICAL_RELAY_QUALIFICATION:-0}" = 1 ]; then
  [ "${AIUEOS_PHYSICAL_NETWORK_QUALIFICATION:-0}" = 1 ] || {
    echo "error: physical relay qualification requires physical network qualification" >&2
    exit 1
  }
  physical_relay_qualification_cflags="-DAIUEOS_PHYSICAL_RELAY_QUALIFICATION=1"
fi
if [ "${AIUEOS_PHYSICAL_JOB_QUALIFICATION:-0}" = 1 ]; then
  [ "${AIUEOS_PHYSICAL_RELAY_QUALIFICATION:-0}" = 1 ] || {
    echo "error: physical job qualification requires physical relay qualification" >&2
    exit 1
  }
  physical_job_qualification_cflags="-DAIUEOS_PHYSICAL_JOB_QUALIFICATION=1"
fi
if [ "${AIUEOS_EMBEDDED_RELEASE:-0}" = 1 ]; then
  embedded_release_cflags="-DAIUEOS_EMBEDDED_RELEASE=1"
  embedded_release_link="$embedded_object"
fi
if [ "${AIUEOS_NETBOOT_QUALIFICATION:-0}" = 1 ]; then
  [ "${AIUEOS_PHYSICAL_QUALIFICATION:-0}" = 1 ] || {
    echo "error: netboot qualification requires AIUEOS_PHYSICAL_QUALIFICATION=1" >&2
    exit 1
  }
  [ "${AIUEOS_EMBEDDED_RELEASE:-0}" = 1 ] || {
    echo "error: netboot qualification requires AIUEOS_EMBEDDED_RELEASE=1" >&2
    exit 1
  }
  netboot_qualification_cflags="-DAIUEOS_NETBOOT_QUALIFICATION=1"
fi
if [ "${AIUEOS_GOP_FORCE_PROTOCOL_SCAN:-0}" = 1 ]; then
  gop_discovery_cflags="-DAIUEOS_GOP_FORCE_PROTOCOL_SCAN=1"
fi
if [ -n "${AIUEOS_QUALIFICATION_FORCE_LOADER_FAILURE_CODE:-}" ]; then
  loader_failure_test_cflags="-DAIUEOS_QUALIFICATION_FORCE_LOADER_FAILURE_CODE=${AIUEOS_QUALIFICATION_FORCE_LOADER_FAILURE_CODE}"
fi
qualification_watchdog_seconds=${AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS:-}
if [ -n "${AIUEOS_QUALIFICATION_FORCE_LOADER_HANG_CODE:-}" ]; then
  loader_hang_test_cflags="-DAIUEOS_QUALIFICATION_FORCE_LOADER_HANG_CODE=${AIUEOS_QUALIFICATION_FORCE_LOADER_HANG_CODE}"
  qualification_watchdog_seconds=${qualification_watchdog_seconds:-3}
fi
if [ -n "$qualification_watchdog_seconds" ]; then
  case "$qualification_watchdog_seconds" in
    *[!0-9]*|'')
      echo "error: qualification loader watchdog seconds must be an integer" >&2
      exit 1
      ;;
  esac
  [ "$qualification_watchdog_seconds" -ge 1 ] &&
    [ "$qualification_watchdog_seconds" -le 3600 ] || {
      echo "error: qualification loader watchdog seconds must be 1..3600" >&2
      exit 1
    }
  [ "${AIUEOS_PHYSICAL_QUALIFICATION:-0}" = 1 ] || {
    echo "error: qualification loader watchdog requires physical qualification" >&2
    exit 1
  }
  [ "${AIUEOS_PERSISTENT_BOOT:-0}" != 1 ] || {
    echo "error: persistent boot disables the loader watchdog" >&2
    exit 1
  }
  qualification_watchdog_cflags="-DAIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS=${qualification_watchdog_seconds}"
fi
if [ -n "${AIUEOS_QUALIFICATION_FORCE_KERNEL_HANG_CODE:-}" ]; then
  kernel_hang_test_cflags="-DAIUEOS_QUALIFICATION_FORCE_KERNEL_HANG_CODE=${AIUEOS_QUALIFICATION_FORCE_KERNEL_HANG_CODE}"
fi
kotoba_ime_object=${AIUEOS_KOTOBA_IME_OBJECT:-"$aiueos/kotoba/ime-romaji.o"}
kotoba_wm_object=${AIUEOS_KOTOBA_WM_OBJECT:-"$aiueos/kotoba/wm-hit.o"}
kotoba_scanout_object=${AIUEOS_KOTOBA_SCANOUT_OBJECT:-"$aiueos/kotoba/scanout-bind.o"}
kotoba_broker_object=${AIUEOS_KOTOBA_BROKER_OBJECT:-"$aiueos/kotoba/broker-admit.o"}
kotoba_session_object=${AIUEOS_KOTOBA_SESSION_OBJECT:-"$aiueos/kotoba/session-restore.o"}
kotoba_browser_frame_object=${AIUEOS_KOTOBA_BROWSER_FRAME_OBJECT:-"$aiueos/kotoba/browser-frame.o"}
kotoba_browser_reduce_object=${AIUEOS_KOTOBA_BROWSER_REDUCE_OBJECT:-"$aiueos/kotoba/browser-reduce.o"}
kotoba_browser_frame2_object=${AIUEOS_KOTOBA_BROWSER_FRAME2_OBJECT:-"$aiueos/kotoba/browser-frame2.o"}
kotoba_browser_ime_object=${AIUEOS_KOTOBA_BROWSER_IME_OBJECT:-"$aiueos/kotoba/browser-ime.o"}
kotoba_browser_damage_object=${AIUEOS_KOTOBA_BROWSER_DAMAGE_OBJECT:-"$aiueos/kotoba/browser-damage.o"}
kotoba_net_arp_object=${AIUEOS_KOTOBA_NET_ARP_OBJECT:-"$aiueos/kotoba/net-arp-reply-valid.o"}
kotoba_ipv4_checksum_object=${AIUEOS_KOTOBA_IPV4_CHECKSUM_OBJECT:-"$aiueos/kotoba/ipv4-checksum.o"}
kotoba_ipv4_icmp_object=${AIUEOS_KOTOBA_IPV4_ICMP_OBJECT:-"$aiueos/kotoba/ipv4-icmp-reply-valid.o"}
kotoba_tcp_checksum_object=${AIUEOS_KOTOBA_TCP_CHECKSUM_OBJECT:-"$aiueos/kotoba/tcp-checksum-ok.o"}
kotoba_tcp_segment_object=${AIUEOS_KOTOBA_TCP_SEGMENT_OBJECT:-"$aiueos/kotoba/tcp-segment-valid.o"}
kotoba_dhcp_reply_object=${AIUEOS_KOTOBA_DHCP_REPLY_OBJECT:-"$aiueos/kotoba/dhcp-reply-valid.o"}
kotoba_dhcp_option_object=${AIUEOS_KOTOBA_DHCP_OPTION_OBJECT:-"$aiueos/kotoba/dhcp-option-u32.o"}
# The murakumo relay HELLO line and ACK admission (ADR-0215). These replaced
# kernel/relay_protocol.c; pci.c calls them where it called the C.
kotoba_relay_hello_object=${AIUEOS_KOTOBA_RELAY_HELLO_OBJECT:-"$aiueos/kotoba/relay-hello-payload.o"}
kotoba_relay_ack_object=${AIUEOS_KOTOBA_RELAY_ACK_OBJECT:-"$aiueos/kotoba/relay-ack-payload-valid.o"}
kotoba_user_elf=${AIUEOS_KOTOBA_USER_ELF:-"$aiueos/kotoba/user-smoke.elf"}
kotoba_fnv_sha=
if [ -z "${AIUEOS_KOTOBA_FNV_OBJECT:-}" ]; then
  kotoba_fnv_sha=c98c7fb1e8a9bffdd8fc290d83042afd4aeda88b92ca15ac4edb9012845af507
fi
kotoba_journal_sha=
if [ -z "${AIUEOS_KOTOBA_JOURNAL_OBJECT:-}" ]; then
  kotoba_journal_sha=0b97cda6327bb330b7900dacc2a68086d7ac164244b7c1e22908a85e5d94a20f
fi
kotoba_kernel_sha=
if [ -z "${AIUEOS_KOTOBA_KERNEL_OBJECT:-}" ]; then
  kotoba_kernel_sha=3f7409bff00efaa79ec2e260b6734f740e9d7da002a9eb22a747344591e5d327
fi
input_smoke_cflags=
if [ "${AIUEOS_INPUT_SMOKE_SYNTHETIC:-0}" = 1 ]; then
  input_smoke_cflags=-DAIUEOS_INPUT_SMOKE_SYNTHETIC=1
fi
# D3: scripted touchpad gestures (pinch / three-finger swipe / two-finger tap).
# virtio-tablet has no multi-touch; see the note in pci.c.
if [ "${AIUEOS_TOUCHPAD_GESTURE_SYNTHETIC:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_TOUCHPAD_GESTURE_SYNTHETIC=1"
fi
# I2: synthetic battery probe. The reference VM has no battery device to read
# (framebuffer.c's status note), so the level state and the BAT status text
# exist only in this build -- without the flag the status band is byte-for-byte
# the one every gate's frame model already pins.
if [ "${AIUEOS_BATTERY_PROBE:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_BATTERY_PROBE=1"
fi
if [ "${AIUEOS_CATALOG_POLICY_SELFTEST:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_CATALOG_POLICY_SELFTEST=1"
fi
if [ "${AIUEOS_CRASH_RECEIPT_SMOKE:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_CRASH_RECEIPT_SMOKE=1"
fi
if [ "${AIUEOS_FAULT_RECEIPT_SMOKE:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_FAULT_RECEIPT_SMOKE=1"
fi
# ADR-0199 red/green.  1 raises a #UD at the earliest point the early fatal
# IDT covers; 2 raises the same instruction with that table compiled out,
# which is what every boot did before ADR-0199.  Never set in production.
if [ "${AIUEOS_EARLY_FAULT_SMOKE:-0}" != 0 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_EARLY_FAULT_SMOKE=${AIUEOS_EARLY_FAULT_SMOKE}"
  if [ "${AIUEOS_EARLY_FAULT_SMOKE}" = 2 ]; then
    input_smoke_cflags="$input_smoke_cflags -DAIUEOS_SKIP_EARLY_FATAL_IDT=1"
  fi
fi
# Test-only. Breaks a received DHCP reply in exactly ONE way so the gate can
# show the admission refusing it, and refusing it for the reason that was
# broken. Only kernel/pci.c is compiled with it; a value of 0 or an unset
# variable compiles none of the tampering in at all.
if [ -n "${AIUEOS_DHCP_TAMPER:-}" ] && [ "${AIUEOS_DHCP_TAMPER}" != 0 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_DHCP_TAMPER=${AIUEOS_DHCP_TAMPER}"
fi
# Test-only. Compiles the SSH passive-open listener (pci.c) and its evidence
# marker (main.c) into the kernel. Off by default so every existing gate
# builds the exact kernel it built before; the SSH gate sets it. Both main.c
# and pci.c receive input_smoke_cflags, so one flag reaches both.
if [ "${AIUEOS_SSH_LISTEN:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_SSH_LISTEN=1"
  if [ "${AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION:-0}" = 1 ]; then
    [ "${AIUEOS_MURAKUMO_DEVICE_RESULT:-0}" = 1 ] || {
      echo "error: physical SSH requires the Device-P256 identity" >&2
      exit 1
    }
    [ -n "${AIUEOS_SSH_AUTHORIZED_KEY_HEX:-}" ] || {
      echo "error: physical SSH requires AIUEOS_SSH_AUTHORIZED_KEY_HEX (public x||y only)" >&2
      exit 1
    }
  fi
  if [ -n "${AIUEOS_SSH_AUTHORIZED_KEY_HEX:-}" ]; then
    python3 "$aiueos/scripts/write-ssh-authorized-key-header.py" \
      "$AIUEOS_SSH_AUTHORIZED_KEY_HEX" "$out/aiueos-ssh-authorized-key.h"
    input_smoke_cflags="$input_smoke_cflags -DAIUEOS_SSH_AUTHORIZED_KEY_HEADER=1"
  fi
fi
# Test-only. Re-arms the end-of-boot #UD probe (aiueos#436): 54ac566 removed
# the probe so the persistent desktop loop can live past end-of-boot, which
# also removed the only producer of AIUEOS_EXCEPTION_OK vector=6 -- the
# terminal evidence smoke-qemu-uefi.sh's normal path asserts. Off by default
# so every existing gate builds the exact kernel it built before; the
# journal-recovery smoke sets it. With it, the machine ends its boot exactly
# as it always used to: the probe fires at its old slot and its handler
# writes the marker and terminates the machine through isa-debug-exit (0x30
# -> harness status 97). Gates that need the persistent loop do not set it.
if [ "${AIUEOS_SMOKE_FINAL_PROBE:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_SMOKE_FINAL_PROBE=1"
fi
# The ECDSA sign known-answer test (main.c). Its own flag so the ~50 KiB sign
# object is only linked here, not in the SSH-listener build near the 1 MiB
# ceiling (ADR-0105).
if [ "${AIUEOS_ECDSA_SIGN_KAT:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_ECDSA_SIGN_KAT=1"
fi
plc_runtime_link=
if [ "${AIUEOS_PLC_RT_SMOKE:-0}" = 1 ]; then
  : "${AIUEOS_PLC_ELF:?AIUEOS_PLC_ELF is required for the RT smoke}"
  : "${AIUEOS_PLC_RECEIPT:?AIUEOS_PLC_RECEIPT is required for the RT smoke}"
  : "${AIUEOS_PLC_SIGNATURE:?AIUEOS_PLC_SIGNATURE is required for the RT smoke}"
  : "${AIUEOS_PLC_PUBLIC_KEY:?AIUEOS_PLC_PUBLIC_KEY is required for the RT smoke}"
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_PLC_RT_SMOKE=1"
  plc_runtime_link="$kernel_plc_runtime_object $kernel_plc_embedded_object $kotoba_rt_dispatch_plan_object"
  kotoba_user_elf_valid_object="$aiueos/kotoba/plc-user-elf-valid.o"
  kotoba_user_elf_valid_sha=77c5e791da666e8355a7a877c37841cc63a3f228fbf785656522284a5259bbdd
fi
if [ "${AIUEOS_ECDSA_PUBLIC_KAT:-0}" = 1 ]; then
  input_smoke_cflags="$input_smoke_cflags -DAIUEOS_ECDSA_PUBLIC_KAT=1"
fi

# Pure-AIUEOS Qwen handoff. Production values are pinned and cannot be
# overridden accidentally; the tiny overrides exist only for the QEMU gate and
# require the explicit test-fixture switch.
model_handoff_cflags=
model_handoff_link=
qwen35_smp_cflags=
qwen35_vector_cflags=
model_slots_cflags=
model_slots_link=
# The split artifact the loader admits (ADR-0117).  Two production identities,
# selected by name and never by lengths: qwen38 is three FAT32-safe parts
# Q38P0..2, bonsai2 (Ternary-Bonsai-2-27B-PTQ1_0, ADR-0222 step 5) is two parts
# B2P0..1.  A two-part profile has part2 = 0.
model_profile=${AIUEOS_MODEL_PROFILE:-qwen38}
case "$model_profile" in
  qwen38)
    model_name=qwen38-27b model_file_prefix=Q38P
    pinned_total=10934860704 pinned_part0=4000000000 pinned_part1=4000000000
    pinned_part2=2934860704 pinned_parts=3
    pinned_sha256=c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee ;;
  bonsai2)
    model_name=bonsai2-27b model_file_prefix=B2P
    pinned_total=5946648928 pinned_part0=4000000000 pinned_part1=1946648928
    pinned_part2=0 pinned_parts=2
    pinned_sha256=53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3 ;;
  *) echo "error: AIUEOS_MODEL_PROFILE must be qwen38 or bonsai2" >&2; exit 1 ;;
esac
model_parts=$pinned_parts
model_total=${AIUEOS_MODEL_TOTAL_BYTES:-$pinned_total}
model_part0=${AIUEOS_MODEL_PART0_BYTES:-$pinned_part0}
model_part1=${AIUEOS_MODEL_PART1_BYTES:-$pinned_part1}
model_part2=${AIUEOS_MODEL_PART2_BYTES:-$pinned_part2}
model_sha256=${AIUEOS_MODEL_SHA256:-$pinned_sha256}
model_min_address=${AIUEOS_MODEL_MIN_ADDRESS:-4294967296}
model_max_address=${AIUEOS_MODEL_MAX_ADDRESS:-68719476735}
# The Kotoba/C parity self-test for the Qwen3.5 forward-pass objects
# (ADR-0147).  A SEPARATE flag from AIUEOS_QWEN38_MODEL_HANDOFF on purpose: the
# handoff makes the UEFI loader demand a 10,934,860,704-byte model mapping and
# refuse the boot without one (AIUEOS_LOADER_FAIL qwen38-model-admission
# code=121, measured 2026-09-02), while this comparison needs no model -- it is
# bit-equality of the arithmetic over synthetic inputs.  It compiles the same
# two C files the handoff does, so the reference half of the comparison is the
# code the model path actually runs.
qwen35_parity_cflags=
qwen35_parity_link=
case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
  0) ;;
  1|2|3|4|5) qwen35_parity_cflags="-DAIUEOS_QWEN35_KOTOBA_PARITY=${AIUEOS_QWEN35_KOTOBA_PARITY}" ;;
  *) echo "error: AIUEOS_QWEN35_KOTOBA_PARITY must be 0, 1, 2, 3, 4 or 5" >&2; exit 1 ;;
esac
if [ "${AIUEOS_QWEN38_MODEL_HANDOFF:-0}" = 1 ] ||
   [ "${AIUEOS_MODEL_NVME_SLOTS:-0}" = 1 ]; then
  if [ "${AIUEOS_MODEL_TEST_FIXTURE:-0}" != 1 ]; then
    [ "$model_total" = "$pinned_total" ] &&
    [ "$model_part0" = "$pinned_part0" ] &&
    [ "$model_part1" = "$pinned_part1" ] &&
    [ "$model_part2" = "$pinned_part2" ] &&
    [ "$model_sha256" = "$pinned_sha256" ] &&
    [ "$model_min_address" = 4294967296 ] &&
    [ "$model_max_address" = 68719476735 ] || {
      echo "error: production Qwen handoff identity is pinned; overrides require AIUEOS_MODEL_TEST_FIXTURE=1" >&2
      exit 1
    }
  fi
  for value in "$model_total" "$model_part0" "$model_part1" "$model_part2" \
               "$model_min_address" "$model_max_address"; do
    case "$value" in ''|*[!0-9]*) echo "error: model identity values must be decimal integers" >&2; exit 1 ;; esac
  done
  case "$model_sha256" in
    *[!0-9a-f]*|'') echo "error: model SHA-256 must be lowercase hexadecimal" >&2; exit 1 ;;
  esac
  [ "${#model_sha256}" -eq 64 ] || { echo "error: model SHA-256 must contain 64 hex digits" >&2; exit 1; }
  [ $((model_part0 + model_part1 + model_part2)) -eq "$model_total" ] || {
    echo "error: model part lengths do not sum to total bytes" >&2; exit 1;
  }
  # FAT32 caps a file at 4,294,967,295 bytes; every declared part must be a
  # non-empty file under it, and a two-part profile has no third part.
  for value in "$model_part0" "$model_part1"; do
    [ "$value" -ge 1 ] && [ "$value" -le 4294967295 ] || {
      echo "error: model part length must be 1..4294967295 (FAT32)" >&2; exit 1; }
  done
  if [ "$model_parts" = 3 ]; then
    [ "$model_part2" -ge 1 ] && [ "$model_part2" -le 4294967295 ] || {
      echo "error: model part length must be 1..4294967295 (FAT32)" >&2; exit 1; }
  else
    [ "$model_part2" = 0 ] || {
      echo "error: two-part model profile $model_profile has no third part" >&2; exit 1; }
  fi
  if [ "${AIUEOS_MODEL_NVME_SLOTS:-0}" = 1 ] && [ "$model_parts" != 3 ]; then
    echo "error: NVMe model slots stage the three-part qwen38 bundle only" >&2; exit 1
  fi
  if [ "${AIUEOS_QWEN38_MODEL_HANDOFF:-0}" = 1 ]; then
    model_handoff_cflags="-DAIUEOS_QWEN38_MODEL_HANDOFF=1"
    case "${AIUEOS_QWEN35_SMP:-1}" in
      1) qwen35_smp_cflags="-DAIUEOS_QWEN35_SMP=1" ;;
      0) qwen35_smp_cflags= ;;
      *) echo "error: AIUEOS_QWEN35_SMP must be 0 or 1" >&2; exit 1 ;;
    esac
    case "${AIUEOS_QWEN35_AVX2:-1}" in
      1) qwen35_vector_cflags= ;;
      0) qwen35_vector_cflags="-DAIUEOS_QWEN35_SCALAR=1" ;;
      *) echo "error: AIUEOS_QWEN35_AVX2 must be 0 or 1" >&2; exit 1 ;;
    esac
    if [ "${AIUEOS_MODEL_TEST_FIXTURE:-0}" = 1 ]; then
      model_handoff_cflags="$model_handoff_cflags -DAIUEOS_MODEL_TEST_FIXTURE=1"
    fi
    model_handoff_link="$kernel_model_handoff_object $kotoba_model_mapping_plan_object $kotoba_model_handoff_validate_object $kernel_qwen35_runtime_object $kernel_qwen35_quant_object $kernel_qwen35_infer_object $kotoba_qwen35_header_object $kotoba_qwen35_kv_object $kotoba_qwen35_tensor_object"
  fi
  if [ "${AIUEOS_MODEL_NVME_SLOTS:-0}" = 1 ]; then
    model_slots_cflags="-DAIUEOS_MODEL_NVME_SLOTS=1"
    if [ "${AIUEOS_MODEL_NVME_TARGET_OPTIONAL:-0}" = 1 ]; then
      model_slots_cflags="$model_slots_cflags -DAIUEOS_MODEL_NVME_TARGET_OPTIONAL=1"
    fi
    if [ "${AIUEOS_MODEL_SLOT_IMPORT_EXIT:-0}" = 1 ]; then
      [ "${AIUEOS_MODEL_TEST_FIXTURE:-0}" = 1 ] || {
        echo "error: model-slot import exit is test-fixture only" >&2
        exit 1
      }
      model_slots_cflags="$model_slots_cflags -DAIUEOS_MODEL_SLOT_IMPORT_EXIT=1"
    fi
    model_slots_link="$model_slots_object"
  fi
elif [ "${AIUEOS_MODEL_NVME_TARGET_OPTIONAL:-0}" = 1 ]; then
  echo "error: optional NVMe model target requires AIUEOS_MODEL_NVME_SLOTS=1" >&2
  exit 1
elif [ "${AIUEOS_MODEL_TEST_FIXTURE:-0}" = 1 ]; then
  echo "error: model test fixture requires a model handoff or NVMe-slot build" >&2
  exit 1
fi

command -v zig >/dev/null 2>&1 || {
  echo "error: Zig is required to build the freestanding UEFI application" >&2
  exit 1
}

mkdir -p "$(dirname -- "$efi")" "$kernel_dir"

# ---------------------------------------------------------------------------
# AIUEOS_K16_PURE_NATIVE=1 -- the pure Kotoba/Amu profile (ADR-0131).
#
# This profile does NOT produce a bootable image and is not trying to. What it
# does is make the Kotoba/foreign boundary MACHINE-CHECKED instead of stated:
#
#   (i)   the kernel link input is restricted to Kotoba objects and Amu
#         toolchain stubs -- the 33 C/ASM objects the ordinary link carries are
#         not compiled and not linked;
#   (ii)  the exact link list is handed to k16-pure-native-gate.cljs BEFORE
#         `zig ld.lld` runs, and a non-zero exit aborts the build;
#   (iii) the artifacts are named aiueos-k16-pure-native-* and the gate receipt
#         is written next to them;
#   (iv)  BOOTX64.EFI would have to come from a Kotoba/Amu artifact. None
#         exists: `uefi/main.c` is the loader. So this profile REFUSES to emit
#         a loader rather than shipping the C one under a "pure native" name.
#
# The refusal is conditional on a measurement, not hard-coded: set
# AIUEOS_KOTOBA_LOADER_EFI to a Kotoba/Amu-produced PE32+ image and this stops
# refusing on that ground. Until such an artifact exists, the honest output of
# this profile is a refusal and a count.
#
# The link list is DERIVED from the production `zig ld.lld` invocation below
# rather than restated here. A second copy of that list is a copy that can fall
# out of step with it silently, and a gate over the wrong list is worse than no
# gate at all.
# ---------------------------------------------------------------------------
if [ "${AIUEOS_K16_PURE_NATIVE:-0}" = 1 ]; then
  command -v python3 >/dev/null 2>&1 || {
    echo "error: the K16 pure-native profile needs python3 to run its gate" >&2
    exit 2
  }
  pure_prefix="$out/aiueos-k16-pure-native"
  pure_list="$pure_prefix-link-list.txt"
  pure_receipt="$pure_prefix-receipt.edn"
  pure_kernel="$pure_prefix-kernel.elf"
  pure_vars=$(sed -n '/^zig ld\.lld /,/^fi$/p' "$0" \
    | grep -o '\$kotoba_[A-Za-z0-9_]*_object' | sed 's/^\$//')
  [ -n "$pure_vars" ] || {
    echo "error: could not derive the Kotoba link list from $0" >&2
    exit 2
  }
  : > "$pure_list"
  for pure_var in $pure_vars; do
    eval "printf '%s\n' \"\$$pure_var\"" >> "$pure_list"
  done
  # The two conditionally linked Kotoba objects reach the production link
  # through these variables rather than by name, so they are appended the same
  # way the link line reads them.
  for pure_extra in $ecdsa_sign_link $ecdsa_public_link; do
    printf '%s\n' "$pure_extra" >> "$pure_list"
  done
  echo "AIUEOS_K16_PURE_NATIVE profile: kernel link restricted to Kotoba objects + Amu stubs"
  echo "AIUEOS_K16_PURE_NATIVE link-list=$pure_list entries=$(wc -l < "$pure_list" | tr -d ' ')"
  pure_gate_status=0
  # The provenance manifest is overridable so the profile's ADMITTED branch can
  # be exercised. It is not a way to wave objects through: the override is still
  # a manifest the gate checks digest-for-digest against the bytes on disk.
  pure_provenance=${AIUEOS_K16_PURE_NATIVE_PROVENANCE:-"$aiueos/kotoba/provenance.edn"}
  python3 "$aiueos/scripts/k16-pure-native-gate.py" \
    --link-list "$pure_list" \
    --provenance "$pure_provenance" \
    --receipt-out "$pure_receipt" \
    --root "$repo" || pure_gate_status=$?
  if [ "$pure_gate_status" = 0 ]; then
    zig ld.lld -nostdlib -static --strip-all -z max-page-size=0x1000 \
      -T "$aiueos/kernel/linker.ld" -o "$pure_kernel" @"$pure_list" \
      || {
        echo "AIUEOS_K16_PURE_NATIVE_LINK_FAILED kernel=$pure_kernel" >&2
        pure_gate_status=3
      }
  else
    echo "AIUEOS_K16_PURE_NATIVE gate refused; kernel not linked" >&2
  fi
  pure_kernel_state=not-linked
  if [ -f "$pure_kernel" ]; then
    pure_kernel_state=linked
  fi
  if [ -n "${AIUEOS_KOTOBA_LOADER_EFI:-}" ] && [ -f "${AIUEOS_KOTOBA_LOADER_EFI:-}" ]; then
    cp "$AIUEOS_KOTOBA_LOADER_EFI" "$pure_prefix-BOOTX64.EFI"
    pure_loader_state=copied
  else
    echo "REFUSED foreign-code: uefi/main.c"
    pure_loader_state=refused
    if [ "$pure_gate_status" = 0 ]; then
      pure_gate_status=3
    fi
  fi
  echo "AIUEOS_K16_PURE_NATIVE_INCOMPLETE loader=$pure_loader_state kernel=$pure_kernel_state bootable=no receipt=$pure_receipt"
  echo "This profile cannot produce a bootable K16 image today. It exists so that" >&2
  echo "every later stream can measure progress against a machine-checked boundary." >&2
  exit "$pure_gate_status"
fi

build_version=$(tr -d '\r\n' < "$aiueos/VERSION")
build_source_commit=$(git -C "$repo" rev-parse HEAD)
build_source_dirty=false
if [ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ]; then
  build_source_dirty=true
fi
python3 - "$build_identity_header" "$build_version" \
  "$build_source_commit" "$build_source_dirty" <<'PYBUILD'
from pathlib import Path
import re
import sys

out, version, commit, dirty = sys.argv[1:]
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?", version):
    raise SystemExit("error: os/aiueos/VERSION must be a bounded SemVer string")
if not re.fullmatch(r"[0-9a-f]{40}", commit):
    raise SystemExit("error: AIUEOS source commit must be a full lowercase git hash")
suffix = "-DIRTY" if dirty == "true" else ""
Path(out).write_text(
    "#ifndef AIUEOS_BUILD_IDENTITY_H\n#define AIUEOS_BUILD_IDENTITY_H\n"
    f'#define AIUEOS_BUILD_VERSION "{version}"\n'
    f'#define AIUEOS_BUILD_SOURCE_HASH "{commit[:12]}"\n'
    f'#define AIUEOS_BUILD_DIRTY_SUFFIX "{suffix}"\n'
    "#endif\n", encoding="ascii")
PYBUILD
python3 - "$model_identity_header" "$model_total" "$model_part0" \
  "$model_part1" "$model_part2" "$model_sha256" "$model_min_address" \
  "$model_max_address" "$model_parts" "$model_name" "$model_file_prefix" <<'PYMODEL'
from pathlib import Path
import sys

(out, total, part0, part1, part2, digest, minimum, maximum, parts, name,
 prefix) = sys.argv[1:]
values = ",".join(f"0x{int(digest[i:i+2], 16):02x}" for i in range(0, 64, 2))
Path(out).write_text(
    "#ifndef AIUEOS_MODEL_IDENTITY_H\n#define AIUEOS_MODEL_IDENTITY_H\n"
    "#include <stdint.h>\n"
    f"#define AIUEOS_MODEL_TOTAL_BYTES {total}ULL\n"
    f"#define AIUEOS_MODEL_PART0_BYTES {part0}ULL\n"
    f"#define AIUEOS_MODEL_PART1_BYTES {part1}ULL\n"
    f"#define AIUEOS_MODEL_PART2_BYTES {part2}ULL\n"
    f"#define AIUEOS_MODEL_PART_COUNT {parts}U\n"
    f'#define AIUEOS_MODEL_PARTS_TEXT "{parts}"\n'
    f'#define AIUEOS_MODEL_NAME "{name}"\n'
    f'#define AIUEOS_MODEL_PART0_PATH u"\\\\EFI\\\\AIUEOS\\\\{prefix}0.BIN"\n'
    f'#define AIUEOS_MODEL_PART1_PATH u"\\\\EFI\\\\AIUEOS\\\\{prefix}1.BIN"\n'
    f'#define AIUEOS_MODEL_PART2_PATH u"\\\\EFI\\\\AIUEOS\\\\{prefix}2.BIN"\n'
    f"#define AIUEOS_MODEL_MIN_ADDRESS {minimum}ULL\n"
    f"#define AIUEOS_MODEL_MAX_ADDRESS {maximum}ULL\n"
    "#ifndef AIUEOS_MODEL_IDENTITY_MACROS_ONLY\n"
    "static const uint8_t aiueos_expected_model_sha256[32]={" + values + "};\n"
    "#endif\n"
    "#endif\n", encoding="ascii")
PYMODEL
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_kernel_object" "$kotoba_kernel_sha"
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_journal_object" \
  "$kotoba_journal_sha" kotoba_aiueos_journal_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_fnv_object" \
  "$kotoba_fnv_sha" kotoba_aiueos_fnv1a
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_journal_valid_object" \
  ba81e7a03351f16d2950a0d5d19fd6c73e8ee53bb68c2688e2ccd1c8977bb605 \
  kotoba_aiueos_journal_record_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_transaction_valid_object" \
  f0b02853561a52540d4daa806ffa1e2cc880f3efa99b110777db59ca01f3eacc \
  kotoba_aiueos_object_transaction_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_transaction_route_object" \
  183144e10fc4291f7bb2c7eaaf28196f43c7ca9dc911670e482a3d2105563a87 \
  kotoba_aiueos_object_transaction_route
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_mutable_valid_object" \
  e3bc00b7fa726a77bb2f80694c1c3b0b5b8bee0f1873cfe86b44b3f52faf3dbf \
  kotoba_aiueos_mutable_object_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_superblock_valid_object" \
  6f7f8d66fe5e1634a56386dc6447a26970962f8bbe40b0a2a5b6215a8422d1c1 \
  kotoba_aiueos_superblock_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_journal_build_object" \
  73d6277a3b8576e6c1b6dc4fcc23f1506927439e328aa4741d18c73fd82b9ebf \
  kotoba_aiueos_journal_record_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_mutable_build_object" \
  c0702160f1f0fb7e2ae4fb66ca145fecee320de1c49875b8e5a92ad0f9a60977 \
  kotoba_aiueos_mutable_object_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_cap_valid_object" \
  0f591a342fe5b4fa959f8a21d36930ec9eca7859302a747ce43f5e3caa20c9c6 \
  kotoba_aiueos_virtio_cap_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_extent_valid_object" \
  cfde40e55fc8e52d6100183e2e4a7eecd60120be95f9c04234714ad041916ec4 \
  kotoba_aiueos_pci_extent_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_region_valid_object" \
  e71f161385afb5e3c83913633417e59fa53532e2d7ba7f4234ea192988c6e0a6 \
  kotoba_aiueos_pci_region_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_pci_config_read_object" \
  04ab0830219e6e03552cfc46ccfc56ce34fd1cf84b2f418d3a7916d4aac264d6 \
  kotoba_aiueos_pci_config_read
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_pci_config_write_object" \
  354f8ca148b0264af2dac50b2d26af9d0b439f641b0dcdf5714fd7465add4ba5 \
  kotoba_aiueos_pci_config_write
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_mmio_map_admit_object" \
  fb6b5591bf9c78b030aaf10aa93d305ac2b0f41cac9278be56507a6ec519e60b \
  kotoba_aiueos_mmio_map_admit
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_acpi_checksum_object" \
  f92dd1922a7d4dd2bb30614d3f8058da671b5f154bd9b5c452174ae8a17a5978 \
  kotoba_aiueos_acpi_checksum_ok
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_acpi_table_valid_object" \
  66e621af0bbd4f7436a03a52e945d10f99a87b2608554aa1f9e997b36b1de1f6 \
  kotoba_aiueos_acpi_table_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_vtd_admit_object" \
  2e7f1d3e6c324fe760c9ab2fb2b2614f655bd3c1aa61d31d929a4aa0aacf0bfd \
  kotoba_aiueos_vtd_admit
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_msr_read_object" \
  da3add0a82de4562a8da117105e9a40a67e87c8086ca9b71851c4a9d9e673e0c \
  kotoba_aiueos_msr_read
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_msr_write_object" \
  a6ae6efbe7c3a7543b391b01a9203906532b3c4328fb38bafb2d093b37bfe20d \
  kotoba_aiueos_msr_write
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_idt_gate_object" \
  52c88178bbd56a1b0c133b6a1ad6e5393b8e38c2a419c20a867e94bc87b3294b \
  kotoba_aiueos_idt_gate_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_pic_disable_object" \
  c88ff01d1eb89f9cf549f4c0ca24f34928f948cab4a96cad82a8ab518bf7fad1 \
  kotoba_aiueos_pic_disable
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_cpu_feature_nx_object" \
  8e6b33fede5b4dd669e91c52d27273c2e36fc883e3b7d7d5b99806ab3e96903d \
  kotoba_aiueos_cpu_feature_nx
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_cpu_feature_syscall_object" \
  6255927efd8e44e7b204171426595c8040ee9fec57805c85162acbae5657ae61 \
  kotoba_aiueos_cpu_feature_syscall
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_cpu_apic_id_object" \
  078886d7c38cde4761e31a7f5a8b2e10c0facc9491394fb00d2702e515955183 \
  kotoba_aiueos_cpu_apic_id
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_syscall_range_object" \
  04dd94e36e17da696f5bd235a7e1359173ab6625366b6db07651c5f255c90d3e \
  kotoba_aiueos_syscall_range_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_copy_in_object" \
  9f88efa075c7d10af87299f4eb358633378827a603726f624e26ec3a19d5ab78 \
  kotoba_aiueos_copy_in
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_allocator_plan_object" \
  2073156ec60c484bd2d9cdd4e93e2fbee4c9f3eef77c343306f839a4e5bcc0d1 \
  kotoba_aiueos_allocator_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_capability_object" \
  32b398da53886afe2dc7dca67bba54779e7791bed9373bad52c0cf527c55697b \
  kotoba_aiueos_capability_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_capability_mutation_object" \
  026bcc5a6cc3336d892f3c58cdbf07dbca49f72d8e129f8cb46c29f9fdb7b668 \
  kotoba_aiueos_capability_mutation_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_service_lifecycle_object" \
  a61aea52c4186715a8f87f5c3eed861e9c64b9487e5f659ba43cb6165a6dbaac \
  kotoba_aiueos_service_lifecycle
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_service_registry_object" \
  3abb1bb7dbf76b4beb6b42d131590e2b780a9f7716a7ddb96f898f725eae9ea0 \
  kotoba_aiueos_service_registry_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_service_registry_state_object" \
  ac55a65f0ae76a0c2837292f3e8c105cf3923f88a32fcdc28456cbc0d71b2c06 \
  kotoba_aiueos_service_registry_state
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_user_object_journal_object" \
  86a38657fed34f13caabb3b17dd5b7c7d1faa075616eb11fc9a8b0357b2f2d9e \
  kotoba_aiueos_user_object_journal_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_user_object_journal_valid_object" \
  0cf73686917e098cc4a6786a1d658080250c6a75a527d8218ed216e96e0b2b09 \
  kotoba_aiueos_user_object_journal_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_user_object_journal_value_object" \
  0225a24d0e3bb105be13344b898866659ce0b25a01f15a471261ab24d66ba92b \
  kotoba_aiueos_user_object_journal_value
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_sha256_object" \
  e73ea80aeb200c5f6ab5eec49e4d54f5921b78baf9d5d018aed74ec2c8cf40ec \
  kotoba_aiueos_sha256
# tokenizer: same check as every object above -- one export, zero imports, one
# relocation into its own .data, and the sha256 of the artifact this tree
# carries.
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_vocab_index_object" \
  4963039783ea1e7a4582dc6ae140bb52a642da48f1d8f3c1927f862f819f8b7a \
  kotoba_aiueos_qwen35_vocab_index_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_tokenize_object" \
  8c1da69cfc836efc7fc23c228d7ad78ba092ed8295a8f477fdf08a8ed871af81 \
  kotoba_aiueos_qwen35_tokenize
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_detokenize_object" \
  d1713172ee70aaf0c46c3f06fe38a37eb103219192d708fe1b8acf556ec9cea0 \
  kotoba_aiueos_qwen35_detokenize
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_digest_equal_object" \
  d5af2bd0ed029cb5e2c64445dc28cf360a09f7467e684d0b3ebb8b50f2417a46 \
  kotoba_aiueos_digest_equal
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_catalog_valid_object" \
  fb2421c25351d62061b62266f12b63fdd1bf16cd917da2dd852018ad29ac6777 \
  kotoba_aiueos_app_catalog_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_app_lookup_object" \
  ec822fe970c315e15c997372f30cb4c016c482c0192e550117c4c1a69000b771 \
  kotoba_aiueos_app_lookup_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_user_elf_valid_object" \
  "$kotoba_user_elf_valid_sha" \
  kotoba_aiueos_user_elf_valid
if [ "${AIUEOS_PLC_RT_SMOKE:-0}" = 1 ]; then
  python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_rt_dispatch_plan_object" \
    63d74ae94bfa918fc4284a554165d56555105c3b4740735dfbd5d4318c1e7774 \
    kotoba_aiueos_rt_scheduler_plan
fi
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_user_context_object" \
  7b724a994ebdcb1c223bd381b34162fa6a7044364e35ae0e0894412d8817238f \
  kotoba_aiueos_user_context_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_kernel_context_object" \
  f5bc59c40dde2df00db88a2e6097409c222bed80308778c6f5a94211bea1ef4d \
  kotoba_aiueos_kernel_context_build
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_mapping_plan_object" \
  bdff4601a48da4627345a8b5bf2018cce70baff7ee56151e56365f6ccb42c66a \
  kotoba_aiueos_page_mapping_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_process_plan_object" \
  35b980f64d0238a67662e924a641fead9cb742523911963cf4d5e32db6bc7752 \
  kotoba_aiueos_process_create_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_teardown_plan_object" \
  2d30a3cf9af5ff5d040f907a476bb16d420fc8bd91fc1c04adfdddfb642ec823 \
  kotoba_aiueos_process_teardown_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_task_plan_object" \
  c5c3cc5f553021af742bd5ab674196b76310d4296c88290d665870de7c6f9e63 \
  kotoba_aiueos_task_slot_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_dispatch_plan_object" \
  028cc85bcf38dd6b0a702a28904f6e281eda82122599e5fb06e150d718546f6a \
  kotoba_aiueos_scheduler_dispatch_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_exit_route_object" \
  548fc48d4c59db4f69d9477da1d776b0de8cbde743ef08681674142d732498c0 \
  kotoba_aiueos_task_exit_route
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_service_task_object" \
  a5ad1725c09d11f4c12f83c867846b6ebede3455e33e7276f7e9c4c5fbd17275 \
  kotoba_aiueos_service_task_transition
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_rsa2048_object" \
  0f4eeeecdc0605217aae5dfe55cd219c2c9a586a9ca9104d760d87c21642e72c \
  kotoba_aiueos_rsa2048_sha256_verify
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_net_arp_object" \
  b333e29909d521963e300073e8f49639413e754465394ba92b1419ede73a954e \
  kotoba_aiueos_net_arp_reply_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_ipv4_checksum_object" \
  5bc0305f1f29238bdfff4ed45d66948cda266d811f90356cbbfebace7f250d77 \
  kotoba_aiueos_ipv4_checksum
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_ipv4_icmp_object" \
  a3465a3e9bb7527957e09d02171c3eafa3d117b854e0ca55258e175afee5b249 \
  kotoba_aiueos_ipv4_icmp_reply_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_tcp_checksum_object" \
  e54aaefced0e7ae91315fa41eaf1c22d9fba2110df5da63304962e6199cada4f \
  kotoba_aiueos_tcp_checksum_ok
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_tcp_segment_object" \
  1a6b406a39aa5b5a71798046911e72b7d36c393b08d3d8c123e7e1a52efcaf7b \
  kotoba_aiueos_tcp_segment_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_dhcp_reply_object" \
  977208efc1fd8b92160c41fbf99959b6a940662d104cf85717c9decc972d0346 \
  kotoba_aiueos_dhcp_reply_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_dhcp_option_object" \
  c759b70a5061f03d27c3c94e05fe248e6cccc82182a63a35e674647cf050c482 \
  kotoba_aiueos_dhcp_option_u32
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_relay_hello_object" \
  4c38d1ec0602a46beea61a5759b450da0bef260bdd1f04aab1055d141134958d \
  kotoba_aiueos_relay_hello_payload
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_relay_ack_object" \
  e5bafb1b7fd0e57ecf2cc5e7521a9c960f9e7005a455c6bd7aecf2e359bd42bb \
  kotoba_aiueos_relay_ack_payload_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_inference_status_valid_object" \
  7bffa1b85e1835493a624c85dd4cee15a63f48e180521055efd17d4e700d60a8 \
  kotoba_aiueos_inference_status_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_inference_rate_object" \
  069d218c6a91a3ac4728d461a2089977f39f9d84b2a62dfa2800159d1450a41c \
  kotoba_aiueos_inference_milli_tokens_per_second
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_model_mapping_plan_object" \
  c636da1971323aeba566cec7d64a7c116cda77bf75e2248ad4371beda0587d35 \
  kotoba_aiueos_model_mapping_plan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_model_handoff_validate_object" \
  057a0ba7a1d150b5eeca2a3e3d8c95642e3aa140181f6f20d5cdbb2f2a8a6c10 \
  kotoba_aiueos_model_handoff_validate
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_device_worker_poll_object" \
  5d31e51fe0416756a5c2911760e2fa7ac4f9408ae675cf231fa729b4f15f424d \
  kotoba_aiueos_device_worker_poll_response
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_job_protocol_object" \
  c8df3c8f8d4ea5534ad879f6a94eff9f1c0281ab44a456ed58c229c53456187b \
  kotoba_aiueos_job_protocol
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_micro_infer_next_object" \
  52dcbd0c677e9d619fb91090526e9bbe863624235ab22c359b2a515261ad4eed \
  kotoba_aiueos_micro_infer_next
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_aes128_gcm_selftest_object" \
  45cee00c5bbf25060691cb86e1cd178c317f9746bf43b6dfde82c3ad0745a3c9 \
  kotoba_aiueos_aes128_gcm_selftest
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_x25519_object" \
  30db73025df711305c34cd738f489c01ea38c06738c1f44c9e0dc934c6aff4db \
  kotoba_aiueos_x25519
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_ecdsa_object" \
  5540c3b633bec183446ac11bdbedfb84970bfe134bd45af6490a3bcded88f855 \
  kotoba_aiueos_ecdsa_p256_sha256_verify
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_aes128_gcm_object" \
  2b3b4c7d5f8800dc2c9f187e3693210bd1b69d0e434bc2f8ce78d2f236489f46 \
  kotoba_aiueos_aes128_gcm
# Qwen3.8-27B GGUF admission (ADR-0137). Verified unconditionally like every
# object above, even in profiles that do not link them: the digests are what
# ties the committed artifacts to the sources the oracles graded.
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_header_object" \
  b2e466eebabfdae8aaad8741b552ddeed0033c8814756b0409e59026fa8f72ec \
  kotoba_aiueos_qwen35_gguf_header_valid
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_kv_object" \
  58df1be50a53c63332969963fa580e07101c6045f225367fb8a68de8ebbd5297 \
  kotoba_aiueos_qwen35_gguf_kv_scan
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_tensor_object" \
  1a409350fbecd3b75b8814e406ee598a4e1f048bac7c0b1ccdba9a43391ccfaf \
  kotoba_aiueos_qwen35_tensor_table_bind
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_tls13_record_object" \
  572b7e33640a413bb68e37f39f09e155282eefe86c33f9e2a31040c70a170d7a \
  kotoba_aiueos_tls13_record
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_cid_v1_admit_object" \
  4760b9183029babcad5b2d3dcf8418f4a970cbdc289e5c8a1b053d1149d6c333 \
  kotoba_aiueos_cid_v1_admit
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_value_runtime_cas_verify_object" \
  851e6af2813dc651a69a65bf1036d4bb8d7a374fe117df6fe2b0e0dd4d1b4ad7 \
  kotoba_aiueos_value_runtime_cas_verify
if [ -n "$model_handoff_link" ] || [ -n "$qwen35_parity_cflags" ]; then
  python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_dot_object" \
    2045ea927e0f9ae36d45e766a78ff0a9e2254e2cad9849ccf6b2308111a0c15c kotoba_aiueos_qwen35_dot_f32
  python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_dequant_object" \
    2713ffbac10ad71dad46a899b782c2687820fc2896edab444806867ae62fd730 kotoba_aiueos_qwen35_dequant_row
  python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_matvec_object" \
    916b1b9009c67525b96610a4ede21e4bbe4117987cf9495d4ed0128e61b8a245 kotoba_aiueos_qwen35_matvec
  # FIVE parity profiles, each linking only the objects its stages call. The
  # low region (`aiueos_low_end <= 0x1f4000`) cannot hold every object at once
  # since the tokenizer objects landed -- measured, not assumed, and measured
  # again for the third tranche: attention (17,872 B) and recurrent-step
  # (6,808 B) together overflow it, and so does either one alone until the
  # parity build gained `--gc-sections` (ADR-0175).
  # The norm and activation objects are the LIVE path since ADR-0220's
  # cutover stage 2, so the model image links them beside the matvec trio;
  # parity profile 2 links them alone and compares them against the C.
  # The attention object joins them at cutover stage 3; parity profile 3
  # links it alone and compares it against the C. The recurrent-step object
  # joins them at cutover stage 4; parity profile 4 links it alone. The
  # rope object joins them at cutover stage 5; parity profile 5 links it
  # alone and compares it against the Prism reference, not the C (whose
  # x87 sine no Kotoba object can match), and prints its distance from the C.
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    0|5)
      python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_rope_object" \
        51405dd582722833216f7a29b76f43ed5dc14c4f6caccec3a8aa0db473fff914 \
        kotoba_aiueos_qwen35_rope
      ;;
  esac
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    0|4)
      python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_recurrent_object" \
        1e295fb9bb22b36871d5703b74fc4da5838407a7fea481e7137e343549bebbbc \
        kotoba_aiueos_qwen35_recurrent_step
      ;;
  esac
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    0|3)
      python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_attention_object" \
        83457f37408b8666ac3aeabad58f6c6dc0dcef4d242a6d3912851188a5a53093 \
        kotoba_aiueos_qwen35_attention
      ;;
  esac
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    0|2)
      python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_activation_object" \
        abfbcf8e7e0fcda94ab3dd9c5c71d26b4d38fa043945990bbe5b53ff5a3d1c26 kotoba_aiueos_qwen35_activation
      python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_qwen35_norm_object" \
        9b949aa9fce7d9cb91f39c94428f153dc016f37f3e4ac78f1d2c85fce6633edd kotoba_aiueos_qwen35_norm
      ;;
  esac
  if [ "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" = 2 ]; then
    qwen35_kotoba_link="$kotoba_qwen35_activation_object $kotoba_qwen35_norm_object"
  elif [ "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" = 3 ]; then
    qwen35_kotoba_link="$kotoba_qwen35_attention_object"
  elif [ "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" = 4 ]; then
    qwen35_kotoba_link="$kotoba_qwen35_recurrent_object"
  elif [ "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" = 5 ]; then
    qwen35_kotoba_link="$kotoba_qwen35_rope_object"
  else
    qwen35_kotoba_link="$kotoba_qwen35_dot_object $kotoba_qwen35_dequant_object $kotoba_qwen35_matvec_object $kotoba_qwen35_activation_object $kotoba_qwen35_norm_object $kotoba_qwen35_attention_object $kotoba_qwen35_recurrent_object $kotoba_qwen35_rope_object"
  fi
fi
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_device_worker_canonical_object" \
  fdd390542fc7a315bff5a8adb3e7ca78eef493d46e652f45c80a77dba664fc95 \
  kotoba_aiueos_device_worker_canonical
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_sha256_stream_object" \
  116e6521295545a5090bd7f6fa5c2e9ed5c9d02df590fbda3a7ef170667606dd \
  kotoba_aiueos_sha256_stream
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_sha256_region_object" \
  1e9f85cb3c43d8523ff8590818294ec4910dfee3a296bc59db3456cf08333835 \
  kotoba_aiueos_sha256_region
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_device_worker_digest_object" \
  69ff3682122313c00b61fb0362cfce40fc7c76065d7e327d829c9f8cb4d5c914 \
  kotoba_aiueos_device_worker_digest
if [ -n "$ecdsa_sign_link" ]; then
  python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_ecdsa_sign_object" \
    42496f9fe7c540c869e1bbe1d63e6b2a7e5e9387f5ffb486f89cc3f1a6f0adb6 \
    kotoba_aiueos_ecdsa_p256_sign
fi
if [ -n "$ecdsa_public_link" ]; then
  python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_ecdsa_public_object" \
    b1b1c6ccef85594c890c0a17be9c9e718c00b54da9615b5bd56510f883de0172 \
    kotoba_aiueos_ecdsa_p256_public
fi
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_ime_object" \
  ee11f50c9dfb30d03c820bead466b2f1bf18e4e64f3a2bfda98f5a5dd5d4ca34 \
  kotoba_aiueos_ime_commit
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_wm_object" \
  f0eb2dd827b30c778ac9321963d4da53932802693be72bc5ef8a38f25893d900 \
  kotoba_aiueos_wm_hit
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_scanout_object" \
  5ca924dff9fe42620f2313d16f8f62018d9bfbf588c7b142383066cce65d8305 \
  kotoba_aiueos_scanout_bind
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_broker_object" \
  713bdc8e4c3d41ea9602fe9184741c15bd7a7b71d6f1b688a766a2d83714a48f \
  kotoba_aiueos_broker_admit
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_session_object" \
  1983e5fa9026b2a356a4c43f6fa84630f6261ebd50c9939c4d657a326659048b \
  kotoba_aiueos_session_restore
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_browser_frame_object" \
  d828fde6c002264314c9e86ee4bd72ceda2965c97cfd6ba87d6558956c591569 \
  kotoba_aiueos_browser_frame
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_browser_reduce_object" \
  fd355f2da0d3b5a77c39ee2f7d1c888a127c1af67122b354773bb260cc9c9677 \
  kotoba_aiueos_browser_reduce
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_browser_frame2_object" \
  e753f2658573c2c681e60e1c37cd7c802d65925aa055cf01b734f9eefc5b506c \
  kotoba_aiueos_browser_frame2
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_browser_ime_object" \
  52ef6924472cded523d80c9f9dd7c2ad533bb58446240028424e08462bdbbba7 \
  kotoba_aiueos_browser_key
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$kotoba_browser_damage_object" \
  5dc5c33880e39b2a656d701230156963b604f04c765298379c8d479d59745ecc \
  kotoba_aiueos_browser_damage
python3 "$aiueos/scripts/verify-kotoba-user-elf.py" "$kotoba_user_elf" \
  1f0e5897831d0de6bbcb15eec82a6e0c4b402b436689cec051bc6de3b5c4e905
if [ -n "${AIUEOS_EXTERNAL_KERNEL_ELF:-}" ]; then
  python3 "$aiueos/scripts/verify-kotoba-native-kernel.py" \
    "$AIUEOS_EXTERNAL_KERNEL_ELF" "$aiueos/native/kernel.kotoba" \
    6d14f1ab0dc8c296a25a3b41a774423a829239eb "$out/native-kernel-receipt.json"
  cp "$AIUEOS_EXTERNAL_KERNEL_ELF" "$kernel"
else
# ADR-0270: the low region (kernel/linker.ld, 0x1f4000) has no room for the passkey's ECDSA sign and public objects at -O2; the guest-browser
# build, which carries the desktop stages, compiles main.c for size. Every other build is unchanged.
kernel_main_opt=-O2
# AIUEOS_KERNEL_OPT: the optimisation level alone, for splitting the ring3
# investigation's bundle (JUN-140, 2026-10-26): the default image dies before
# AIUEOS_RING3_OK and the working flavour bundles -Os, -DAIUEOS_SIZE_BUILD and
# the ECDSA objects. Empty keeps -O2.
if [ -n "${AIUEOS_KERNEL_OPT:-}" ]; then kernel_main_opt="$AIUEOS_KERNEL_OPT"; fi
# -fno-builtin: -Os turns clear loops into memset/memcpy calls the freestanding kernel does not define.
# AIUEOS_KERNEL_SIZE_BUILD: the same main.c flavour the guest-browser build
# uses, selectable on its own (explicit caller choice wins -- the pattern
# smoke-qemu-uefi.sh uses for AIUEOS_SMOKE_FINAL_PROBE). It exists so the
# offline-floor's default-profile boot can be measured against THIS variable
# alone: AIUEOS_GUEST_BROWSER also switches the stage script and the injector,
# which confound any attempt to ask whether the -O2 default build is what dies
# before AIUEOS_RING3_OK.
if [ "${AIUEOS_KERNEL_SIZE_BUILD:-${AIUEOS_GUEST_BROWSER:-0}}" = 1 ]; then kernel_main_opt="-Os -fno-builtin -DAIUEOS_SIZE_BUILD"; fi
# AIUEOS_KERNEL_SIZE_DEFINE: the define (and the ECDSA objects passkey
# ceremony needs) WITHOUT -Os, so -O2+define can be measured against -Os+define
# and against plain -O2. Second knob of the same investigation.
if [ "${AIUEOS_KERNEL_SIZE_DEFINE:-0}" = 1 ]; then kernel_main_opt="$kernel_main_opt -fno-builtin -DAIUEOS_SIZE_BUILD"; fi
zig cc -target x86_64-freestanding-none -std=c11 $kernel_main_opt \
  -ffreestanding -fno-stack-protector -mno-red-zone -I "$out" \
  $input_smoke_cflags $model_handoff_cflags $physical_qualification_cflags \
  $qwen35_smp_cflags $qwen35_parity_cflags \
  $physical_network_qualification_cflags $physical_direct_https_qualification_cflags \
  $murakumo_device_result_cflags $persistent_boot_cflags \
  $physical_relay_qualification_cflags \
  $physical_job_qualification_cflags \
  $kernel_hang_test_cflags \
  -c -o "$kernel_object" "$aiueos/kernel/main.c"
zig cc -target x86_64-freestanding-none \
  -c -o "$kernel_entry_object" "$aiueos/kernel/entry.S"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone -I "$out" \
  $physical_qualification_cflags $model_handoff_cflags \
  -c -o "$kernel_paging_object" "$aiueos/kernel/paging.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_acpi_object" "$aiueos/kernel/acpi.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_vtd_object" "$aiueos/kernel/vtd.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_apic_object" "$aiueos/kernel/apic.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_memory_object" "$aiueos/kernel/memory.c"
# ADR-0272: the virtio-sound driver is compiled into the guest-browser build only.
kernel_pci_audio=
if [ "${AIUEOS_GUEST_BROWSER:-0}" = 1 ]; then kernel_pci_audio=-DAIUEOS_AUDIO; fi
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone -I "$out" \
  $input_smoke_cflags $physical_network_qualification_cflags \
  $physical_direct_https_qualification_cflags \
  $murakumo_device_result_cflags \
  $physical_relay_qualification_cflags \
  $physical_job_qualification_cflags $kernel_pci_audio \
  -c -o "$kernel_pci_object" "$aiueos/kernel/pci.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_rtl8125_object" "$aiueos/kernel/rtl8125.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_micro_infer_object" "$aiueos/kernel/micro_infer.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_inference_status_object" "$aiueos/kernel/inference_status.c"
if [ "${AIUEOS_MURAKUMO_DEVICE_RESULT:-0}" = 1 ]; then
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    -c -o "$kernel_device_result_object" "$aiueos/kernel/device_result.c"
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    -c -o "$kernel_device_worker_protocol_object" \
    "$aiueos/kernel/device_worker_protocol.c"
fi
if [ -z "$model_handoff_link" ] && [ -n "$qwen35_parity_cflags" ]; then
  # The parity build compiles the reference C without the model handoff, so
  # the loader never asks for a model and the comparison still runs against
  # the same qwen35_quant.c / qwen35_infer.c the handoff compiles.
  #
  # `-ffunction-sections -fdata-sections` + `--gc-sections` is what makes a
  # parity image FIT. MEASURED 2026-09-03 at aiueos main f11967e: without it
  # every profile is over `aiueos_low_end <= 0x1f4000` -- profile 1 by 45,056
  # bytes, profile 2 by 40,960, profile 3 by 40,960, profile 4 by 28,672 --
  # and ld.lld produces nothing. That is not a cost this tranche introduced:
  # profiles 1 and 2 landed working and the tree grew past them. The
  # comparison is unaffected because what the collector removes is the model
  # path (`aiueos_qwen35_generate`, the GGUF parser, the IQ codebook grids),
  # which no self-test stage calls, and it removes it from the REFERENCE half
  # -- a stage whose reference had been collected would not agree with the
  # object, it would fail to link.
  qwen35_parity_section_cflags="-ffunction-sections -fdata-sections"
  qualification_gc_link="--gc-sections"
  # Profiles 2-4 link only their own stage's objects (above), so the live
  # matvec/dequant path -- the Kotoba objects since ADR-0221 -- has nothing
  # to resolve against there; those profiles compile the inference C with
  # its C reference as the forward pass. Profile 1 links the objects and
  # compares them against that reference on the CPU.
  # The same for the norm/activation objects (ADR-0220 cutover stage 2):
  # only profile 2 links them, so profiles 1, 3 and 4 run the C norms.
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    2|3|4|5) qwen35_parity_section_cflags="$qwen35_parity_section_cflags -DAIUEOS_QWEN35_C_REFERENCE_MATVEC=1" ;;
  esac
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    1|3|4|5) qwen35_parity_section_cflags="$qwen35_parity_section_cflags -DAIUEOS_QWEN35_C_REFERENCE_NORM=1" ;;
  esac
  # And the attention object (cutover stage 3): only profile 3 links it.
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    1|2|4|5) qwen35_parity_section_cflags="$qwen35_parity_section_cflags -DAIUEOS_QWEN35_C_REFERENCE_ATTENTION=1" ;;
  esac
  # And the recurrent-step object (cutover stage 4): only profile 4 links it.
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    1|2|3|5) qwen35_parity_section_cflags="$qwen35_parity_section_cflags -DAIUEOS_QWEN35_C_REFERENCE_RECURRENT=1" ;;
  esac
  # And the rope object (cutover stage 5): only profile 5 links it.
  case "${AIUEOS_QWEN35_KOTOBA_PARITY:-0}" in
    1|2|3|4) qwen35_parity_section_cflags="$qwen35_parity_section_cflags -DAIUEOS_QWEN35_C_REFERENCE_ROPE=1" ;;
  esac
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $qwen35_parity_section_cflags \
    -c -o "$kernel_qwen35_runtime_object" "$aiueos/kernel/qwen35_runtime.c"
  zig cc -target x86_64-freestanding-none -std=c11 -O3 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $qwen35_parity_section_cflags \
    -c -o "$kernel_qwen35_quant_object" "$aiueos/kernel/qwen35_quant.c"
  zig cc -target x86_64-freestanding-none -std=c11 -O3 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $qwen35_parity_section_cflags \
    $qwen35_parity_cflags \
    -c -o "$kernel_qwen35_infer_object" "$aiueos/kernel/qwen35_infer.c"
  qwen35_parity_link="$kernel_qwen35_runtime_object $kernel_qwen35_quant_object $kernel_qwen35_infer_object"
fi
if [ -n "$model_handoff_link" ]; then
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone -I "$out" \
    $model_handoff_cflags \
    -c -o "$kernel_model_handoff_object" "$aiueos/kernel/model_handoff.c"
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $model_handoff_cflags -DAIUEOS_QWEN35_KOTOBA_ADMISSION \
    -c -o "$kernel_qwen35_runtime_object" "$aiueos/kernel/qwen35_runtime.c"
  zig cc -target x86_64-freestanding-none -std=c11 -O3 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $model_handoff_cflags \
    -c -o "$kernel_qwen35_quant_object" "$aiueos/kernel/qwen35_quant.c"
  zig cc -target x86_64-freestanding-none -std=c11 -O3 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $qwen35_smp_cflags \
    $qwen35_vector_cflags \
    $model_handoff_cflags \
    -c -o "$kernel_qwen35_infer_object" "$aiueos/kernel/qwen35_infer.c"
fi
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  $model_handoff_cflags \
  -c -o "$kernel_kototama_runtime_object" "$aiueos/kernel/kototama_runtime.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_job_protocol_object" "$aiueos/kernel/job_protocol.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_tls_aes_object" "$aiueos/kernel/tls_aes_gcm.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_tls13_object" "$aiueos/kernel/tls13.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  $input_smoke_cflags \
  -c -o "$kernel_scheduler_object" "$aiueos/kernel/scheduler.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  $input_smoke_cflags \
  -c -o "$kernel_syscall_object" "$aiueos/kernel/syscall.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  $input_smoke_cflags \
  -c -o "$kernel_process_object" "$aiueos/kernel/process.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  $input_smoke_cflags \
  -c -o "$kernel_loader_object" "$aiueos/kernel/loader.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_smp_object" "$aiueos/kernel/smp.c"
zig cc -target x86_64-freestanding-none \
  -c -o "$kernel_trampoline_object" "$aiueos/kernel/ap_trampoline.S"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_ioapic_object" "$aiueos/kernel/ioapic.c"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone -I "$out" \
  $physical_qualification_cflags \
  $input_smoke_cflags \
  -c -o "$kernel_framebuffer_object" "$aiueos/kernel/framebuffer.c"
if [ -n "$plc_runtime_link" ]; then
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    -c -o "$kernel_plc_runtime_object" "$aiueos/kernel/plc_runtime.c"
  python3 "$aiueos/scripts/make-plc-embedded-assembly.py" \
    "$AIUEOS_PLC_ELF" "$AIUEOS_PLC_RECEIPT" \
    "$AIUEOS_PLC_SIGNATURE" "$AIUEOS_PLC_PUBLIC_KEY" "$out/plc-embedded.S"
  zig cc -target x86_64-freestanding-none -c \
    -o "$kernel_plc_embedded_object" "$out/plc-embedded.S"
fi
if [ -n "$qualification_link" ]; then
  zig cc -target x86_64-freestanding-none \
    -c -o "$kernel_qualification_entry_object" \
    "$aiueos/kernel/qualification_entry.S"
  zig cc -target x86_64-freestanding-none -std=c11 -O2 \
    -ffreestanding -fno-stack-protector -mno-red-zone \
    $persistent_boot_cflags \
    -c -o "$kernel_qualification_object" "$aiueos/kernel/qualification.c"
fi
# --strip-all: the symbol/string tables are ~550 KiB and are never loaded (only
# PT_LOAD segments are), but the loader shas and reads the WHOLE KERNEL.ELF file
# into a 1 MiB buffer, so they count against the ceiling. Stripping them keeps
# the file at its loadable size (~516 KiB). Relocations are resolved at link
# time; a freestanding static kernel needs no symbol table at runtime. The sha
# is recomputed below, so nothing external pins the pre-strip file. (ADR-0107:
# net_ssh_kex pushed the unstripped file over 1 MiB while the loadable size was
# well under it.)
# The physical qualification branches halt before the generic virtio/SMP
# continuation.  Dropping those unreachable whole sections there keeps
# optional model runtimes inside the existing low-2MiB W^X bootstrap boundary.
# The ordinary OS link deliberately keeps its historical section set.
# AIUEOS_K16_LINK_LIST_OUT=<file> writes the EXACT object list this link is
# about to receive, one path per line, and changes nothing else. It exists so
# that the pure-native gate (ADR-0131) can be run against today's production
# link rather than against a list somebody retyped -- the variable names are
# read back out of this very invocation, so a list added here cannot fall out
# of step with the one measured.
if [ -n "${AIUEOS_K16_LINK_LIST_OUT:-}" ]; then
  : > "$AIUEOS_K16_LINK_LIST_OUT"
  for link_var in $(sed -n '/^zig ld\.lld /,/^fi$/p' "$0" \
                      | grep -o '\$[A-Za-z_][A-Za-z0-9_]*' | sed 's/^\$//' \
                      | grep -vxE 'aiueos|kernel|qualification_gc_link'); do
    eval "set -- \$$link_var"
    for link_path in "$@"; do
      printf '%s\n' "$link_path" >> "$AIUEOS_K16_LINK_LIST_OUT"
    done
  done
  echo "AIUEOS_K16_LINK_LIST_WRITTEN entries=$(wc -l < "$AIUEOS_K16_LINK_LIST_OUT" | tr -d ' ') path=$AIUEOS_K16_LINK_LIST_OUT"
fi
# -Map: the image stays stripped (the symbol tables are never loaded and the
# reason for --strip-all is unchanged), but the link map is written beside it so
# a runtime address can be turned back into a function without rebuilding.
# Every numeric diagnosis in this tree has needed that and none of them had it:
# exit 63 took days to attribute, 0x6f named twenty-seven call sites, and a
# hang at RIP 0x123a41 could be seen but not named. The map is a build-time
# file that ships nowhere.
zig ld.lld -nostdlib -static --strip-all $qualification_gc_link -z max-page-size=0x1000 \
  -Map "$out/kernel.map" \
  -T "$aiueos/kernel/linker.ld" -o "$kernel" \
  "$kernel_entry_object" "$kernel_object" "$kernel_paging_object" \
  "$kernel_acpi_object" "$kernel_vtd_object" "$kernel_apic_object" "$kernel_memory_object" \
  "$kernel_pci_object" "$kernel_rtl8125_object" \
  "$kernel_micro_infer_object" "$kernel_inference_status_object" \
  $device_result_link $model_handoff_link "$kernel_kototama_runtime_object" \
  "$kernel_job_protocol_object" \
  "$kernel_tls_aes_object" "$kernel_tls13_object" \
  "$kernel_scheduler_object" "$kernel_syscall_object" \
  "$kernel_process_object" "$kernel_loader_object" \
  "$kernel_smp_object" "$kernel_trampoline_object" \
  "$kernel_ioapic_object" "$kernel_framebuffer_object" $plc_runtime_link $qualification_link \
  "$kotoba_kernel_object" \
  "$kotoba_journal_object" "$kotoba_fnv_object" "$kotoba_journal_valid_object" \
  "$kotoba_transaction_valid_object" "$kotoba_transaction_route_object" \
  "$kotoba_mutable_valid_object" \
  "$kotoba_superblock_valid_object" "$kotoba_journal_build_object" \
  "$kotoba_mutable_build_object" "$kotoba_cap_valid_object" \
  "$kotoba_extent_valid_object" "$kotoba_region_valid_object" \
  "$kotoba_pci_config_read_object" "$kotoba_pci_config_write_object" \
  "$kotoba_rtl8125_identify_object" "$kotoba_rtl8125_link_up_object" \
  "$kotoba_rtl8125_ring_build_object" "$kotoba_rtl8125_program_object" \
  "$kotoba_rtl8125_tx_submit_object" "$kotoba_rtl8125_rx_poll_object" \
  "$kotoba_x25519_object"   "$kotoba_ecdsa_object" $ecdsa_sign_link $ecdsa_public_link "$kotoba_ime_object" \
  "$kotoba_aes128_gcm_object" "$kotoba_tls13_record_object" \
  $qwen35_kotoba_link $qwen35_parity_link \
  "$kotoba_device_worker_canonical_object" \
  "$kotoba_sha256_stream_object" "$kotoba_sha256_region_object" \
  "$kotoba_device_worker_digest_object" \
  "$kotoba_wm_object" "$kotoba_scanout_object" "$kotoba_broker_object" "$kotoba_session_object" \
  "$kotoba_browser_frame_object" "$kotoba_browser_reduce_object" "$kotoba_browser_frame2_object" "$kotoba_browser_ime_object" \
  "$kotoba_browser_damage_object" \
  "$kotoba_mmio_map_admit_object" \
  "$kotoba_acpi_checksum_object" "$kotoba_acpi_table_valid_object" \
  "$kotoba_relay_hello_object" "$kotoba_relay_ack_object" \
  "$kotoba_inference_status_valid_object" "$kotoba_inference_rate_object" \
  "$kotoba_job_protocol_object" "$kotoba_micro_infer_next_object" \
  "$kotoba_aes128_gcm_selftest_object" \
  "$kotoba_vtd_admit_object" \
  "$kotoba_msr_read_object" "$kotoba_msr_write_object" \
  "$kotoba_idt_gate_object" "$kotoba_pic_disable_object" \
  "$kotoba_cpu_feature_nx_object" "$kotoba_cpu_feature_syscall_object" \
  "$kotoba_cpu_apic_id_object" \
  "$kotoba_syscall_range_object" "$kotoba_copy_in_object" \
  "$kotoba_allocator_plan_object" \
  "$kotoba_capability_object" "$kotoba_capability_mutation_object" \
  "$kotoba_service_lifecycle_object" \
  "$kotoba_service_registry_object" "$kotoba_service_registry_state_object" \
  "$kotoba_user_object_journal_object" \
  "$kotoba_user_object_journal_valid_object" \
  "$kotoba_user_object_journal_value_object" "$kotoba_sha256_object" \
  "$kotoba_digest_equal_object" "$kotoba_catalog_valid_object" \
  "$kotoba_app_lookup_object" \
  "$kotoba_user_elf_valid_object" \
  "$kotoba_user_context_object" \
  "$kotoba_kernel_context_object" \
  "$kotoba_mapping_plan_object" \
  "$kotoba_process_plan_object" \
  "$kotoba_teardown_plan_object" \
  "$kotoba_task_plan_object" \
  "$kotoba_dispatch_plan_object" \
  "$kotoba_exit_route_object" \
  "$kotoba_service_task_object" \
  "$kotoba_rsa2048_object" \
  "$kotoba_net_arp_object" \
  "$kotoba_ipv4_checksum_object" \
  "$kotoba_ipv4_icmp_object" \
  "$kotoba_tcp_checksum_object" \
  "$kotoba_tcp_segment_object" \
  "$kotoba_dhcp_reply_object" \
  "$kotoba_dhcp_option_object" \
  "$kotoba_qwen35_vocab_index_object" \
  "$kotoba_qwen35_tokenize_object" \
  "$kotoba_qwen35_detokenize_object"
fi
initramfs="$kernel_dir/INITRD.IMG"
recovery_signature="$aiueos/kotoba/user-smoke.sig"
if [ "${AIUEOS_CORRUPT_RECOVERY_SIG:-0}" = 1 ]; then
  # Test-only: a structurally valid archive whose recovery signature fails
  # the RSA policy. The archive digest is recomputed below, so the loader
  # admits it and the kernel admission must be the layer that rejects.
  recovery_signature="$out/corrupt-recovery.sig"
  python3 - "$aiueos/kotoba/user-smoke.sig" "$recovery_signature" <<'PYSIG'
from pathlib import Path
import sys
data = bytearray(Path(sys.argv[1]).read_bytes())
data[17] ^= 1
Path(sys.argv[2]).write_bytes(data)
PYSIG
fi
python3 "$aiueos/scripts/make-initramfs.py" \
  --entry "recovery/user-smoke.elf,$aiueos/kotoba/user-smoke.elf" \
  --entry "recovery/user-smoke.sig,$recovery_signature" \
  --entry "recovery/app-catalog.sig,$aiueos/kotoba/app-catalog.sig" \
  --entry "font/aiueos-16.fnt,$aiueos/fonts/aiueos-16.fnt" \
  --entry "ime/aiueos-kanji.dic,$aiueos/ime/aiueos-kanji.dic" \
  --output "$initramfs" >/dev/null
python3 - "$kernel" "$initramfs" "$identity_source" <<'PY'
import hashlib, pathlib, sys
kernel_digest = hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).digest()
initramfs_digest = hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).digest()
def values(digest):
    return ",".join(f"0x{byte:02x}" for byte in digest)
pathlib.Path(sys.argv[3]).write_text(
    "#include <stdint.h>\n"
    "const uint8_t aiueos_expected_kernel_sha256[32]={" + values(kernel_digest) + "};\n"
    "const uint8_t aiueos_expected_initramfs_sha256[32]={" + values(initramfs_digest) + "};\n",
    encoding="ascii")
PY
zig cc -target x86_64-windows-gnu -std=c11 -O2 -ffreestanding \
  -c -o "$identity_object" "$identity_source"
if [ "${AIUEOS_EMBEDDED_RELEASE:-0}" = 1 ]; then
  python3 - "$kernel" "$initramfs" "$embedded_source" <<'PYEMBED'
from pathlib import Path
import hashlib
import sys

kernel_path = Path(sys.argv[1]).resolve()
initramfs_path = Path(sys.argv[2]).resolve()
kernel = kernel_path.as_posix()
initramfs = initramfs_path.as_posix()
kernel_sha256 = hashlib.sha256(kernel_path.read_bytes()).hexdigest()
initramfs_sha256 = hashlib.sha256(initramfs_path.read_bytes()).hexdigest()
Path(sys.argv[3]).write_text(
    f'# aiueos-embedded-kernel-sha256={kernel_sha256}\n'
    f'# aiueos-embedded-initramfs-sha256={initramfs_sha256}\n'
    '.section .rdata,"dr"\n'
    '.balign 16\n'
    '.globl aiueos_embedded_kernel_start\n'
    'aiueos_embedded_kernel_start:\n'
    f'.incbin "{kernel}"\n'
    '.globl aiueos_embedded_kernel_end\n'
    'aiueos_embedded_kernel_end:\n'
    '.balign 16\n'
    '.globl aiueos_embedded_initramfs_start\n'
    'aiueos_embedded_initramfs_start:\n'
    f'.incbin "{initramfs}"\n'
    '.globl aiueos_embedded_initramfs_end\n'
    'aiueos_embedded_initramfs_end:\n',
    encoding='ascii')
PYEMBED
  zig cc -target x86_64-windows-gnu -c \
    -o "$embedded_object" "$embedded_source"
fi
if [ -n "$model_slots_link" ]; then
  zig cc -target x86_64-windows-gnu -std=c11 -O2 \
    -ffreestanding -fno-builtin -fshort-wchar -fno-stack-protector -mno-red-zone \
    -I "$aiueos/uefi" -c -o "$model_slots_object" \
    "$aiueos/uefi/model_slots.c"
fi
zig cc -target x86_64-windows-gnu -std=c11 -O2 \
  -ffreestanding -fshort-wchar -fno-stack-protector -mno-red-zone \
  -I "$out" -I "$aiueos/uefi" \
  $gop_discovery_cflags $physical_qualification_cflags $loader_failure_test_cflags \
  $loader_hang_test_cflags $qualification_watchdog_cflags \
  $embedded_release_cflags $netboot_qualification_cflags \
  $persistent_boot_cflags $model_handoff_cflags $model_slots_cflags \
  -c -o "$object" "$aiueos/uefi/main.c"
zig lld-link /subsystem:efi_application /entry:efi_main /nodefaultlib /timestamp:0 \
  /fixed:no "/out:$efi" "$object" "$identity_object" \
  $embedded_release_link $model_slots_link

if [ "${AIUEOS_EMBEDDED_RELEASE:-0}" = 1 ]; then
  # `.incbin` inputs are not compiler source files.  Keep both a content salt
  # in embedded-release.S (above) and this post-link admission so a stale Zig
  # object can never be published with fresh expected digests.
  python3 - "$efi" "$kernel" "$initramfs" <<'PYVERIFYEMBED'
from pathlib import Path
import sys

image = Path(sys.argv[1]).read_bytes()
for label, source in (("kernel", sys.argv[2]), ("initramfs", sys.argv[3])):
    payload = Path(source).read_bytes()
    first = image.find(payload)
    if first < 0 or image.find(payload, first + 1) >= 0:
        raise SystemExit(
            f"error: linked EFI must contain exactly one current {label} payload")
print("AIUEOS_EMBEDDED_POSTLINK_OK kernel+initramfs exact-current-bytes")
PYVERIFYEMBED
fi

magic=$(dd if="$efi" bs=1 count=2 2>/dev/null)
[ "$magic" = MZ ] || {
  echo "error: $efi is not a PE/COFF image" >&2
  exit 1
}
[ "$(dd if="$kernel" bs=1 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')" = 7f454c46 ] || {
  echo "error: $kernel is not an ELF image" >&2
  exit 1
}

# The freshness receipt (ADR-0155). Written LAST, from the artifacts that were
# just produced and the tree they were produced from, so that a boot harness
# can refuse an image it did not just build. Nothing above this line is allowed
# to have failed: `set -e` is on, and the receipt is therefore evidence that the
# whole build ran, not merely that a file called BOOTX64.EFI exists.
#
# `python3` absent is a REFUSAL, not a skip. A build that quietly shipped no
# receipt would put every downstream `assert` into could-not-run, which is
# exactly the state this file exists to make impossible. The checker is the
# Node-free port (`image-freshness.py`): the nbb original stays in the tree as
# the dev-time oracle only, and NBB/Node must not sit on the accepted build
# path (JUN-31 acceptance).
command -v python3 >/dev/null 2>&1 || {
  echo "error: python3 is required to write the image freshness receipt" >&2
  exit 3
}
python3 "$aiueos/scripts/image-freshness.py" record \
  --out "$out/image-receipt.edn" --root "$repo" \
  "$efi" "$kernel" "$initramfs" >/dev/null

echo "$efi"
