# Agent rules

The workspace contract in `com-junkawasaki/root/AGENTS.md` applies.
Canonical new implementation and final execution use Kotoba and Amu selfhost
native. Preserve historical CLJK sources as migration inventory; do not use
JVM, NBB, Babashka, KBB, Node, or a host EVM as implementation fallback.

## CDCI stopped: no JVM or NBB

Per the owner decision of 2026-10-22 (JUN-290), the workflow
`.github/workflows/kototama-platform.yml` was removed during AWAI-81. It
installed Babashka and the NBB-backed KBB runner on Ubuntu/macOS/Windows.
Do not retain it disabled or restore it as fallback.

The portable CLJK Kototama program cross-platform suite is no longer covered
by CI. No replacement native CI/controller is qualified. AWAI-81's local
checked-module and process-crash gates are recorded in `docs/native-evm-status.md`; they
qualify a bounded native project closure; they do not replace whole public API migration,
cross-platform execution, artifact admission, or runtime resource gates.
Keep missing gates blocked and report their actual status.

## Native EVM candidate

`conformance/native/awai81-profile.json` is explicitly experimental and not
selected by the existing implementation profile. Do not promote subset
frame or message-domain evidence into full EVM/FEVM, Ethereum transaction,
MPT proof, durable exactly-once, or live consensus qualification. Native
release and production cutover remain separate gates.
