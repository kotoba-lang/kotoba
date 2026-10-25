# ADR-0001: Extract deterministic final machine-code layout

- Status: accepted
- Date: 2026-08-09

## Context

x86-64 and AArch64 production emitters share a two-pass boundary for labels and
PC-relative branches. Keeping that contract inside one native backend obscured
the MIR-to-MC ownership line and made future backends likely to copy it.

## Decision

`kotoba-codegen` owns canonical final-layout tokens and deterministic
resolution. It validates labels, encodings, operands, displacement range and
alignment, and verifies that the target encoder returns the reserved width.
It also owns the closed allocated MC program schema handed from MIR allocation
to target byte encoders. MC validation reuses MIR's physical-register and
control-flow authority rather than duplicating those rules.

Target backends still own instruction selection and byte encoding. `kotoba-mir`
still owns target selection and register allocation. `kotoba-codegen` depends
on MIR only to validate the physical-register/control-flow projection; it does
not import a target backend.

## Consequences

Both x86-64 and AArch64 production emitters consume one layout authority. The
repository can grow toward more MIR-to-MC contracts without absorbing ABI,
runtime, or object-container policy.
