# ADR-0123: K16 Qwen one-shot qualification uses a bounded model-sized watchdog

## Status

Accepted (2026-08-30)

## Context

The physical K16 loaded the one-shot Qwen/Murakumo EFI and returned through the
PXE control image with `AIUEOS_QUALIFICATION_RESULT state=incomplete code=210`.
Code 210 is persisted immediately before allocating, loading and admitting the
exact 10,934,860,704-byte GGUF.  The generic 90-second loader watchdog reset the
machine before that stage completed.  This is recovery evidence, not a model
admission, inference or Murakumo failure.

Persistent node images disable the watchdog, but they cannot automatically
return the bounded NVRAM result to the PXE control image.  The qualification
run needs both enough time for the exact artifact and a finite recovery bound.

## Decision

`build-uefi.sh` accepts an explicit physical-qualification-only loader watchdog
from 1 through 3,600 seconds.  Persistent builds refuse the setting because
their watchdog is disabled.  Ordinary one-shot qualification remains at 90
seconds.

The dedicated Qwen/Murakumo one-shot profile uses 1,800 seconds.  It still:

- writes only the 16-byte qualification record and the existing BootNext value;
- does not write the internal SSD, USB model media or BootOrder;
- resets into the PXE control image after a terminal result; and
- reports physical success only after exact model admission, the frozen first
  token, signed HTTPS POST and HTTP admission all complete.

## Evidence boundary

The observed code 210 proves only that the real K16 entered model admission and
that the 90-second recovery path worked.  The longer image remains unverified
until a later physical boot returns a terminal result.
