# ADR-0013: A writable region, and the address of a function

- Status: accepted
- Date: 2026-09-02

## Context

ADR-0011 (read-only literals and the two wider firmware calls) closed with two
things a Kotoba UEFI application still could not do, and both are the same
missing noun: an ADDRESS the program is allowed to name.

1. **Every remaining UEFI boot service takes an out-pointer.**
   `AllocatePages(type, memtype, pages, &addr)`,
   `HandleProtocol(handle, &guid, &iface)` and `GetMemoryMap`'s five all write
   through a pointer the caller supplies, and this IR could not produce one
   that pointed at writable memory. The literal pool of ADR-0011 is in
   `.text`, which the packager marks `0x60000020` -- read and execute.
   `:boot-info` and `:system-table` answer with words the FIRMWARE handed over,
   not with the address of the context slot they were parked in. `OpenProtocol`
   worked only because `EFI_OPEN_PROTOCOL_TEST_PROTOCOL` makes the firmware
   ignore the out-parameter entirely.
2. **`:jump-to` has never been executed.** It has been encoded and gated since
   ADR-0008, and nothing produced the address of a Kotoba function to give it.

## Decision

**`:scratch-region`, a zero-arity privileged action.** It answers with the base
of a writable area the image packager reserves inside the image's own `.data`,
past the hidden context. An ADDRESS rather than a load, like
`:page-fault-handler-address` -- so no context slot has to be published and an
image that did not reserve the area cannot answer zero and be believed.

The LENGTH is deliberately NOT a second action. It is a compile-time constant,
and the place a program already writes one is the window length of the checked
`kernel-load-*`/`kernel-store-*` it declares over the region; kotoba-sema
refuses a window wider than the reservation, naming both numbers. A second
action returning the same number would be a second spelling of one constant,
and the pair `bytes-literal`/`bytes-literal-length` is not the precedent it
looks like: THAT length is a property of a piece of source text the program
cannot otherwise count, and this one is a number the program writes anyway.

**`:gmir/function-address`, its own instruction rather than a privileged
action.** The operand is a NAME. Every privileged action's arguments are
virtual registers by the time a backend sees them, which is exactly the
argument ADR-0011 made for giving `:rodata-address` its own instruction, and
the argument ADR-0010's `:isr-entry-address` avoided by taking a vector NUMBER
instead of a name. `:gmir/function` is a `function-id?` symbol -- the shape
`:gmir/callee` already carries.

**A v3 module resolves the name against its own function list**, and reports
`:unresolved-function-address` rather than `:unresolved-callee`. The two are
different mistakes: one calls something that is not there, the other takes the
address of something that is not there, and only the second can occur in a
program that contains no call to the name at all -- which is the whole point
of the operation.

**A flat v1/v2 program refuses it outright**
(`:function-address-needs-a-module`). There is no function list to resolve
against, and the backend's flat encoder passes an EMPTY callee-label table, so
without this the report would be `unknown-call-target` -- a sentence about a
call the program does not contain.

## Consequences

- `:scratch-region` is admitted here for every target that admits the x86
  privileged channel at all, as every action in that table is; WHICH target
  may name it is amu's, and amu puts it with the UEFI-only operations rather
  than with the literals. The reason is measured and is in kotoba-native
  ADR-0052: at the displacement the backend uses, a kernel image's context
  holds its GDT.
- Eight operands remains the widest privileged arity. `:scratch-region` is
  zero, so nothing about the register tiers moves.
- **ADR-0011 has no file in this repository.** Seven repositories' ADRs cite
  it -- kotoba-mir 0016, kotoba-kir 0235, kotoba-codegen 0010, kotoba-sema
  0007, kotoba-native 0046, kotoba-verifier 0025, amu 0295 -- and the commit
  that landed the decision (`fe23816`) touched `src/kotoba/gmir.cljk` and
  `test/kotoba/gmir_rodata_test.cljk` and nothing else. The citations are not
  wrong about the DECISION, which is in the source comments at
  `:gmir/rodata-address` and `:uefi-call4`/`:uefi-call6`; they are wrong about
  there being a document. Recorded here rather than fixed, because writing
  another stream's ADR after the fact would be inventing its reasoning.
