# ADR-0229: A UEFI entry contract that keeps its arguments, and four boundary operations

- Status: accepted
- Date: 2026-09-02

## Context

`:x86_64-aiueos-uefi-v1` declared one entry contract,
`:microsoft-x64-zero-arity-efi-status-v1`. UEFI calls an EFI image entry point
with `(EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable)` in RCX and RDX;
the shim amu emits for that contract discards both. A Kotoba program compiled
for this target therefore could not reach the firmware AT ALL -- not the
console, not boot services, not the memory map -- which is why
`os/aiueos/uefi/main.c` is still C.

## Decision

The profile declares two entry contracts and names the new one as its default:

```clojure
:entry-contract  :microsoft-x64-two-arity-efi-status-v2
:entry-contracts {0 :microsoft-x64-zero-arity-efi-status-v1
                  2 :microsoft-x64-two-arity-efi-status-v2}
```

v2 is `(defn main [image-handle system-table] ...)` returning an i64
EFI_STATUS. The shim parks RCX and RDX in the hidden context, at +0x50 and
+0x58, where `kernel-boot-info` and `kernel-system-table` read them.
`kernel-boot-info` keeps its instruction (`mov r, [r9+0x50]`) and gains a
per-target meaning: the boot-info pointer under the kernel profile, the
ImageHandle under this one. The packager chooses the contract by the entry's
arity, so v1 keeps working and `:entry-contract` is the default a new program
gets rather than the only one available.

Four operations join the privileged family and, at this oracle, refuse:

| operation | arity | why it cannot be answered here |
|---|---|---|
| `kernel-system-table` | 0 | the pointer is the FIRMWARE's choice |
| `kernel-load-ptr` | 2 | the memory is the firmware's |
| `kernel-uefi-call2` | 4 | the code is the firmware's |
| `kernel-jump-to` | 2 | there is no value: it does not return |

They also mark a module kernel-native, so no constant folder pre-answers one.

## Consequences

- `kotoba.kir-uefi-boundary-test` pins `:kernel-privileged-unavailable` and the
  offending operation for all four. Break-checked by removing `kernel-load-ptr`
  from the set: the trap becomes `:unknown-function`, which is a different
  refusal and a red test.
- The oracle can never confirm a boot. Anything built on these operations is
  qualified by running it, not by executing the KIR.
- KIR states the contract; it does not enforce which target may use the three
  firmware operations. amu owns that gate, because KIR's interpreter does not
  see a target keyword.
