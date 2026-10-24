# ADR 0010: The interrupt entry address is one action taking the vector

## Status

Accepted.

## Decision

One action joins the closed x86 privileged family:

    :isr-entry-address 1

`(vector) -> the address of the toolchain-generated interrupt entry for that
vector`. An IDT gate descriptor splits that address across three offset fields,
so a kernel that installs its own IDT cannot do so without being able to name
an entry.

## Why the operand is a number and not a name

An interrupt entry is declared in Kotoba as `aiueos-isr-<vector>`, so the name
and the vector carry the same information and neither is derived from the
other. Taking the number is what lets this ride the ordinary privileged
channel: `:gmir/x86-privileged` operands are virtual registers, and a symbol
operand would have to survive GMIR validation, MIR selection and register
allocation as a literal. Nothing in this IR carries one, and adding a second
operand kind for one action is a larger change than the action is worth.

The vector is therefore an ordinary runtime value here. The bound that keeps
it inside the entry table is the backend's, not this table's -- kotoba-native
emits the comparison and traps above it.

## Why arity 1 rather than 0

The family already holds three zero-arity address actions:
`:page-fault-handler-address`, `:page-fault-recovery-handler-address` and
`:double-fault-handler-address`. Each names exactly ONE canned byte sequence,
which is why each can be nullary. This action names any member of a table, so
it needs an operand, and those three keep their arity -- the test pins all four
together so that widening one cannot be mistaken for widening the family.

## What this table does not say

Where the answer comes from. In the bootable-image route it is a load from the
kernel context, because the entries are laid down by the ELF image packager
after every byte of the function has been emitted; in the relocatable-object
route there is no answer at all, because the context there is the object's own
private 80 bytes. That refusal is kotoba-native's, and it is a refusal rather
than a read past the end of a private context.

## Evidence

`kbb -M:test`: 20 tests, 238 assertions, 0 failures.

One deliberate break, producing the failure it names and no other: changing
the arity to 2 turns the arity assertion red and makes the one-argument
program throw `GMIR rejected: invalid-x86-privileged` -- which is what the
action got before this row existed and the reason it exists.
