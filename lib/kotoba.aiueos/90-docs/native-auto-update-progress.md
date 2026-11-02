# Native automatic update progress (AWAI-122, 2026-11-02)

The full goal is verified OS-pulled updates, durable version policy, safe
activation/trial boot/recovery, retained app state, and macOS-like automatic
preparation plus Now/Tonight/Later settings. None is replaced by this component
receipt. Current production update.begin still accepts version>=1; the new
journal is not yet called by install/boot and does not protect that route yet.

OSMETA.BIN is a separate checked20KiB FAT32 file. The shared record-file
mechanism retains STATE.BIN's format, checks GPT/header/table CRC, FAT copies,
contiguous/aligned allocation and disjointness from BOOTX64.EFI, UPDATE.BIN and
the other record file. An existing malformed file is never reformatted. New
allocation validates known live chains and an existing peer before any write.
Only explicit provisioning creates a file; read-only boot never creates one.

The native update journal uses marker0, publication head1 and alternating
slots2/3. Each512-byte record occupies a separate4KiB page. Writes flush and
read back the complete slot before publishing a matching generation/digest,
then flush/read back the head. A corrupt published record refuses even when
another old slot is valid. An unpublished newer slot is ignored. The checksum
is integrity evidence, not a TPM-protected or authenticated monotonic counter.

The record keeps generation, policy bits, last confirmed version/digest,
highest accepted version, candidate version/digest, prepared/trial/rollback
state and trial count. Trusted callers must verify the artifact before prepare
and obtain real health evidence before confirm. Trial/rollback retain the
higher floor, so a failed new release cannot make an older network release
admissible. Confirm requires exact candidate version and digest. Policy flags
are stored data, not network/operation approval. No clock or automatic reboot
policy is enabled by this unit.

The exact36-module filesystem component executes30 actual QEMU cold boots:
provision/prepare, cold restore, duplicate/replayed version refusal, trial,
wrong confirmation digest refusal, exact confirmation, failed-trial rollback
with retained floor, policy save/cold restore, reinitialization refusal,
unknown policy bits, floor above u32 and signed-u64 positive limit/cold restore,
unpublished native slot, damaged marker/head/slot/payload/digest, checksummed
invalid schema, cross-file alias and GPT CRC refusal. All refusal/read boots
leave the disk unchanged; app STATE.BIN and the existing EFI image are preserved.
This is modeled crash ordering, not hardware power-cut qualification.

This test root never enables a user domain and its required user ABI entries
refuse all calls. Its NVMe/ESP/journal implementation is real; it cannot qualify
CPL3/ValueRuntime/app execution. The production input-entry retains its actual
providers, reproduces with44 modules and passes the full12 USB/NVMe state
checks separately. Initial isolated provider roots were refused by the pinned
region prover (E7106); a full-provider diagnostic root exceeded RXcap (E7104).
Those failures are retained locally. The filesystem-only root uses the same
fixed grants, with actual desktop source roots for provenance and deny-all user
ABI. It is not a substitute production kernel. Direct product integration and
its exact code-budget admission remain future work.

The first shared-file build also exceeded the unchanged RXcap. Public UI
literals now pack u64 pairs behind the original u32 lookup interface, and nine
public legacy SMP KAT tables use packed words. Native23-module execution matches
all1224 UI selector words/104 bounds, legacy126 original bytes/288 selector
bytes/18 bounds, plus the existing SC369 bytes/1216 selectors/38 bounds and
HID139 bytes/160 selectors/4 bounds. Original public literal data and source
hashes are retained. No production test/feature or memory allowance was removed.

Remaining integration: signature/version admission in network install; durable
bootstrap from an independently verified installed image; staged artifact
binding; atomic activation and real boot-attempt/health handling; recovery and
power cuts; user settings/notifications and a valid clock for Tonight; automatic
check/download/prepare; ML-DSA/boot trust and the normal disk-boot route. PXE and
the Mac management bridge are preserved; no hardware install/provision/update
was performed by this unit. Physical mouse/HHKB checks are paused at the owner's
request. The next priority is Mac remote screen/mouse/key operation (AWAI-119).

Evidence: docs/evidence/awai122-update-journal-20261102/.
